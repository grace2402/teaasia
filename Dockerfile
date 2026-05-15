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

# Patch flask_uploads for Werkzeug 2.x compatibility
RUN python3 -c "p='/usr/local/lib/python3.9/site-packages/flask_uploads.py';d=open(p).read();open(p,'w').write(d.replace('from werkzeug import secure_filename, FileStorage','from werkzeug.datastructures import FileStorage\nfrom werkzeug.utils import secure_filename'))"

COPY . .

RUN mkdir -p uploads taipower_replies

# 預設使用 gunicorn via wrapper
CMD ["bash", "/app/wrapper.sh"]
