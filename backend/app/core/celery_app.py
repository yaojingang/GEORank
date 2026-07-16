"""
Celery 异步任务引擎配置
"""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "georank",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.crawl",
        "app.tasks.process",
        "app.tasks.diagnose",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={"visibility_timeout": 900},
    # 任务路由
    task_routes={
        "app.tasks.crawl.*": {"queue": "crawl"},
        "app.tasks.process.*": {"queue": "process"},
        "app.tasks.diagnose.*": {"queue": "diagnose"},
    },
    # Beat 定时任务
    beat_schedule={
        "re-diagnose-companies": {
            "task": "app.tasks.process.re_diagnose_all",
            "schedule": 60 * 60 * 24 * 30,  # 每 30 天
        },
    },
)
