FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --upgrade pip uv

COPY pyproject.toml README.md ./
COPY main.py config.py ./ 
COPY docker/ ./docker/

RUN uv pip install --system --no-cache-dir -e .

COPY . .

CMD ["python", "main.py"]
