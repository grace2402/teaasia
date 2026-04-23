FROM python:3.9-slim-bullseye

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libcurl4-openssl-dev \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --use-deprecated=legacy-resolver -r requirements.txt

COPY . .

RUN mkdir -p uploads taipower_replies

# 預設使用 gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "wsgi:app"]
