FROM python:3.12-slim

WORKDIR /app

# Copy everything needed
COPY backend/auth-service/ /app/auth/
COPY backend/shared/ /app/shared/
COPY backend/__init__.py /app/

ENV PYTHONPATH=/app

# Install dependencies
COPY backend/auth-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Debug: Check files
RUN ls -la /app/auth/

CMD ["python", "-m", "uvicorn", "auth.main:app", "--host", "0.0.0.0", "--port", "8000"]