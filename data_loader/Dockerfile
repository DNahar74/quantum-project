FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY data_loader/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY data_loader/ /app/data_loader/
COPY 12_Industry_Portfolios_Daily.csv /app/12_Industry_Portfolios_Daily.csv
COPY shared_contracts/ /app/shared_contracts/

RUN chown -R appuser:appuser /app

USER appuser

CMD ["python", "-m", "data_loader.build_tidy_returns"]
