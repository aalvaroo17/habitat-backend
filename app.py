import os, json, logging
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# Firebase Admin / Firestore
import firebase_admin
from firebase_admin import credentials, firestore

logging.basicConfig(level=logging.INFO)

# ========= Inicialización Firebase Admin (Render o Cloud Run) =========
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID")  # p.ej. "habitat-proyecto"
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS")    # JSON completo si estás en Render

_env_json_project = None
if not firebase_admin._apps:
    if GOOGLE_CREDENTIALS:
        # Render: leemos el JSON de la variable de entorno
        info = json.loads(GOOGLE_CREDENTIALS)
        _env_json_project = info.get("project_id")
        cred = credentials.Certificate(info)
        firebase_admin.initialize_app(cred, {
            "projectId": FIREBASE_PROJECT_ID or _env_json_project
        })
        logging.info("Firebase initialized with service account (env). project=%s",
                     FIREBASE_PROJECT_ID or _env_json_project)
    else:
        # Cloud Run / local con ADC
        firebase_admin.initialize_app()
        logging.info("Firebase initialized with ADC/default credentials")

db = firestore.client()

def _effective_project_id() -> str:
    """Intenta deducir el projectId efectivo del cliente actual."""
    try:
        app = firebase_admin.get_app()
        proj = getattr(app, "project_id", None)
        if not proj:
            proj = app.options.get("projectId")
    except Exception:
        proj = None
    return proj or FIREBASE_PROJECT_ID or _env_json_project or ""

logging.info("Firestore client ready. effective_project=%s", _effective_project_id())

# ========= Flask app =========
app = Flask(__name__)

# CORS: tu dominio de Firebase Hosting (añade localhost si lo necesitas en dev)
CORS(app, resources={r"/api/*": {"origins": "https://habitat-proyecto.web.app"}})

# ---------- Health ----------
@app.get("/api/health")
def api_health():
    return jsonify(ok=True), 200

# ---------- Debug (para verificar proyecto/credenciales) ----------
@app.get("/api/debug")
def api_debug():
    return jsonify(
        env_project=FIREBASE_PROJECT_ID,
        client_project=_effective_project_id()
    ), 200

# ---------- Helpers ----------
def _serialize(value):
    """Convierte valores Firestore (Timestamp/datetime) a str ISO si hace falta."""
    try:
        # google.cloud.firestore Timestamp tiene .to_datetime()
        if hasattr(value, "to_datetime"):
            return value.to_datetime().isoformat() + "Z"
    except Exception:
        pass
    if isinstance(value, datetime):
        return value.isoformat() + "Z"
    return value

# ---------- Crear contacto ----------
@app.post("/api/contact")
def post_contact():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify(error="Invalid JSON"), 400

    if not isinstance(data, dict):
        return jsonify(error="Payload must be an object"), 400

    required = ["name", "email", "type", "consent"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        return jsonify(error=f"Missing fields: {', '.join(missing)}"), 400

    contact_data = {
        "name": str(data.get("name", "")).strip(),
        "email": str(data.get("email", "")).strip(),
        "phone": str(data.get("phone", "")).strip(),
        "type": str(data.get("type", "")).strip(),
        "message": str(data.get("message", "")).strip(),
        "consent": bool(data.get("consent", False)),
        # Firestore acepta datetime (se guarda como Timestamp)
        "submittedAt": data.get("submittedAt") or datetime.utcnow(),
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        "ua": request.headers.get("User-Agent", "")
    }

    try:
        db.collection("contactos").add(contact_data)
    except Exception as exc:
        logging.exception("Firestore write failed")
        return jsonify(error="Failed to persist data", details=str(exc)), 500

    return jsonify(ok=True), 201

# ---------- Listar contactos ----------
@app.get("/api/contacts")
def list_contacts():
    try:
        q = db.collection("contactos").order_by("submittedAt", direction=firestore.Query.DESCENDING)
        docs = q.stream()
        out = []
        for d in docs:
            o = d.to_dict()
            o["id"] = d.id
            # serializa posibles Timestamps
            for k, v in list(o.items()):
                o[k] = _serialize(v)
        return jsonify(out), 200
    except Exception as exc:
        logging.exception("Firestore read failed")
        return jsonify(error="Failed to retrieve data", details=str(exc)), 500

# ---------- Run local ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
