FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app

ENV APP_HOST=0.0.0.0
ENV APP_PORT=7788

EXPOSE 7788

CMD ["sh", "-c", "uvicorn main:app --host ${APP_HOST:-0.0.0.0} --port ${APP_PORT:-7788} --proxy-headers --forwarded-allow-ips='*'"]
