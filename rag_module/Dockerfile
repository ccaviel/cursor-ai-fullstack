FROM python:3.11-slim

WORKDIR /app

# Install git and other dependencies
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directories for repositories
RUN mkdir -p /app/repos/coderabbit-docs \
    /app/repos/browser-use \
    /app/repos/augment-vim

COPY . .

# Clone repositories during build
RUN git clone https://github.com/coderabbitai/coderabbit-docs.git /app/repos/coderabbit-docs && \
    git clone https://github.com/browser-use/browser-use.git /app/repos/browser-use && \
    git clone https://github.com/augmentcode/augment.vim.git /app/repos/augment-vim

CMD ["python", "main.py"] 