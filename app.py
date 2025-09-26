import json
import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS


def ensure_data_folder(path: str) -> None:
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)


DATA_FILE = os.path.join(os.path.dirname(__file__), 'data', 'info_formulario.json')
ensure_data_folder(DATA_FILE)
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)


app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:*", "http://127.0.0.1:*"]}})


@app.get('/health')
def health() -> tuple:
    return jsonify({"status": "ok"}), 200


@app.post('/api/contact')
def post_contact() -> tuple:
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    if not isinstance(data, dict):
        return jsonify({"error": "Payload must be an object"}), 400

    required_fields = ["name", "email", "type", "consent"]
    missing = [k for k in required_fields if not data.get(k)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    record = {
        "name": str(data.get("name", "")).strip(),
        "email": str(data.get("email", "")).strip(),
        "phone": str(data.get("phone", "")).strip(),
        "type": str(data.get("type", "")).strip(),
        "message": str(data.get("message", "")).strip(),
        "consent": bool(data.get("consent", False)),
        "submittedAt": data.get("submittedAt") or datetime.utcnow().isoformat() + "Z",
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        "ua": request.headers.get("User-Agent", "")
    }

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            current = json.load(f)
        if not isinstance(current, list):
            current = []
        current.append(record)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        return jsonify({"error": "Failed to persist data", "details": str(exc)}), 500

    return jsonify({"ok": True}), 201


@app.get('/api/contacts')
def list_contacts() -> tuple:
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            current = json.load(f)
        if not isinstance(current, list):
            current = []
    except Exception:
        current = []
    return jsonify(current), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=True)


