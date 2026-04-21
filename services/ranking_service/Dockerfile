FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src /app/src

CMD ["sh", "-c", "python -m src.migrate && uvicorn src.main:app --host 0.0.0.0 --port 8000"]
