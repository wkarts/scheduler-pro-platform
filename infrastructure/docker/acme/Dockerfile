FROM neilpang/acme.sh:3.1.0

COPY infrastructure/docker/acme/entrypoint.sh /usr/local/bin/scheduler-acme-entrypoint
RUN chmod 0755 /usr/local/bin/scheduler-acme-entrypoint

ENTRYPOINT ["/usr/local/bin/scheduler-acme-entrypoint"]
