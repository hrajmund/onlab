import json
import os
import collections
import requests
import time
import base64
import base58
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from arpeggio import *
from arpeggio import RegExMatch as _
from flask import Flask, request, render_template_string, redirect, jsonify

app = Flask(__name__)
LOG_FILE = "log.json"
webhook_logs = []

def redirect_with_alert(message: str, target: str = "/"):
    return f"""
        <script>
            alert("{message}");
            window.location.href = "{target}";
        </script>
    """
@app.route("/connect_john_jane", methods=["POST"])
def connect_john_jane():
    response = requests.post("http://john:8031/out-of-band/create-invitation", json={
        "handshake_protocols": ["https://didcomm.org/didexchange/1.0"],
        "use_public_did": False
    })
    invitation = response.json()["invitation"]

    requests.post("http://jane:8032/out-of-band/receive-invitation", json=invitation)

    return redirect_with_alert("Created invitation between John and Jane!")

@app.route('/webhooks/topic/<topic>/', methods=['POST'])
def webhook(topic):
    data = request.get_json()
    log_entry = {"topic": topic, "data": data}
    webhook_logs.append(log_entry)

    with open(LOG_FILE, "w") as f:
        json.dump(webhook_logs, f, indent=2)

    print(f"Webhook received: {topic}", flush=True)
    return "ok", 200

@app.route("/create_cheqd_did_john", methods=["POST"])
def create_cheqd_did_john():
    response = requests.post("http://john:8030/wallet/did/create", json={
        "method": "cheqd",
        "options": {
            "network": "testnet"
        }
    })
    result = response.json()["result"]
    did = result["did"]
    verkey = result["verkey"]
    return redirect_with_alert(f"John cheqd DID created: {did} with verkey: {verkey}")

@app.route('/')
def index():
    html = """
    <h1>Controller is running!</h1>
    <h2>Actions</h2>

    <form action="/connect_john_jane" method="post">
        <button type="submit">John -> Jane: Create Connection</button>
    </form>

    <form action="/create_cheqd_did_john" method="post">
        <button type="submit">RegDID</button>
    </form>
    <hr>
    """
    return render_template_string(html, logs=webhook_logs)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8051, debug=True)