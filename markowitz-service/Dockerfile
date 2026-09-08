FROM python:3.12-slim AS builder

WORKDIR /build

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev && rm -rf /var/lib/apt/lists/*

COPY markowitz-service/requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy wheels and install
COPY --from=builder /build/wheels /wheels
COPY markowitz-service/requirements.txt .
RUN pip install --no-cache /wheels/*

# We need both shared_contracts and markowitz_service
COPY shared_contracts/ /app/shared_contracts/
COPY markowitz-service/app/ /app/app/

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
