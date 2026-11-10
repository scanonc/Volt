FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --uid 10001 --create-home appuser && \
    mkdir -p /data && \
    chown -R appuser:appuser /app /data

USER appuser

EXPOSE 5001

CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "app:create_app()"]
