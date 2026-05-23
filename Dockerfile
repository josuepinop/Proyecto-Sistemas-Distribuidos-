FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY common ./common
COPY namenode ./namenode
COPY datanode ./datanode
COPY client ./client

CMD ["uvicorn", "namenode.main:app", "--host", "0.0.0.0", "--port", "8000"]
