FROM python:3.11-slim

WORKDIR /app

# Copy and install requirements
COPY api-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared code
COPY shared/ ./shared/

# Copy api-gateway code
COPY api-gateway/app/ ./app/

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]