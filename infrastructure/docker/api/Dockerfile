ARG PYTHON_BASE_IMAGE=ghcr.io/wkarts/scheduler-pro-platform/python-base:latest
FROM ${PYTHON_BASE_IMAGE}

ARG APP_VERSION=2.0.0
ARG APP_RELEASE_TAG=
ARG APP_BUILD_SHA=
ENV APP_VERSION=${APP_VERSION} APP_RELEASE_TAG=${APP_RELEASE_TAG} APP_BUILD_SHA=${APP_BUILD_SHA}

LABEL org.opencontainers.image.title="Scheduler Pro API"
LABEL org.opencontainers.image.source="https://github.com/wkarts/scheduler-pro-platform"

WORKDIR /app

COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY --chown=scheduler:scheduler apps/api /app

USER scheduler
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD curl -fsS http://127.0.0.1:8000/api/v1/health/live || exit 1
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
