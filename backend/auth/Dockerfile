FROM python:3.13-slim

WORKDIR /app

# Install build dependencies for asyncpg
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY backend/auth/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ONLY shared module and auth service
COPY backend/shared/ ./shared/
COPY backend/auth/ ./

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]