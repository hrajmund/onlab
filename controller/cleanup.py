# cleanup.py
import json
import csv
from datetime import datetime

LOG_FILE = "log.json"
OUTPUT_FILE = "log_summary.csv"

def extract_logs():
    with open(LOG_FILE, "r") as f:
        logs = json.load(f)

    summary = []
    for entry in logs:
        topic = entry.get("topic", "N/A")
        data = entry.get("data", {})
        timestamp = data.get("updated_at") or data.get("created_at") or "N/A"
        state = data.get("state", "N/A")
        conn_id = data.get("connection_id", "N/A")

        summary.append({
            "timestamp": timestamp,
            "topic": topic,
            "state": state,
            "connection_id": conn_id
        })

    with open(OUTPUT_FILE, "w", newline="") as csvfile:
        fieldnames = ["timestamp", "topic", "state", "connection_id"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary)

    print(f"Log summary saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    extract_logs()
