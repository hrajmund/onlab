import json
import os
import collections
import requests
from arpeggio import *
from arpeggio import RegExMatch as _
from flask import Flask, request, render_template_string, redirect, Response

app = Flask(__name__)
LOG_FILE = "log.json"
webhook_logs = []

### TODO - To be discussed
# The agent tuple should be a class
# BaseAgent then AskarAgent ?
agentConnection = collections.namedtuple('agentConnection', ['name', 'admin_url', 'endpoint'])
agent_list = []

def field_content_quoted():     return _(r'(("")|([^"]))+')
def quoted_field():             return '"', field_content_quoted, '"'
def field_content():            return _(r'([^,\n])+')
def field():                    return [quoted_field, field_content]
def record():                   return field, ZeroOrMore(",", field)
def csvfile():                  return OneOrMore([record, '\n']), EOF

def redirect_with_alert(message: str, target: str = "/"):
    html = f"""
        <script>
            alert("{message}");
            window.location.href = "{target}";
        </script>
    """
    return Response(html, mimetype='text/html')


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
    active_conns = [conn for conn in conns if conn["state"] == "active"]
    if not active_conns:
        return redirect_with_alert("There is no connection between John and Jane!")

    conn_id = active_conns[0]["connection_id"]

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
    if response.ok:
        return redirect_with_alert("Credential offer sent to Jane")
    else:
        return redirect_with_alert(f"Error with sending the offer! Response: {response.status_code} {response.text}")

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
@app.route("/init_schema")
def init_schema():
    schema = {
        "schema_name": "MyTestSchema",
        "version": "1.0",
        "attributes": ["name", "email", "age"]
    }

    try:
        schema_resp = requests.post("http://issuer:8031/schemas", json=schema)
        if schema_resp.status_code == 200:
            schema_id = schema_resp.json()["schema_id"]
        elif schema_resp.status_code == 400 and "already exists" in schema_resp.text:
            existing = requests.get("http://issuer:8031/schemas/created").json()
            schema_id = next((sid for sid in existing["schema_ids"] if schema["schema_name"] in sid and schema["version"] in sid), None)
            if not schema_id:
                return redirect_with_alert("Schema already exists, de nem található vissza!")
        else:
            return redirect_with_alert(f"Creating schema failed! Response: {schema_resp.status_code}: {schema_resp.text}")

        cred_def = {
            "schema_id": schema_id,
            "support_revocation": False,
            "tag": "default"
        }
        cred_def_resp = requests.post("http://issuer:8031/credential-definitions", json=cred_def)
        if cred_def_resp.ok:
            cred_def_id = cred_def_resp.json()["credential_definition_id"]
            with open("cred_def.txt", "w") as f:
                f.write(cred_def_id)
            return redirect_with_alert(f"Schema & Credential Definition OK!\nCredDef ID:\n{cred_def_id}")
        else:
            return redirect_with_alert(f"Creating credential definition failed! Response: {cred_def_resp.status_code}: {cred_def_resp.text}")

    except Exception as e:
        return redirect_with_alert(f"Hiba: {str(e)}")


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
    
    #parser = ParserPython(csvfile, ws='\t ')
    #test_data = open('../conf/agent.csv', 'r').read()
    #parse_tree = parser.parse(test_data)
