# 数据库迁移与启动

GEOrank 使用 Alembic 作为数据库结构的唯一所有者。Docker Compose 中的 `migrate` 是唯一迁移服务；它成功退出后，API、Worker、Beat 和 Crawler 才会启动。应用镜像的统一 entrypoint 还会执行只读的 `python -m app.scripts.migrate --check`，因此直接运行 API 或 Celery 镜像时，数据库未迁移或版本落后都会立即退出。

## 首次启动

```bash
cp .env.example .env
docker compose up -d
```

启动链路会等待 PostgreSQL 健康，获取 PostgreSQL advisory lock，运行 `alembic upgrade head`，再核对数据库中的版本与代码仓库 Alembic head 完全一致。迁移失败会让依赖服务保持停止状态。

`migrate` 只接收数据库连接所需环境变量，不读取应用 `.env` 中的第三方密钥。应用服务仍通过 `GEORANK_ENV_FILE` 加载运行配置，默认值为 `.env`。

可用以下命令查看状态：

```bash
docker compose ps
docker compose logs migrate
docker compose exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "TABLE alembic_version;"'
```

`migrate` 正常完成后会显示 `Exited (0)`。API 应显示 `healthy`。

## 升级和重复执行

拉取新版本后执行：

```bash
docker compose run --rm migrate
docker compose up -d
```

`alembic upgrade head` 可安全重复执行。迁移服务使用 session-level advisory lock；即使维护人员同时发起两次命令，也只会有一个进程修改结构。

种子脚本只写入示例数据，执行前必须先完成迁移：

```bash
docker compose run --rm migrate
docker compose run --rm api python -m app.scripts.seed
```

## 无 Alembic 版本的旧数据库

早期开发启动路径可能通过 SQLAlchemy `create_all` 创建表，却没有 `alembic_version`。迁移服务发现 GEOrank 管理表存在且版本表缺失时会停止，并输出 `managed tables exist without alembic_version`。它不会自动 stamp，也不会修改这类数据库。

恢复步骤：

1. 停止 API、Worker、Beat 和 Crawler。
2. 使用 `pg_dump` 创建完整备份，并在隔离环境验证备份可恢复。
3. 数据无需保留时，创建空数据库或空 volume，再运行 `docker compose up -d`。
4. 数据需要保留时，在隔离数据库中比对旧结构与 Alembic 各 revision，编写并审核一次性 reconciliation migration。确定真实 revision 后才能进行显式 stamp。
5. 在副本上完成 `alembic upgrade head`、数据核对和应用冒烟测试，再安排正式切换。

请勿根据表名猜测 revision，也不要直接对生产库执行 `alembic stamp head`。这会掩盖结构漂移，并让后续迁移在错误基线上继续运行。

迁移脚本使用显式、只追加的 `ALEMBIC_MANAGED_TABLES` 清单识别旧数据库。新增 `op.create_table(...)` 迁移时，必须把表名追加到该清单；测试会校验所有历史迁移中的建表操作都已覆盖。已有表名不应从清单移除，即使后续迁移删除了该表。

## 自动验证

```bash
scripts/check-container-migration-bootstrap.sh
```

该契约在正式 `docker-compose.yml` 上叠加隔离 override，使用实际 Docker image 和生产服务依赖，覆盖 fresh database、直接启动应用镜像的只读门禁、空库并发迁移、重复升级、5 位专家 seed、API healthcheck、legacy fail-closed，以及迁移失败阻止 API 启动。
