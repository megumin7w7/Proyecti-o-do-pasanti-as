FROM python:3.11-slim

# 1. Instalar dependencias del sistema (Chrome, librerías gráficas headless)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    chromium \
    chromium-driver \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# 2. Establecer variables de entorno para Playwright y Selenium
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV HEADLESS_MODE=True

# 3. Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Instalar navegadores de Playwright (Chromium)
RUN playwright install chromium
RUN playwright install-deps chromium

# 5. Copiar el código del proyecto
WORKDIR /app
COPY . .

# 6. Crear directorio de logs y config vacío (para evitar errores si no existen)
RUN mkdir -p /app/logs /app/config

# 7. Exponer el puerto que Streamlit usa en Hugging Face
EXPOSE 7860

# 8. Comando de inicio
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]