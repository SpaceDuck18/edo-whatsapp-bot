# twilio_adapter.py - simple Flask endpoint to receive Twilio webhook and forward to same handlers
from flask import Flask, request, jsonify
import requests, os

app = Flask(__name__)
EDO_WEBHOOK = os.getenv("EDO_INTERNAL_WEBHOOK", "http://localhost:8000/webhook")

@app.route("/twilio-webhook", methods=["POST"])
def twilio_webhook():
    # Twilio sends form-encoded body with 'From' and 'Body'
    from_no = request.form.get("From")
    body = request.form.get("Body")
    # Map into minimal shape expected by FastAPI handler
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "twilio"},
                            "messages": [
                                {"from": from_no, "id": "twilio-msg", "timestamp": "", "text": {"body": body}, "type": "text"}
                            ]
                        }
                    }
                ]
            }
        ]
    }
    r = requests.post(EDO_WEBHOOK, json=payload)
    return jsonify({"status": "forwarded", "code": r.status_code})

if __name__ == "__main__":
    app.run(port=5000)