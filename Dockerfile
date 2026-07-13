FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY Model/models ./Model/models
COPY App ./App

EXPOSE 8000

# Railway inyecta PORT; en local se usa 8000.
CMD alembic upgrade head && uvicorn App.main:app --host 0.0.0.0 --port ${PORT:-8000}
