FROM python:3.14.7-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN python -m pip install --no-cache-dir pip==26.2.1

COPY requirements.lock ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock

COPY . ./

RUN useradd --create-home --uid 10001 app \
    && chmod +x docker/entrypoint.sh \
    && mkdir -p staticfiles \
    && chown -R app:app /app

USER app

ENTRYPOINT ["docker/entrypoint.sh"]
