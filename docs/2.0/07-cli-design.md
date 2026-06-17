# 07. CLI 设计

## 目标

把高频后台操作和修复动作命令化，而不是继续依赖手点后台和零散脚本。

## 技术选型

- Typer

## 命令树

```text
georank
  auth
    login
    whoami
    logout
  company
    submit
    recrawl
    publish
    delete
  diagnostic
    run
    rerun
    export
  solutions
    generate
    export
  keywords
    expand
    export
  tutorial
    publish
    translate
    backfill
  ops
    rebuild-index
    sync-qdrant
    sync-neo4j
    repair-data
```

## 第一阶段必须起的命令

- `georank auth login`
- `georank company submit`
- `georank diagnostic run`
