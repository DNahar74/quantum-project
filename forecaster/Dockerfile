FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY forecaster/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY forecaster/ /app/forecaster/

RUN chown -R appuser:appuser /app

USER appuser

# One-shot job: reads data/processed/daily_returns.csv, writes data/processed/mu_hat.csv
CMD ["python", "-m", "forecaster.build_mu_hat"]
