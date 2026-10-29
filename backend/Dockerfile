FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# pg_dump and pg_restore (the backup and restore tests use them) and the time zone files.
COPY scripts/install-system-packages.sh /tmp/
RUN sh /tmp/install-system-packages.sh

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
