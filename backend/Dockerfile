FROM python:3.9-slim

WORKDIR /app

# Install required system packages including curl for healthcheck
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
ARG PORT=5001
ENV PORT=$PORT
EXPOSE $PORT

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV NODE_ID=node1

# Command to run the application
CMD ["sh", "-c", "python app.py"]