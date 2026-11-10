from typing import Any, Callable
from app.config import Config

try:
    from celery import Celery  # type: ignore
except ImportError:  # pragma: no cover - fallback cuando Celery no está instalado en el entorno local de tests
    class _FallbackTask:
        def __init__(self, func: Callable[..., Any], **options: Any):
            self._func = func
            self.name = options.get('name', func.__name__)
            self.autoretry_for = options.get('autoretry_for', ())
            self.max_retries = options.get('max_retries', 3)
            self.retry_backoff = options.get('retry_backoff', False)
            self.__name__ = func.__name__
            self.__doc__ = func.__doc__

        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            return self._func(*args, **kwargs)

        def delay(self, *args: Any, **kwargs: Any) -> Any:
            return self._func(*args, **kwargs)

        def apply_async(self, args: Any = None, kwargs: Any = None, **_options: Any) -> Any:
            return self._func(*(args or ()), **(kwargs or {}))

    class Celery:  # type: ignore[no-redef]
        def __init__(self, main: str, broker: str = '', backend: str = ''):
            self.main = main
            self.conf: dict[str, Any] = {'broker_url': broker, 'result_backend': backend}

        def task(self, *args: Any, **options: Any) -> Callable[..., Any]:
            def decorator(func: Callable[..., Any]) -> _FallbackTask:
                return _FallbackTask(func, **options)
            if args and callable(args[0]):
                return decorator(args[0])
            return decorator


def make_celery() -> Celery:
    """Crea y configura la instancia Celery para tareas de indexación en segundo plano."""
    celery = Celery(
        'chatbot_tasks',
        broker=Config.CELERY_BROKER_URL,
        backend=Config.CELERY_RESULT_BACKEND,
    )
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        task_acks_late=True,
    )
    return celery


celery_app = make_celery()
