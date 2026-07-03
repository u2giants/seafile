FROM flrnnc/seafile-client:latest

USER root
RUN apt-get update && \
    apt-get install --no-install-recommends --yes tini && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY --chmod=755 entrypoint.py /home/seafile/entrypoint.py
COPY --chmod=755 seaf-entrypoint.py /home/seafile/seaf-entrypoint.py

ENTRYPOINT ["/usr/bin/tini", "--", "/home/seafile/entrypoint.py"]
HEALTHCHECK --interval=60s --timeout=10s --start-period=60s --retries=3 \
    CMD ["/usr/bin/python3", "/home/seafile/entrypoint.py", "--healthcheck"]
