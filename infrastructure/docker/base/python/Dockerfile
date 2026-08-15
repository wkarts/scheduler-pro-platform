FROM python:3.13-slim

LABEL org.opencontainers.image.title="Scheduler Pro Python Base"
LABEL org.opencontainers.image.description="Base image with Python 3.13 and native dependencies for Scheduler Pro API and workers"
LABEL org.opencontainers.image.source="https://github.com/wkarts/scheduler-pro-platform"
LABEL org.opencontainers.image.licenses="Proprietary"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      curl \
      libpq-dev \
      netcat-openbsd \
      tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin --uid 10001 scheduler

WORKDIR /app
