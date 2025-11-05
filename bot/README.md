# edo WhatsApp Bot (FastAPI)
## Overview
FastAPI webhook + handler for WhatsApp Cloud API (Meta). Integrates with Supabase.
## Run locally
1. Copy `.env.example` to `.env` and populate values.
2. Install deps: `pip install -r requirements.txt`
3. Start: `uvicorn app:app --reload --port 8000`
4. Use ngrok to expose `http://localhost:8000/webhook` to Meta for webhook events.
## Docker
Build: `docker build -t edo-bot .`
Run: `docker run -e ... -p 8000:8000 edo-bot`