import json
import os
import sys
import uuid
import collections
import requests
import time
from arpeggio import * # type: ignore
from arpeggio import RegExMatch as _ # type: ignore
from flask import Flask, request, render_template_string, redirect # type: ignore

app = Flask(__name__)
LOG_FILE = "log.json"
webhook_logs = []

def wait_until_connection_active(admin_url, conn_id, timeout=10):
    for _ in range(timeout):
        conns = requests.get(f"{admin_url}/connections").json()["results"]
        conn = next((c for c in conns if c["connection_id"] == conn_id), None)
        if conn and conn["state"] == "active":
            return True
        time.sleep(1)
    return False

def redirect_with_alert(message: str, target: str = "/"):
    return f"""
        <script>
            alert(\"{message}\");
            window.location.href = \"{target}\";
        </script>
    """

def wait_until_connection_active(admin_url, conn_id, timeout=10):
    for _ in range(timeout):
        conns = requests.get(f"{admin_url}/connections").json()["results"]
        conn = next((c for c in conns if c["connection_id"] == conn_id), None)
        if conn and conn["state"] == "active":
            return True
        time.sleep(1)
    return False

@app.route("/connect_john_jane", methods=["POST"])
def connect_john_jane():
    response = requests.post("http://john:8031/out-of-band/create-invitation", json={
        "handshake_protocols": ["https://didcomm.org/didexchange/1.0"],
        "use_public_did": False
    })
    invitation = response.json()["invitation"]

    requests.post("http://jane:8032/out-of-band/receive-invitation", json=invitation)

    return redirect_with_alert("Created invitation between John and Jane!")

@app.route("/connect_james_jane", methods=["POST"])
def connect_james_jane():
    response = requests.post("http://james:8033/out-of-band/create-invitation", json={
        "handshake_protocols": ["https://didcomm.org/didexchange/1.0"],
        "use_public_did": False
    })
    invitation = response.json()["invitation"]

    requests.post("http://jane:8032/out-of-band/receive-invitation", json=invitation)

    return redirect_with_alert("Created connection between James and Jane!")

@app.route("/request_proof", methods=["POST"])
def request_proof():
    conns = requests.get("http://james:8033/connections").json()["results"]
    if not conns:
        return redirect_with_alert("There is no connection between James and Jane!")

    conn_id = conns[0]["connection_id"]

    if not wait_until_connection_active("http://james:8033", conn_id):
        return redirect_with_alert("Connection not ready after waiting!")

    proof_request = {
        "connection_id": conn_id,
        "presentation_request": {
            "indy": {
                "name": "Proof of Role",
                "version": "1.0",
                "requested_attributes": {
                    "attr1_referent": {
                        "name": "name"
                    },
                    "attr2_referent": {
                        "name": "role"
                    }
                },
                "requested_predicates": {}
            }
        }
    }

    response = requests.post("http://james:8033/present-proof-2.0/send-request", json=proof_request)

    if response.status_code == 200:
        return redirect_with_alert("Proof request sent from James to Jane!")
    else:
        return redirect_with_alert(f"Error sending proof request!\n{response.text}")

@app.route("/issue_credential", methods=["POST"])
def issue_credential():
    try:
        with open("cred_def.txt", "r") as f:
            cred_def_data = json.loads(f.read())
    except FileNotFoundError:
        return redirect_with_alert("The credential definition is not found!")

    conns = requests.get("http://john:8031/connections").json()["results"]
    if not conns:
        return redirect_with_alert("There is no connection between John and Jane!")

    conn_id = conns[0]["connection_id"]

    if not wait_until_connection_active("http://john:8031", conn_id):
        return redirect_with_alert("Connection not ready after waiting!")

    cred_defs = requests.get("http://john:8031/credential-definitions/created").json()
    if not cred_defs.get("credential_definition_ids"):
        return redirect_with_alert("No credential definition found on ledger. Please init schema first!")

    latest_cred_def_id = cred_defs["credential_definition_ids"][-1]

    credential = {
        "connection_id": conn_id,
        "credential_preview": {
            "@type": "issue-credential/2.0/credential-preview",
            "attributes": [
                {"name": "name", "value": "Jane Doe"},
                {"name": "role", "value": "User"}
            ]
        },
        "filter": {
            "indy": {
                "cred_def_id": latest_cred_def_id
            }
        }
    }

    response = requests.post("http://john:8031/issue-credential-2.0/send", json=credential)

    if response.status_code == 200:
        return redirect_with_alert("Credential issued to Jane")
    else:
        return redirect_with_alert(f"Error sending credential!\n{response.text}")

