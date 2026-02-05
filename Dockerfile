FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema necesarias para Chromium
RUN apt-get update \
     && apt-get install -y --no-install-recommends \
         wget \
         ca-certificates \
         chromium \
         fonts-liberation \
         libnss3 \
         libxss1 \
         libasound2 \
         libatk1.0-0 \
         libatk-bridge2.0-0 \
         libx11-xcb1 \
         libxrandr2 \
         libgtk-3-0 \
     && rm -rf /var/lib/apt/lists/*

# Install a chromedriver that matches the installed Chromium at build time.
# This avoids runtime mismatches where the system chromedriver is an older version.
RUN python - <<'PY'
import subprocess, re, sys
from webdriver_manager.chrome import ChromeDriverManager
try:
    out = subprocess.check_output(['/usr/bin/chromium', '--version'], text=True)
    m = re.search(r'(\d+)\.', out)
    major = m.group(1) if m else None
except Exception:
    major = None

if major:
    try:
        # Attempt to install a chromedriver matching the major version
        path = ChromeDriverManager(version=major).install()
    except Exception:
        path = ChromeDriverManager().install()
else:
    path = ChromeDriverManager().install()

print('CHROMEDRIVER_INSTALLED_AT_BUILD:' + str(path))
PY

RUN ln -sf $(python -c "from webdriver_manager.chrome import ChromeDriverManager; print(ChromeDriverManager().install())") /usr/local/bin/chromedriver || true

WORKDIR /app

# Copiar e instalar dependencias primero (cacheable)
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r /app/requirements.txt

# Copiar código de la app
COPY . /app

# A script that will download a compatible chromedriver at container start
# using webdriver-manager, then start the FastAPI server.
# This avoids mismatches between system chromedriver and Chromium in the image.

# Indicar ruta del binario de Chromium dentro del contenedor
ENV CHROME_BIN=/usr/bin/chromium

EXPOSE 8000

# Ensure the start script is executable and use it as entrypoint
RUN chmod +x /app/start.sh || true

# Render establece $PORT; usar fallback
CMD ["sh", "-c", "/app/start.sh"]
