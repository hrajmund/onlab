import asyncio
import time
import json
import os
import requests
from flask import Flask, render_template_string, request

app = Flask(__name__)

AGENTS = {
    "john": {"admin": "http://john:8030"},
    "jane": {"admin": "http://jane:8032"},
    "james": {"admin": "http://james:8034"},
}

SCHEMA_ID = None
CRED_DEF_IDS = {}
VDR_FILE = "vdr.json"

def redirect_with_alert(message, target="/"):
    return render_template_string(f"""
        <script>alert("{message}"); window.location.href="{target}";</script>
    """)

@app.route("/webhooks/topic/<topic>/", methods=["POST"])
def webhook(topic):
    data = request.json
    print(f"[WEBHOOK] Topic: {topic}\n{json.dumps(data, indent=2)}")

    if topic == "connections" and data.get("state") == "active":
        print(f"Active! ID: {data['connection_id']}")
    return "", 200

@app.route("/register_schema", methods=["GET", "POST"])
def register_schema():
    print("Registering schema...", flush=True)
    if request.method == "POST":
        try:
            issuer = request.form["issuer"]
        except Exception as e:
            print(f"Failed to get issuer from form: {e}", flush=True)
            return redirect_with_alert(f"Hibás kérés: {e}")
    else:
        return redirect_with_alert("Csak POST metódus engedélyezett.")
        
    issuer = request.form["issuer"]
    issuer_ep = AGENTS[issuer]["admin"]

    schema_name = "EmailSchema"
    schema_version = "1.0"
    attributes = ["name", "email"]

    schema_body = {
        "schema_name": schema_name,
        "schema_version": schema_version,
        "attributes": attributes
    }

    try:
        res = requests.post(f"{issuer_ep}/schemas", json=schema_body)
        res.raise_for_status()
        schema_id = res.json()["schema_id"]
    except Exception as e:
        return redirect_with_alert(f"Schema registration failed: {e}")

    cred_def_body = {
        "schema_id": schema_id,
        "support_revocation": False,
        "tag": "default"
    }

    try:
        res = requests.post(f"{issuer_ep}/credential-definitions", json=cred_def_body)
        res.raise_for_status()
        cred_def_id = res.json()["credential_definition_id"]
    except Exception as e:
        return redirect_with_alert(f"Credential Definition failed: {e}")

    global SCHEMA_ID, CRED_DEF_IDS
    SCHEMA_ID = schema_id
    CRED_DEF_IDS[issuer] = cred_def_id

    return redirect_with_alert("Schema & Credential Definition registered successfully.")


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
        <form action="/register_schema" method="post">
            <h2>Register Schema</h2>
            <input type="hidden" name="issuer" value="john">
            <button>Create Schema & CredDef</button>
        </form>
    """)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8051, debug=True)
