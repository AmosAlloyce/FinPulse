FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

RUN useradd --create-home --uid 10001 finpulse
USER finpulse

FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "finpulse.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS producer
CMD ["finpulse-producer"]

FROM base AS dashboard
USER root
RUN pip install '.[dashboard]'
USER finpulse
EXPOSE 8501
CMD ["streamlit", "run", "src/finpulse/dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
