FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей для PyTorch и других библиотек
RUN apt-get update && apt-get install -y \
    libgomp1 \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV TORCH_CUDA_VERSION="none"

CMD ["python", "-m", "api_gateway.main"]