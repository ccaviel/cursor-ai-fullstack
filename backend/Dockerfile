FROM python:3.11-slim

WORKDIR /app

# Install git, curl and other dependencies
RUN apt-get update && \
    apt-get install -y git curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Add requests to requirements for health checks
RUN pip install requests

CMD ["python", "app.py"] 