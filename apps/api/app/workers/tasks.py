from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.run_provisioning")
def run_provisioning(job_id: str, tenant_id: str, correlation_id: str) -> dict:
    return {"job_id": job_id, "tenant_id": tenant_id, "correlation_id": correlation_id, "queued": True}


@celery_app.task(name="app.workers.tasks.process_whatsapp_webhook")
def process_whatsapp_webhook(tenant_id: str, event_id: str, correlation_id: str) -> dict:
    return {"tenant_id": tenant_id, "event_id": event_id, "correlation_id": correlation_id, "processed": True}
