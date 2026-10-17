# Una sola imagen con el código de los cuatro servicios; docker-compose
# arranca cada uno con su propio comando, red y secretos. Las llaves NO van
# dentro de la imagen (.dockerignore excluye secrets/): se montan solo en
# el contenedor que las necesita.
FROM python:3.11-slim

WORKDIR /app

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
