from app.workers.celery_app import typed_task


@typed_task(name="app.workers.tasks.run_provisioning")
def run_provisioning(job_id: str, tenant_id: str, correlation_id: str) -> dict[str, object]:
    return {"job_id": job_id, "tenant_id": tenant_id, "correlation_id": correlation_id, "queued": True}


@typed_task(name="app.workers.tasks.process_whatsapp_webhook")
def process_whatsapp_webhook(tenant_id: str, event_id: str, correlation_id: str) -> dict[str, object]:
    return {"tenant_id": tenant_id, "event_id": event_id, "correlation_id": correlation_id, "processed": True}


@typed_task(name="app.workers.tasks.process_due_notifications")
def process_due_notifications(tenant_id: str, correlation_id: str) -> dict[str, object]:
    # The API endpoint /notifications/process-due executes the transactional path.
    # This task is intentionally small until tenant-aware worker session routing is promoted.
    return {"tenant_id": tenant_id, "correlation_id": correlation_id, "queued": True}


@typed_task(name="app.workers.tasks.run_build_job")
def run_build_job(job_id: str, tenant_id: str, target: str, correlation_id: str) -> dict[str, object]:
    return {"job_id": job_id, "tenant_id": tenant_id, "target": target, "correlation_id": correlation_id, "queued": True}
