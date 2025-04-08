import time
import uuid
import json
import os
import requests
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)

AGENTS = {
    "john": {"endpoint": "http://john:8031"},
    "jane": {"endpoint": "http://jane:8032"},
    "james": {"endpoint": "http://james:8033"},
}

SCHEMA_ID = "Th7MpTaRZVRYnPiabds81Y:2:DummySchema:1.0"
CRED_DEF_IDS = {
    "john": "Th7MpTaRZVRYnPiabds81Y:3:CL:12345:john",
    "jane": "Th7MpTaRZVRYnPiabds81Y:3:CL:12346:jane",
}

VDR_FILE = "vdr.json"

def redirect_with_alert(message, target="/"):
    return render_template_string(f"""
        <script>alert(\"{message}\"); window.location.href=\"{target}\";</script>
    """)

def save_connection_to_vdr(sender, receiver, connection_id):
    vdr = {}
    if os.path.exists(VDR_FILE):
        with open(VDR_FILE, "r") as f:
            try:
                vdr = json.load(f)
            except json.JSONDecodeError:
                vdr = {}

    key = f"{sender}->{receiver}"
    vdr[key] = {
        "connection_id": connection_id,
        "timestamp": time.time()
    }

    with open(VDR_FILE, "w") as f:
        json.dump(vdr, f, indent=2)

@app.route("/")
def index():
    return render_template_string("""
        <h1>ACA-Py Dummy Controller</h1>
        <form action="/init_schema" method="post"><button>Init Dummy Schema</button></form>
        <form action="/issue_credential" method="post">
            <label>From:</label>
            <select name="sender">
                <option>john</option>
                <option>jane</option>
            </select>
            <label>To:</label>
            <select name="receiver">
                <option>jane</option>
                <option>john</option>
            </select>
            <button>Issue Credential</button>
        </form>
    """)

@app.route("/init_schema", methods=["POST"])
def init_schema():
    return redirect_with_alert("Dummy schema és cred def beállítva!")

@app.route("/issue_credential", methods=["POST"])
def issue_credential():
    sender = request.form["sender"]
    receiver = request.form["receiver"]

    sender_ep = AGENTS[sender]["endpoint"]
    receiver_ep = AGENTS[receiver]["endpoint"]

    # Create invitation
    inv = requests.post(f"{receiver_ep}/connections/create-invitation").json()
    invitation = inv["invitation"]
    receiver_conn_id = inv["connection_id"]

    # Accept invitation
    accept = requests.post(f"{sender_ep}/connections/receive-invitation", json=invitation).json()
    sender_conn_id = accept["connection_id"]

    # Wait until connection is active
    for _ in range(10):
        state = requests.get(f"{sender_ep}/connections/{sender_conn_id}").json()["state"]
        if state == "active":
            save_connection_to_vdr(sender, receiver, sender_conn_id)
            break
        time.sleep(1)
    else:
        return redirect_with_alert("Hiba: kapcsolat nem jött létre.")

    # Dummy credential offer
    offer = {
        "connection_id": sender_conn_id,
        "filter": {
            "indy": {
                "cred_def_id": CRED_DEF_IDS[sender]
            }
        },
        "credential_preview": {
            "@type": "issue-credential/2.0/credential-preview",
            "attributes": [
                {"name": "name", "value": "Test User"},
                {"name": "email", "value": "test@example.com"},
            ]
        }
    }

    r = requests.post(f"{sender_ep}/issue-credential-2.0/send-offer", json=offer)
    if r.status_code != 200:
        return redirect_with_alert(f"VC küldés sikertelen: {r.text}")
    
    update_vdr({
        "connection_id": sender_conn_id,
        "issuer": sender,
        "holder": receiver,
        "timestamp": time.time()
    })

    return redirect_with_alert(f"VC sikeresen elküldve {sender} → {receiver}.")

@app.route("/webhooks/topic/<topic>/", methods=["POST"])
def webhook(topic):
    data = request.json
    print(f"[WEBHOOK] Topic: {topic}\n{data}")

    # Optionally record when the connection reaches active state
    if topic == "connections" and data.get("state") == "active":
        their_label = data.get("their_label") or data.get("their_did")
        my_label = data.get("my_label") or "unknown"
        connection_id = data.get("connection_id")
        if their_label and my_label:
            save_connection_to_vdr(their_label.lower(), my_label.lower(), connection_id)

    return "", 200

def update_vdr(entry):
    if os.path.exists(VDR_FILE):
        with open(VDR_FILE, "r") as f:
            try:
                vdr_data = json.load(f)
            except json.JSONDecodeError:
                vdr_data = []
    else:
        vdr_data = []

    vdr_data.append(entry)

    with open(VDR_FILE, "w") as f:
        json.dump(vdr_data, f, indent=2)

@app.route("/vdr", methods=["GET"])
def get_vdr():
    if not os.path.exists(VDR_FILE):
        return {"error": "VDR not found"}, 404
    with open(VDR_FILE, "r") as f:
        try:
            data = json.load(f)
            return data
        except json.JSONDecodeError:
            return {"error": "Invalid VDR file"}, 500
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8051, debug=True)