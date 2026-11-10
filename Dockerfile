# One image for the Python services: api, ingest, seed, retention and simulator (docker-compose.yml).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv
COPY requirements-service.txt .
RUN pip install -r requirements-service.txt

# Run as an ordinary user, never root
RUN useradd --create-home --uid 10001 smartvitals
COPY src ./src
COPY simulator ./simulator
COPY app ./app
COPY models/model_v2.joblib models/model_v2.json ./models/
USER smartvitals

EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
