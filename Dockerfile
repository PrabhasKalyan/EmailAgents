FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    OUTREACH_DB_PATH=/data/outreach.db

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY config.py main.py prabhas_context.md FilteredData.csv ./
COPY db ./db
COPY modules ./modules
COPY cron ./cron
COPY dashboard ./dashboard
COPY scripts ./scripts

RUN mkdir -p /data

CMD ["python", "main.py"]
