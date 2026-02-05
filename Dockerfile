FROM selenium/standalone-chrome:latest

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Switch to root for package installation
USER root

# Install minimal system deps and Python (selenium base image doesn't include Python)
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    python3 \
    python3-venv \
    python3-distutils \
    python3-pip \
  && rm -rf /var/lib/apt/lists/*

# Make `python` and `pip` point to python3/pip3
RUN ln -sf /usr/bin/python3 /usr/bin/python || true && ln -sf /usr/bin/pip3 /usr/bin/pip || true

# Ensure chromedriver is available on PATH at a standard location
RUN if [ -f /usr/bin/chromedriver ]; then \
      ln -sf /usr/bin/chromedriver /usr/local/bin/chromedriver; \
    elif [ -f /usr/lib/chromium/chromedriver ]; then \
      ln -sf /usr/lib/chromium/chromedriver /usr/local/bin/chromedriver; \
    elif [ -f /usr/lib/chromium-browser/chromedriver ]; then \
      ln -sf /usr/lib/chromium-browser/chromedriver /usr/local/bin/chromedriver; \
    fi || true

WORKDIR /app

# Copiar e instalar dependencias primero (cacheable)
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r /app/requirements.txt

# Copiar código de la app
COPY . /app

# Ensure files in /app are accessible to the selenium non-root user
RUN chown -R seluser:seluser /app || true

# A script that will download a compatible chromedriver at container start
# using webdriver-manager, then start the FastAPI server.
# This avoids mismatches between system chromedriver and Chromium in the image.

# Indicar ruta del binario de Chromium dentro del contenedor (selenium image usa /usr/bin/google-chrome)
ENV CHROME_BIN=/usr/bin/google-chrome

EXPOSE 8000

# Ensure the start script is executable and use it as entrypoint
RUN chmod +x /app/start.sh || true

# Switch back to the default non-root selenium user
USER seluser

# Render establece $PORT; usar fallback
CMD ["sh", "-c", "/app/start.sh"]

# Expose Selenium port for optional remote control (not strictly necessary)
EXPOSE 4444
