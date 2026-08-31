ARG PYTHON_BASE_IMAGE=ghcr.io/wkarts/scheduler-pro-platform/python-base:latest
FROM ${PYTHON_BASE_IMAGE}

ARG APP_VERSION=2.1.0
ARG APP_RELEASE_TAG=
ARG APP_BUILD_SHA=
ENV APP_VERSION=${APP_VERSION} APP_RELEASE_TAG=${APP_RELEASE_TAG} APP_BUILD_SHA=${APP_BUILD_SHA}

LABEL org.opencontainers.image.title="Scheduler Pro Worker"
LABEL org.opencontainers.image.source="https://github.com/wkarts/scheduler-pro-platform"

WORKDIR /app

COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY --chown=scheduler:scheduler apps/api /app

USER scheduler
CMD ["celery", "-A", "app.workers.celery_app.celery_app", "worker", "-Q", "default,provisioning,whatsapp,notifications,domains,builds,webhooks", "--loglevel=INFO"]
