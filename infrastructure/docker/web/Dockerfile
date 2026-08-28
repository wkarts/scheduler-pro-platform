ARG NODE_IMAGE=node:22-alpine
ARG NGINX_IMAGE=nginx:1.27-alpine
ARG APP_DIR=apps/web

FROM ${NODE_IMAGE} AS build
ARG APP_DIR
WORKDIR /workspace

COPY package.json ./package.json
COPY apps/web/package.json apps/web/package.json
COPY apps/admin/package.json apps/admin/package.json
COPY apps/desktop/package.json apps/desktop/package.json
COPY apps/mobile/package.json apps/mobile/package.json
COPY packages/api-client/package.json packages/api-client/package.json
COPY packages/types/package.json packages/types/package.json
COPY packages/visual-builder/package.json packages/visual-builder/package.json
COPY packages/visual-builder/scripts packages/visual-builder/scripts
COPY packages/visual-builder/release-b64 packages/visual-builder/release-b64

RUN npm install

COPY ${APP_DIR} ${APP_DIR}
COPY packages packages
RUN npm --workspace ${APP_DIR} run build

FROM ${NGINX_IMAGE} AS runtime
ARG APP_DIR
COPY infrastructure/docker/web/nginx-spa.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/${APP_DIR}/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
