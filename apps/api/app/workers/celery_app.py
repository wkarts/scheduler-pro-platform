from celery import Celery

from app.core.config import settings

celery_app = Celery("scheduler_pro", broker=settings.celery_broker_url, backend=settings.celery_result_backend)
celery_app.conf.task_routes = {
    "app.workers.tasks.run_provisioning": {"queue": "provisioning"},
    "app.workers.tasks.process_whatsapp_webhook": {"queue": "whatsapp"},
}
