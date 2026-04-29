# Playwright's official Python image ships Chromium + all OS deps preinstalled.
# Pinned by major.minor — bump deliberately so a sudden Chromium revision can't
# break a working refresh in the middle of the night.
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

# `redis` is the only extra runtime dep — Playwright is already in the base.
# `tini` so a SIGTERM from `docker compose down` actually stops the long sleep
# in the entrypoint loop instead of waiting for the 10s grace timeout.
RUN pip install --no-cache-dir 'redis>=5.0,<6' \
    && apt-get update && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

COPY refresh.py /app/refresh.py

# Run as root inside this container: it needs to write to a host-mounted
# cookies.txt that's typically owned by root on the VPS, and the container is
# isolated to a single trusted task (visiting youtube.com to keep the session
# warm). No untrusted input is accepted. The Playwright base image normally
# runs as `pwuser`; override that here so the cookies write doesn't EACCES.
USER root

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "/app/refresh.py"]
