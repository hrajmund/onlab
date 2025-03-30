import json
import os
import collections
from arpeggio import *
from arpeggio import RegExMatch as _
from flask import Flask, request, render_template_string, redirect

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

if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r") as f:
        try:
            webhook_logs = json.load(f)
        except json.JSONDecodeError:
            webhook_logs = []

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

@app.route('/test')
def TestPage():
    return """
        <h1>Hello world</h1>
        <form action="/" method="get">
            <button>Go back </button>
        </form>
    """

@app.route('/')
def index():
    html = """
    <h1>Controller is running!</h1>
    <form action="/test" method="get">
        <button>Goto test</button>
    </form>

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

    {% if logs %}
        <h2>Webhook events:</h2>
        {% for log in logs %}
            <h3>{{ log.topic }}</h3>
            <pre>{{ log.data | tojson(indent=2) }}</pre>
            <hr>
        {% endfor %}
    {% else %}
        <p>Currently there are no webhooks.</p>
    {% endif %}
    """
    return render_template_string(html, logs=webhook_logs, agents=agent_list)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8051, debug=True)
    
    #parser = ParserPython(csvfile, ws='\t ')
    #test_data = open('../conf/agent.csv', 'r').read()
    #parse_tree = parser.parse(test_data)
