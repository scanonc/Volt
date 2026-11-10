import logging
from typing import Any, Callable, Tuple, Type
from app.config import Config

logger = logging.getLogger(__name__)

try:
    from celery import Celery  # type: ignore
except ImportError:  # pragma: no cover - fallback compatible cuando Celery no está instalado en el host local
    class _FallbackTask:
        def __init__(self, func: Callable[..., Any], **options: Any):
            self._func = func
            self.name = options.get('name', func.__name__)
            self.autoretry_for: Tuple[Type[BaseException], ...] = tuple(options.get('autoretry_for', ()))
            self.max_retries: int = int(options.get('max_retries', 3))
            self.retry_backoff: bool = bool(options.get('retry_backoff', False))
            self.retry_backoff_max: int = int(options.get('retry_backoff_max', 60))
            self.__name__ = func.__name__
            self.__doc__ = func.__doc__

        def _run_with_bounded_retries(self, *args: Any, **kwargs: Any) -> Any:
            attempt = 0
            while True:
                try:
                    return self._func(*args, **kwargs)
                except Exception as exc:
                    if not self.autoretry_for or not isinstance(exc, self.autoretry_for):
                        logger.error("Fallo no recuperable en tarea %s: %s", self.name, exc)
                        raise
                    if attempt >= self.max_retries:
                        logger.error(
                            "Tarea %s agotó el máximo de reintentos (%d): %s",
                            self.name,
                            self.max_retries,
                            exc,
                        )
                        raise
                    attempt += 1
                    logger.warning(
                        "Reintentando tarea %s (intento %d/%d) tras error temporal: %s",
                        self.name,
                        attempt,
                        self.max_retries,
                        exc,
                    )

        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            return self._run_with_bounded_retries(*args, **kwargs)

        def delay(self, *args: Any, **kwargs: Any) -> Any:
            return self._run_with_bounded_retries(*args, **kwargs)

        def apply(self, args: Any = None, kwargs: Any = None, **_options: Any) -> Any:
            return self._run_with_bounded_retries(*(args or ()), **(kwargs or {}))

        def apply_async(self, args: Any = None, kwargs: Any = None, **_options: Any) -> Any:
            return self._run_with_bounded_retries(*(args or ()), **(kwargs or {}))

    class Celery:  # type: ignore[no-redef]
        def __init__(self, main: str, broker: str = '', backend: str = ''):
            self.main = main
            self.conf: dict[str, Any] = {
                'broker_url': broker,
                'result_backend': backend,
                'task_always_eager': False,
            }

        def task(self, *args: Any, **options: Any) -> Callable[..., Any]:
            def decorator(func: Callable[..., Any]) -> _FallbackTask:
                return _FallbackTask(func, **options)
            if args and callable(args[0]):
                return decorator(args[0])
            return decorator


def make_celery() -> Celery:
    """Crea y configura la instancia Celery con Redis como broker para tareas de indexación."""
    celery = Celery(
        'chatbot_tasks',
        broker=Config.CELERY_BROKER_URL,
        backend=Config.CELERY_RESULT_BACKEND,
    )
    celery.conf.update(
        imports=('app.tasks.indexing',),
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        task_acks_late=True,
        broker_connection_retry_on_startup=True,
    )
    return celery


celery_app = make_celery()
