FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TROLLEY_CONFIG_FILE=/etc/trolley/trolley.yaml

COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels trolley \
    && rm -rf /wheels \
    && groupadd --gid 10001 trolley \
    && useradd --uid 10001 --gid trolley --no-create-home --shell /usr/sbin/nologin trolley \
    && mkdir -p /data/exports /etc/trolley \
    && chown -R trolley:trolley /data \
    && chmod 0700 /data /data/exports

WORKDIR /data
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]
ENTRYPOINT ["trolley"]
