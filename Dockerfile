# Use the official lightweight Python image.
# Cache bust: 2026-01-07T13:50
FROM python:3.10-slim

# Allow statements and log messages to immediately appear
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
WORKDIR /app
COPY . ./

# Install production dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Run with gunicorn for production
# Use shell form to properly expand $PORT
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 2 --timeout 120 app:app
