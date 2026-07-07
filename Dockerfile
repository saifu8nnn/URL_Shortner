FROM python:3.12-slim

WORKDIR /app

COPY requirement.txt .
RUN pip install --no-cache-dir -r requirement.txt

COPY . .

CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT