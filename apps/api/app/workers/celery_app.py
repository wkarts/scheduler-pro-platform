from collections.abc import Callable
from typing import ParamSpec, TypeVar, cast

from celery import Celery

from app.core.config import settings

P = ParamSpec("P")
R = TypeVar("R")

celery_app = Celery("scheduler_pro", broker=settings.celery_broker_url, backend=settings.celery_result_backend)
celery_app.conf.task_routes = {
    "app.workers.tasks.run_provisioning": {"queue": "provisioning"},
    "app.workers.tasks.process_whatsapp_webhook": {"queue": "whatsapp"},
    "app.workers.tasks.run_build_job": {"queue": "builds"},
}


def typed_task(*, name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Expose Celery's untyped decorator through a typed boundary."""
    return cast(Callable[[Callable[P, R]], Callable[P, R]], celery_app.task(name=name))
