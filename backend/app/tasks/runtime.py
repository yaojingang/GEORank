"""
Celery 任务运行时辅助。

为每个 Celery 子进程固定一个事件循环，避免 prefork 模式下反复
`asyncio.run()` 导致 asyncpg 连接绑定到不同 loop。
"""
import asyncio

from celery.signals import worker_process_init, worker_process_shutdown

_task_loop: asyncio.AbstractEventLoop | None = None


def get_task_loop() -> asyncio.AbstractEventLoop:
    global _task_loop

    if _task_loop is None or _task_loop.is_closed():
        _task_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_task_loop)

    return _task_loop


def run_async(coro):
    """在当前 Celery 子进程的固定 loop 上执行协程。"""
    loop = get_task_loop()
    return loop.run_until_complete(coro)


async def _dispose_async_engine() -> None:
    try:
        from app.core.database import engine
        await engine.dispose()
    except Exception:
        pass


@worker_process_init.connect
def _init_worker_runtime(**_kwargs):
    global _task_loop

    if _task_loop is not None and not _task_loop.is_closed():
        _task_loop.close()

    _task_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_task_loop)
    _task_loop.run_until_complete(_dispose_async_engine())


@worker_process_shutdown.connect
def _shutdown_worker_runtime(**_kwargs):
    global _task_loop

    if _task_loop is None or _task_loop.is_closed():
        _task_loop = None
        return

    _task_loop.run_until_complete(_dispose_async_engine())
    _task_loop.close()
    _task_loop = None
