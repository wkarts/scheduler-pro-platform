from collections.abc import Callable
from typing import ParamSpec, TypeVar, cast

from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

from app.core.config import settings

P = ParamSpec("P")
R = TypeVar("R")

DURABLE_QUEUES = (
    "default",
    "provisioning",
    "domains",
    "builds",
    "maintenance",
    "whatsapp",
    "notifications",
    "webhooks",
)

scheduler_exchange = Exchange("scheduler", type="direct", durable=True)

celery_app = Celery(
    "scheduler_pro",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks", "app.workers.agenda_report_tasks"],
)
celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    task_default_queue="default",
    task_default_exchange="scheduler",
    task_default_exchange_type="direct",
    task_default_routing_key="default",
    task_default_delivery_mode="persistent",
    task_queues=tuple(
        Queue(queue_name, scheduler_exchange, routing_key=queue_name, durable=True)
        for queue_name in DURABLE_QUEUES
    ),
    task_routes={
        "app.workers.tasks.run_provisioning": {
            "queue": "provisioning",
            "routing_key": "provisioning",
        },
        "app.workers.tasks.reconcile_managed_domains": {
            "queue": "domains",
            "routing_key": "domains",
        },
        "app.workers.tasks.process_whatsapp_webhook": {
            "queue": "whatsapp",
            "routing_key": "whatsapp",
        },
        "app.workers.tasks.process_due_notifications": {
            "queue": "notifications",
            "routing_key": "notifications",
        },
        "app.workers.tasks.process_all_due_notifications": {
            "queue": "notifications",
            "routing_key": "notifications",
        },
        "app.workers.tasks.dispatch_realtime_push": {
            "queue": "notifications",
            "routing_key": "notifications",
        },
        "app.workers.tasks.expire_all_confirmation_requests": {
            "queue": "notifications",
            "routing_key": "notifications",
        },
        "app.workers.tasks.run_build_job": {
            "queue": "builds",
            "routing_key": "builds",
        },
        "app.workers.agenda_report_tasks.process_all_agenda_reports": {
            "queue": "notifications",
            "routing_key": "notifications",
        },
    },
    beat_schedule={
        "notification-sweep-every-minute": {
            "task": "app.workers.tasks.process_all_due_notifications",
            "schedule": crontab(minute="*"),
        },
        "confirmation-expiry-sweep-every-minute": {
            "task": "app.workers.tasks.expire_all_confirmation_requests",
            "schedule": crontab(minute="*"),
        },
        "managed-domain-reconcile-every-ten-minutes": {
            "task": "app.workers.tasks.reconcile_managed_domains",
            "schedule": crontab(minute="*/10"),
        },
        "agenda-management-report-sweep-hourly": {
            "task": "app.workers.agenda_report_tasks.process_all_agenda_reports",
            "schedule": crontab(minute=10),
        },
    },
    timezone="America/Bahia",
    enable_utc=True,
    worker_enable_remote_control=False,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    worker_prefetch_multiplier=1,
)


def typed_task(*, name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Expose Celery's untyped decorator through a typed boundary."""
    return cast(Callable[[Callable[P, R]], Callable[P, R]], celery_app.task(name=name))
