import sys
from flask import Flask, request

app = Flask(__name__)

@app.route('/webhooks/topics/<topic>', methods=['POST'])
@app.route('/webhooks/topic/<topic>/', methods=['POST'])
def webhook(topic):
    data = request.json
    print(f"Webhook received: {topic}")
    print(f"Data: {data}")
    index(f"Webhook received: {topic}\n Data: {data}")
    return "ok", 200

# Egyszerű ellenőrzéshez
@app.route('/')
def index(output = "Controller is running! Waiting for webhooks."):
    return output

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8051)