@app.route("/init_schema", methods=["POST"])
def init_schema():
    schema_name = f"MyTestSchema_{uuid.uuid4().hex[:6]}"
    schema_version = "1.0"

    existing = requests.get(f"http://john:8031/schemas/created?schema_name={schema_name}&schema_version={schema_version}").json()

    if existing.get("schema_ids"):
        schema_id = existing["schema_ids"][-1]
    else:
        schema = {
            "schema_name": schema_name,
            "schema_version": schema_version,
            "attributes": ["name", "role"]
        }
        response = requests.post("http://john:8031/schemas", json=schema)
        if response.status_code != 200:
            return redirect_with_alert(f"Schema creation failed: {response.text}")
        schema_id = response.json().get("schema_id")

    cred_defs = requests.get("http://john:8031/credential-definitions/created").json()
    for cd_id in cred_defs.get("credential_definition_ids", []):
        if schema_id in cd_id:
            with open("cred_def.txt", "w") as f:
                f.write(json.dumps({"cred_def_id": cd_id}))
            return redirect_with_alert("Existing credential definition reused.")

    cred_def = {
        "schema_id": schema_id,
        "support_revocation": False,
        "tag": f"tag_{uuid.uuid4().hex[:4]}"
    }

    cred_def_response = requests.post("http://john:8031/credential-definitions", json=cred_def)
    if cred_def_response.status_code != 200:
        return redirect_with_alert(f"Credential definition failed: {cred_def_response.text}")

    with open("cred_def.txt", "w") as f:
        f.write(json.dumps(cred_def_response.json()))

    return redirect_with_alert("Schema and credential definition ready on ledger.")

def init_sequence():
    print("Starting automated sequence...", file=sys.stderr)

    print("[1] Creating Schema + Credential Definition -> John", file=sys.stderr)
    requests.post("http://localhost:8051/init_schema")
    time.sleep(10)

    print("[2] John -> Jane: Create Connection", file=sys.stderr)
    requests.post("http://localhost:8051/connect_john_jane")
    time.sleep(10)

    print("[3] John -> Jane: Issue VC", file=sys.stderr)
    requests.post("http://localhost:8051/issue_credential")
    time.sleep(10)

    print("[4] James -> Jane: Create Connection", file=sys.stderr)
    requests.post("http://localhost:8051/connect_james_jane")
    time.sleep(10)

    print("[5] James -> Jane: Proof request", file=sys.stderr)
    requests.post("http://localhost:8051/request_proof")
    print("Sequence complete.", file=sys.stderr)


@app.route('/webhooks/topic/<topic>/', methods=['POST'])
def webhook(topic):
    data = request.get_json()
    log_entry = {"topic": topic, "data": data}
    webhook_logs.append(log_entry)

    with open(LOG_FILE, "w") as f:
        json.dump(webhook_logs, f, indent=2)

    print(f"Webhook received: {topic}", file=sys.stderr)
    return "ok", 200

@app.route('/')
def index():
    html = """
    <h1>Controller is running!</h1>
    """
    return render_template_string(html, logs=webhook_logs)

if __name__ == '__main__':
    app.logger.info("Starting the application...")
#    app.run(host='0.0.0.0', port=8051, development=True, use_reloader=False)
    print("Starting the application...2", file=sys.stderr)
    print("Starting the application...3", file=sys.stdout)
    time.sleep(15)
    init_sequence()