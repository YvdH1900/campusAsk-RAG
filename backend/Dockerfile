FROM python:3.11-slim

WORKDIR /app

ARG PIP_INDEX_URL=""
ARG PIP_TRUSTED_HOST=""

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

RUN if [ -n "$PIP_INDEX_URL" ]; then \
        pip config set global.index-url "$PIP_INDEX_URL" && \
        pip config set global.trusted-host "$PIP_TRUSTED_HOST"; \
    fi

RUN pip install --no-cache-dir --upgrade "setuptools>=69.5.1,<70.0"

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
