# simulator/send_mock.py - send mock WhatsApp webhook payloads to local webhook
import requests
import json
import sys

WEBHOOK_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/webhook"

sample_payload = {
  "entry": [
    {
      "id": "test",
      "changes": [
        {
          "value": {
            "metadata": {"phone_number_id": "12345"},
            "messages": [
              {
                "from": "+919812345678",
                "id": "wamid.TEST",
                "timestamp": "1660000000",
                "text": {"body": "hi"},
                "type": "text"
              }
            ]
          }
        }
      ]
    }
  ]
}

r = requests.post(WEBHOOK_URL, json=sample_payload)
print("Status:", r.status_code, r.text)