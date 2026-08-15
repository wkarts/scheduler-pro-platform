ARG NGINX_IMAGE=nginx:1.27-alpine
FROM ${NGINX_IMAGE}
LABEL org.opencontainers.image.title="Scheduler Pro Proxy"
LABEL org.opencontainers.image.source="https://github.com/wkarts/scheduler-pro-platform"
COPY infrastructure/docker/proxy/default.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD wget -qO- http://127.0.0.1/api/v1/health/live >/dev/null || exit 1
