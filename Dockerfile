# Use the official lightweight Python image.
FROM python:3.10-slim

# Allow statements and log messages to immediately appear
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
WORKDIR /app
COPY . ./

# Install production dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# Railway sets PORT dynamically, so we use shell form to read the variable
CMD functions-framework --target=process_chat_message --port=${PORT:-8080}
