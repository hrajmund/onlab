import json
import os
import time
import collections
import requests
from flask import Flask, request, render_template_string, redirect

app = Flask(__name__)
LOG_FILE = "log.json"
webhook_logs = []

agentConnection = collections.namedtuple('agentConnection', ['name', 'admin_url', 'endpoint'])
agent_list = []

AGENTS = {
    "john": {"endpoint": "http://john:8031"},
    "jane": {"endpoint": "http://jane:8032"},
    "james": {"endpoint": "http://james:8033"},
}

SCHEMA_ID = None
CRED_DEF_IDS = {}

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

@app.route("/issue_credential", methods=["POST"])
def issue_credential():
    try:
        with open("cred_def.txt", "r") as f:
            cred_def_id = f.read().strip()
    except FileNotFoundError:
        return redirect_with_alert("The credential definition is not found!")

    conns = requests.get("http://john:8031/connections").json()["results"]
    if not conns:
        return redirect_with_alert("There is no connection between John and Jane!")

    conn_id = conns[0]["connection_id"]

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
                "cred_def_id": cred_def_id
            }
        }
    }

    response = requests.post("http://john:8031/issue-credential-2.0/send-offer", json=credential)
    if response.status_code == 200:
        return redirect_with_alert("Credential offer sent to Jane")
    else:
        return redirect_with_alert("Error with sending the offer!")

@app.route("/init_schema", methods=["POST"])
def init_schema():
    global SCHEMA_ID, CRED_DEF_IDS

    try:
        schema = {
            "schema_name": "DummySchema",
            "schema_version": "1.0",
            "attributes": ["name", "email"]
        }

        john_resp = requests.post(f"{AGENTS['john']['endpoint']}/schemas", json=schema)
        schema_id = john_resp.json()["schema_id"]
        SCHEMA_ID = schema_id

        for agent in ["john", "jane"]:
            resp = requests.post(
                f"{AGENTS[agent]['endpoint']}/credential-definitions",
                json={"schema_id": schema_id, "support_revocation": False}
            )
            cred_def_id = resp.json()["credential_definition_id"]
            CRED_DEF_IDS[agent] = cred_def_id

        with open("cred_def.txt", "w") as f:
            f.write(CRED_DEF_IDS["john"])

        return redirect_with_alert(
            f"Schema and credential definitions created.\\n\\nSchema ID: {SCHEMA_ID}\\nJohn: {CRED_DEF_IDS['john']}\\nJane: {CRED_DEF_IDS['jane']}"
        )

    except Exception as e:
        return redirect_with_alert(f"Hiba történt schema létrehozás közben:\\n{e}")

@app.route('/subscribe', methods=['POST'])
def subscribe_form():
    label = request.form.get("label")
    admin_url = request.form.get("admin_url")
    endpoint = request.form.get("endpoint")
    if label:
        agent_list.append(agentConnection(label, admin_url, endpoint))
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
        <button type="submit">Subscribe</button>
    </form>

    <h2>Actions</h2>

    <form action="/connect_john_jane" method="post">
        <button type="submit">John -> Jane: Create Connection</button>
    </form>

    <form action="/issue_credential" method="post">
        <button type="submit">John -> Jane: Issue VC</button>
    </form>

    <form action="/init_schema" method="post">
        <button type="submit">Create Schema + Credential Definition</button>
    </form>
    <hr>
    """
    return render_template_string(html, logs=webhook_logs, agents=agent_list)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8051, debug=True)
