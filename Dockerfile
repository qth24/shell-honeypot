FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app

EXPOSE 7788

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7788"]
