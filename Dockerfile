# Use the official lightweight Python image.
FROM python:3.10-slim

# Allow statements and log messages to immediately appear
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
WORKDIR /app
COPY . ./

# Install production dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Run with gunicorn for production
CMD exec gunicorn --bind :${PORT:-8080} --workers 1 --threads 2 --timeout 60 main:app
