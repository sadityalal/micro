FROM python:3.11-slim

WORKDIR /app

# Copy and install requirements
COPY auth-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared code
COPY shared/ ./shared/

# Copy auth service code
COPY auth-service/app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]