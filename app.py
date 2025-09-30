import os, json, logging
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore

logging.basicConfig(level=logging.INFO)

FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID")
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS")

if not firebase_admin._apps:
    if GOOGLE_CREDENTIALS:
        info = json.loads(GOOGLE_CREDENTIALS)
        cred = credentials.Certificate(info)
        firebase_admin.initialize_app(cred, {
            "projectId": FIREBASE_PROJECT_ID or info.get("project_id")
        })
        logging.info("Firebase initialized with service account env; project=%s",
                     FIREBASE_PROJECT_ID or info.get("project_id"))
    else:
        firebase_admin.initialize_app()
        logging.info("Firebase initialized with ADC/default credentials")

db = firestore.client()

def _effective_project_id() -> str:
    try:
        app = firebase_admin.get_app()
        proj = getattr(app, "project_id", None) or app.options.get("projectId")
    except Exception:
        proj = None
    return proj or FIREBASE_PROJECT_ID or ""

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "https://habitat-proyecto.web.app"}})

@app.get("/")
def root():
    return "OK - backend vivo", 200

@app.get("/debug")
def debug_plain():
    return {"env_project": FIREBASE_PROJECT_ID, "client_project": _effective_project_id()}, 200

@app.get("/api/health")
def api_health():
    return jsonify(ok=True), 200

@app.get("/api/debug")
def api_debug():
    return jsonify(env_project=FIREBASE_PROJECT_ID, client_project=_effective_project_id()), 200

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

    rec = {
        "name": str(data.get("name", "")).strip(),
        "email": str(data.get("email", "")).strip(),
        "phone": str(data.get("phone", "")).strip(),
        "type": str(data.get("type", "")).strip(),
        "message": str(data.get("message", "")).strip(),
        "consent": bool(data.get("consent", False)),
        "submittedAt": data.get("submittedAt") or datetime.utcnow(),
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        "ua": request.headers.get("User-Agent", "")
    }
    try:
        db.collection("contactos").add(rec)
    except Exception as exc:
        logging.exception("Firestore write failed")
        return jsonify(error="Failed to persist data", details=str(exc)), 500
    return jsonify(ok=True), 201

@app.get("/api/contacts")
def list_contacts():
    try:
        q = db.collection("contactos").order_by("submittedAt", direction=firestore.Query.DESCENDING)
        docs = q.stream()
        out = []
        for d in docs:
            o = d.to_dict()
            o["id"] = d.id
            # serializa datetime/Timestamp
            v = o.get("submittedAt")
            try:
                if hasattr(v, "to_datetime"):
                    o["submittedAt"] = v.to_datetime().isoformat() + "Z"
                elif isinstance(v, datetime):
                    o["submittedAt"] = v.isoformat() + "Z"
            except Exception:
                pass
            out.append(o)
        return jsonify(out), 200
    except Exception as exc:
        logging.exception("Firestore read failed")
        return jsonify(error="Failed to retrieve data", details=str(exc)), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
