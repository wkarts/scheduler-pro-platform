FROM alpine:3.22

RUN apk add --no-cache bash coreutils findutils python3

COPY infrastructure/docker/cloudpanel-agent/entrypoint.sh /usr/local/bin/scheduler-cloudpanel-agent
RUN chmod 0755 /usr/local/bin/scheduler-cloudpanel-agent

ENTRYPOINT ["/usr/local/bin/scheduler-cloudpanel-agent"]
