# Una sola imagen con el código de los cuatro servicios; docker-compose
# arranca cada uno con su propio comando, red y secretos. Las llaves NO van
# dentro de la imagen (.dockerignore excluye secrets/): se montan solo en
# el contenedor que las necesita.
FROM python:3.11-slim

WORKDIR /app

# Lab. 06 (SCA / Trivy): la imagen base trae paquetes del sistema y de
# Python con CVE ya corregidos (zlib1g, wheel, jaraco.context, setuptools).
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip "setuptools>=84.1.0" "wheel>=0.46.2" "jaraco.context>=6.1.0"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m spacy download es_core_news_md

COPY . .

# Entrena el chatbot Andi dentro de la imagen (el modelo guardián ya viene
# entrenado en models/guardian_ner; se puede reentrenar con
# `python -m scripts.train_guardian`).
RUN python -m scripts.train_bot \
    && useradd --create-home appuser \
    && mkdir -p /app/logs /app/data/db \
    && chown -R appuser /app/logs /app/data /app/models

USER appuser

EXPOSE 8000 8101 8102 8103

# Lab. 06 (Trivy DS-0026). Cada servicio expone /health en su puerto
# (variable PORT; 8000 por defecto, la tienda).
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'), timeout=4)"
