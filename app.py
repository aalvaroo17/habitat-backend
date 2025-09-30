import os, json, logging
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- Firestore via Firebase Admin SDK (soporta Render + Cloud Run) ---
import firebase_admin
from firebase_admin import credentials, firestore

logging.basicConfig(level=logging.INFO)

# Si estamos en Render: usamos la variable de entorno GOOGLE_CREDENTIALS (contenido JSON)
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS")
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID")  # opcional, útil para debug

if not firebase_admin._apps:
    if GOOGLE_CREDENTIALS:
        info = json.loads(GOOGLE_CREDENTIALS)
        cred = credentials.Certificate(info)
        firebase_admin.initialize_app(cred, {"projectId": FIREBASE_PROJECT_ID or info.get("project_id")})
        logging.info("Firebase initialized with service account from env; project=%s",
                     FIREBASE_PROJECT_ID or info.get("project_id"))
    else:
        # Cloud Run / ADC
        firebase_admin.initialize_app()
        logging.info("Firebase initialized with ADC (default credentials)")

db = firestore.client()
logging.info("Firestore client project: %s", getattr(db._client_info, "project", None) or FIREBASE_PROJECT_ID)

# ----------------------
# App Flask
# ----------------------
app = Flask(__name__)

# CORS: permite llamadas desde tu Hosting de Firebase
CORS(app, resources={r"/api/*": {"origins": "https://habitat-proyecto.web.app"}})

# ----------------------
# Health check
# ----------------------
@app.get("/api/health")
def api_health():
    return jsonify(ok=True), 200

# Debug (para verificar proyecto/credenciales rápidamente)
@app.get("/api/debug")
def api_debug():
    try:
        proj = getattr(db._client_info, "project", None) or FIREBASE_PROJECT_ID
    except Exception:
        proj = FIREBASE_PROJECT_ID
    return jsonify(
        env_project=FIREBASE_PROJECT_ID,
        client_project=proj
    ), 200

# ----------------------
# Crear contacto
# ----------------------
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
        # Firestore acepta datetime -> Timestamp
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

# ----------------------
# Listar contactos
# ----------------------
@app.get("/api/contacts")
def list_contacts():
    try:
        # Orden por fecha si existe
        q = db.collection("contactos").order_by("submittedAt", direction=firestore.Query.DESCENDING)
        docs = q.stream()
        out = []
        for d in docs:
            o = d.to_dict()
            o["id"] = d.id
            # serializa submittedAt si es Timestamp
            if isinstance(o.get("submittedAt"), datetime):
                o["submittedAt"] = o["submittedAt"].isoformat() + "Z"
            out.append(o)
        return jsonify(out), 200
    except Exception as exc:
        logging.exception("Firestore read failed")
        return jsonify(error="Failed to retrieve data", details=str(exc)), 500

# ----------------------
# Run local
# ----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
