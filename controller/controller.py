import time
import json
import os
import requests
from flask import Flask, render_template_string, request, redirect

app = Flask(__name__)

AGENTS = {
    "john": {"endpoint": "http://john:8031"},
    "jane": {"endpoint": "http://jane:8032"},
    "james": {"endpoint": "http://james:8033"},
}

SCHEMA_ID = "Th7MpTaRZVRYnPiabds81Y:2:DummySchema:1.0"
CRED_DEF_IDS = {
    "john": "Th7MpTaRZVRYnPiabds81Y:3:CL:12345:john",
}

VDR_FILE = "vdr.json"

def redirect_with_alert(message, target="/"):
    return render_template_string(f"""
        <script>alert(\"{message}\"); window.location.href=\"{target}\";</script>
    """)

def update_vdr(entry):
    data = []
    if os.path.exists(VDR_FILE):
        with open(VDR_FILE, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []

    data.append(entry)

    with open(VDR_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_connection_id(sender, receiver):
    if not os.path.exists(VDR_FILE):
        return None
    with open(VDR_FILE, "r") as f:
        try:
            data = json.load(f)
            for entry in data:
                if entry.get("issuer") == sender and entry.get("holder") == receiver and entry.get("type") == "connection":
                    return entry.get("connection_id")
        except json.JSONDecodeError:
            return None
    return None

@app.route("/")
def index():
    return render_template_string("""
        <h1>ACA-Py Dummy Controller</h1>

        <form action="/issue_credential" method="post">
            <h2>Issue Credential</h2>
            <input type="hidden" name="sender" value="john">
            <input type="hidden" name="receiver" value="jane">
            <button>John → Jane: Issue Credential</button>
        </form>

        <form action="/request_proof" method="post">
            <h2>Request Proof</h2>
            <input type="hidden" name="verifier" value="james">
            <input type="hidden" name="holder" value="jane">
            <button>James → Jane: Request Proof</button>
        </form>
        
        <form action="/vdr" method="get">
            <h2>View VDR</h2>
            <button>Show VDR</button>
        </form>
    """)

@app.route("/issue_credential", methods=["POST"])
def issue_credential():
    sender_ep = "http://john:8031"
    receiver_ep = "http://jane:8032"

    # Hozz létre kapcsolatot
    inv = requests.post(f"{receiver_ep}/connections/create-invitation").json()
    conn_id = inv["connection_id"]
    requests.post(f"{sender_ep}/connections/receive-invitation", json=inv["invitation"])

    # Várjuk meg, amíg aktív lesz a kapcsolat
    for _ in range(20):
        state = requests.get(f"{sender_ep}/connections/{conn_id}").json()["state"]
        if state == "active":
            break
        time.sleep(1)

    # JSON-LD credential offer küldése
    cred_offer = {
        "connection_id": conn_id,
        "filter": {
            "ld_proof": {
                "credential": {
                    "@context": ["https://www.w3.org/2018/credentials/v1"],
                    "type": ["VerifiableCredential"],
                    "issuer": "did:web:john.agent",
                    "issuanceDate": "2025-04-09T00:00:00Z",
                    "credentialSubject": {
                        "id": "did:web:jane.agent",
                        "name": "Jane Doe",
                        "degree": {
                            "type": "BachelorDegree",
                            "name": "Computer Science"
                        }
                    }
                },
                "options": {
                    "proofType": "Ed25519Signature2018"
                }
            }
        }
    }

    response = requests.post(f"{sender_ep}/issue-credential-2.0/send-offer", json=cred_offer)
    return redirect_with_alert(response.text)

@app.route("/request_proof", methods=["POST"])
def request_proof():
    verifier = request.form["verifier"]
    holder = request.form["holder"]

    verifier_ep = AGENTS[verifier]["endpoint"]

    conn_id = get_connection_id(holder, verifier)
    if not conn_id:
        return redirect_with_alert("No connection between verifier and holder.")

    proof_request = {
        "connection_id": conn_id,
        "presentation_request": {
            "indy": {
                "name": "Email Proof",
                "version": "1.0",
                "requested_attributes": {
                    "attr1_referent": {
                        "name": "email"
                    }
                },
                "requested_predicates": {}
            }
        }
    }

    r = requests.post(f"{verifier_ep}/present-proof-2.0/send-request", json=proof_request)
    if r.status_code != 200:
        return redirect_with_alert(f"Failed to send proof request: {r.text}")

    update_vdr({
        "type": "proof_request",
        "verifier": verifier,
        "holder": holder,
        "connection_id": conn_id,
        "timestamp": time.time()
    })

    return redirect_with_alert("Proof request sent successfully.")

@app.route("/vdr", methods=["GET"])
def get_vdr():
    if not os.path.exists(VDR_FILE):
        return {"error": "VDR not found"}, 404
    with open(VDR_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {"error": "Invalid VDR file"}, 500

@app.route("/webhooks/topic/<topic>/", methods=["POST"])
def webhook(topic):
    data = request.json
    print(f"[WEBHOOK] Topic: {topic}\n{json.dumps(data, indent=2)}")

    if topic == "connections" and data.get("state") == "active":
        print(f"✅ Kapcsolat aktív! ID: {data['connection_id']}")
    return "", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8051, debug=True)
