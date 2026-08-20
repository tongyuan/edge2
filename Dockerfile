FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system edge2 && useradd --system --gid edge2 --home-dir /app edge2

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
RUN chmod +x scripts/*.sh scripts/*.py && chown -R edge2:edge2 /app

USER edge2
EXPOSE 8790

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8790/health', timeout=4)"

CMD ["./scripts/start.sh"]

FROM base AS test
USER root
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests ./tests
RUN chown -R edge2:edge2 /app
USER edge2
CMD ["python3", "-m", "unittest", "discover", "-s", "tests", "-v"]
