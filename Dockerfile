FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir '.[dev]' && python -m scripts.generate_data --count 60
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "evidencedoc.app:app", "--host", "0.0.0.0", "--port", "8000"]
