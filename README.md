# Backend (Flask) - Inmobiliaria Habitat

## Requisitos

- Python 3.9+
- pip

## Instalación

```bash
cd /Users/practicas4/Desktop/PruebaCursor/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecutar

```bash
export FLASK_APP=app.py
python app.py
```

La API escuchará en `http://127.0.0.1:5000`.

## Endpoints

- `GET /health` → estado del servidor
- `POST /api/contact` → guarda un contacto en `data/info_formulario.json`
- `GET /api/contacts` → lista los contactos (para pruebas)

Los datos se guardan en `backend/data/info_formulario.json`.


