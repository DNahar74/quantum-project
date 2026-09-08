FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY backtest_orchestrator/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared_contracts/ /app/shared_contracts/
COPY data_loader/ /app/data_loader/
COPY results_store/ /app/results_store/
COPY backtest_orchestrator/ /app/backtest_orchestrator/

RUN chown -R appuser:appuser /app

USER appuser

# Orchestrator is meant to be run as a one-shot command
CMD ["python", "backtest_orchestrator/orchestrator.py"]
