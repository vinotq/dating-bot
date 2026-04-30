FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py load_generator.py run_tests.py ./

CMD ["python", "run_tests.py"]
