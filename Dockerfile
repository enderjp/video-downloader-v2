FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install Chromium and chromedriver plus dependencies
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libx11-xcb1 \
    libxrandr2 \
    libgtk-3-0 \
    chromium \
    chromium-driver \
  && rm -rf /var/lib/apt/lists/*

# Set binary paths
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

WORKDIR /app

# Install Python deps first
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY . /app

EXPOSE 8000

# Ensure start script executable
RUN chmod +x /app/start.sh || true

# Render establece $PORT; usar fallback
CMD ["sh", "-c", "/app/start.sh"]
