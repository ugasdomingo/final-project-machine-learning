# Hotel Overbooking API

Proyecto final de Machine Learning (4Geeks bootcamp).

API que estima la **probabilidad de cancelación** de cada reserva y calcula el **% de overbooking recomendado** por sede (hotel, posada o propiedad), pensado para gestionar listas de espera sin quedarse con habitaciones vacías.

## Estructura del repositorio

- `App/`: la API FastAPI en producción (predicciones, overbooking, dashboard web).
- `Model/`: el procedimiento de entrenamiento del modelo (`src/explore.ipynb`) y los artefactos entrenados (`models/`).
- `alembic/`: migraciones de la base de datos.

## Cómo funciona

1. **Registro** (`POST /accounts`): una empresa se registra con su primera sede y recibe una API key. Una cuenta puede tener varias sedes (`POST /sedes`), cada una con su nº de habitaciones y su perfil (país habitual de clientes, régimen, depósito, tarifa media).
2. **Predicción simple** (`POST /predictions/simple`): se envían solo los datos que un recepcionista conoce (fechas, huéspedes, canal de venta, precio). La API deriva el resto de las 26 variables del modelo a partir de las fechas y del perfil de la sede, y devuelve el % de cancelación con una etiqueta de riesgo (bajo/medio/alto).
3. **Predicción avanzada** (`POST /predictions`): para integraciones (PMS) que disponen de las 26 variables completas.
4. **Overbooking** (`POST /overbooking/from-predictions`): con las reservas de una fecha ya registradas, calcula cuántas reservas extra puede aceptar la sede para esa fecha con un riesgo elegido de sobrevender. También existe `POST /overbooking` para enviar un lote completo de reservas.

Todas las peticiones autenticadas usan el header `X-API-Key`. La documentación interactiva está en `/docs` y el panel web en `/` y `/dashboard`.

## Ejecutar en local

```bash
pip install -r requirements.txt
alembic upgrade head          # crea las tablas (SQLite ./app.db por defecto)
uvicorn App.main:app --reload
```

Abre http://127.0.0.1:8000 para registrarte y usar el dashboard.

## Desplegar en Railway

1. Sube el repositorio a GitHub.
2. En [Railway](https://railway.app): **New Project → Deploy from GitHub repo** y elige este repo. Railway detecta el `Dockerfile` automáticamente (ver `railway.json`).
3. Añade una base de datos: **Create → Database → PostgreSQL** en el mismo proyecto.
4. En el servicio de la API → **Variables → New Variable → Add Reference** y selecciona `DATABASE_URL` del servicio Postgres. (El código normaliza el prefijo `postgres://` automáticamente.)
5. En **Settings → Networking → Generate Domain** para obtener la URL pública.

En cada despliegue el contenedor ejecuta `alembic upgrade head` antes de arrancar, así el esquema de la base de datos se mantiene al día. El healthcheck apunta a `/health`.

## Modelo

Random Forest calibrado entrenado sobre el dataset *Hotel Booking Demand* (~119k reservas). Métricas en test: ROC-AUC 0.929, accuracy 0.853, Brier 0.102 (ver `Model/models/model_metadata.json`). El cálculo de overbooking usa la aproximación normal a la Poisson-binomial sobre las probabilidades individuales de cancelación (derivación en `Model/src/explore.ipynb`).
