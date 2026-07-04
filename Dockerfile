FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Cài dependency trước (tận dụng cache layer)
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

EXPOSE 8001

# PORT/HOST đọc từ env (.env hoặc docker-compose)
CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8001}"]
