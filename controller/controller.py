import json
import os
import uuid
import collections
import requests
import time
from arpeggio import *
from arpeggio import RegExMatch as _
from flask import Flask, request, render_template_string, redirect

app = Flask(__name__)
LOG_FILE = "log.json"
webhook_logs = []

agentConnection = collections.namedtuple('agentConnection', ['name', 'admin_url', 'endpoint'])
agent_list = []

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

@app.route('/subscribe', methods=['POST'])
def subscribe_form():
    label = request.form.get("label")
    admin_url = request.form.get("admin_url")
    endpoint = request.form.get("endpoint")
    if label:
        agent_list.append(agentConnection(label, admin_url, endpoint))
        f = open("agents.txt", "a")
        return redirect("/")
    return "Hiányzó adat", 400

@app.route('/webhooks/topic/<topic>/', methods=['POST'])
def webhook(topic):
    data = request.get_json()
    log_entry = {"topic": topic, "data": data}
    webhook_logs.append(log_entry)

    with open(LOG_FILE, "w") as f:
        json.dump(webhook_logs, f, indent=2)

    print(f"Webhook received: {topic}", flush=True)
    return "ok", 200

@app.route('/')
def index():
    html = """
    <h1>Controller is running!</h1>

    <h2>Actions</h2>

    <form action="/connect_john_jane" method="post">
        <button type="submit">John -> Jane: Create Connection</button>
    </form>

    <form action="/issue_credential" method="post">
        <button type="submit">John -> Jane: Issue VC</button>
    </form>

    <form action="/request_proof" method="post">
        <button type="submit">James -> Jane: Proof request</button>
    </form>

    <form action="/connect_james_jane" method="post">
        <button type="submit">James -> Jane: Create Connection</button>
    </form>

    <form action="/init_schema" method="post">
        <button type="submit">Create Schema + Credential Definition -> John</button>
    </form>
    <hr>
    """
    return render_template_string(html, logs=webhook_logs, agents=agent_list)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8051, debug=True)