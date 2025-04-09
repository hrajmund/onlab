import json
import os
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

def field_content_quoted():     return _(r'(("")|([^"]))+')
def quoted_field():             return '"', field_content_quoted, '"'
def field_content():            return _(r'([^,\n])+')
def field():                    return [quoted_field, field_content]
def record():                   return field, ZeroOrMore(",", field)
def csvfile():                  return OneOrMore([record, '\n']), EOF

def redirect_with_alert(message: str, target: str = "/"):
    return f"""
        <script>
            alert("{message}");
            window.location.href = "{target}";
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
                "issuer_did": "NcYxiDXkpYi6ov5FcYDi1e",
                "schema_id": "NcYxiDXkpYi6ov5FcYDi1e:2:MyTestSchema:1.0",
                "cred_def_id": "NcYxiDXkpYi6ov5FcYDi1e:3:CL:20:tag"
            }
        }
    }

    response = requests.post("http://john:8031/issue-credential-2.0/send", json=credential)

    if response.status_code == 200:
        return redirect_with_alert("Credential issued to Jane (ledgerless)")
    else:
        return redirect_with_alert(f"Error sending credential!\n{response.text}")

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

@app.route("/init_schema", methods=["POST"])
def init_schema():
    schema = {
        "schema_name": "MyTestSchema",
        "schema_version": "1.0",
        "attributes": ["name", "role"]
    }

    cred_def = {
        "schema": schema,
        "support_revocation": False
    }

    with open("cred_def.txt", "w") as f:
        f.write(json.dumps(cred_def))

    return redirect_with_alert(
        "Schema and 'credential definition' data saved locally (no-ledger mode)."
    )


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

    {% if agents %}
        <h2>Agents: </h2>
        {% for agent in agents %}
            <p>{{ agent.name }} {{ agent.admin_url }} {{ agent.endpoint }}</p>
        {% endfor %}
    {% else %}
        <p>Currently there are no agents.</p>
    {% endif %}
    <h2>Register Agent</h2>
    <form action="/subscribe" method="post">
        <label>Name: <input type="text" name="label" required></label><br>
        <label>Admin URL: <input type="text" name="admin_url" required></label><br>
        <label>Endpoint URL: <input type="text" name="endpoint" required></label><br>
        <button type="submit">Subsrcibe</button>
    </form>

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

    <form action="/init_schema" method="post">
        <button type="submit">Create Schema + Credential Definition -> John</button>
    </form>
    <hr>
    """
    return render_template_string(html, logs=webhook_logs, agents=agent_list)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8051, debug=True)