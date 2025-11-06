# app.py - FastAPI WhatsApp bot for edo (Meta WhatsApp Cloud API)
import os
import hmac
import hashlib
import json
from typing import Optional
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import PlainTextResponse
import httpx
from supabase import create_client
from datetime import datetime
from uuid import uuid4
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET")
WEBHOOK_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "edo_verify_token")
import sys
print(f"[DEBUG] Loaded WEBHOOK_VERIFY_TOKEN = '{WEBHOOK_VERIFY_TOKEN}'", file=sys.stderr)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Set SUPABASE_URL and SUPABASE_SERVICE_KEY in env")

SUPABASE = create_client(SUPABASE_URL, SUPABASE_KEY)
WHATSAPP_API_URL = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

app = FastAPI(title="edo - WhatsApp Bot")
@app.get("/debug-env")
async def debug_env():
    import os
    return {
        "WEBHOOK_VERIFY_TOKEN": os.getenv("WEBHOOK_VERIFY_TOKEN"),
        "WHATSAPP_TOKEN": bool(os.getenv("WHATSAPP_TOKEN")),
        "SUPABASE_URL": bool(os.getenv("SUPABASE_URL")),
    }


async def send_whatsapp_text(to: str, text: str, preview_url: bool = False):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text, "preview_url": preview_url}
    }
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    async with httpx.AsyncClient() as client:
        r = await client.post(WHATSAPP_API_URL, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def verify_signature(raw_body: bytes, header_signature: Optional[str]) -> bool:
    if not WHATSAPP_APP_SECRET:
        return True
    if not header_signature:
        return False
    try:
        sha_name, signature = header_signature.split('=')
    except Exception:
        return False
    mac = hmac.new(WHATSAPP_APP_SECRET.encode(), msg=raw_body, digestmod=hashlib.sha1)
    expected = mac.hexdigest()
    return hmac.compare_digest(expected, signature)

async def log_whatsapp_message(direction: str, from_no: str, to_no: str, payload: dict, user_id: Optional[str]=None, shop_id: Optional[str]=None, order_id: Optional[str]=None):
    try:
        await SUPABASE.table("whatsapp_messages").insert({
            "direction": direction,
            "whatsapp_from": from_no,
            "whatsapp_to": to_no,
            "payload": payload,
            "user_id": user_id,
            "shop_id": shop_id,
            "order_id": order_id,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print("Log error", e)

@app.get("/webhook")
async def verify_webhook(request: Request):
    import sys
    params = dict(request.query_params)
    print(f"[DEBUG] Full query params: {params}", file=sys.stderr)
    print(f"[DEBUG] Loaded WEBHOOK_VERIFY_TOKEN={WEBHOOK_VERIFY_TOKEN}", file=sys.stderr)

    mode = params.get("hub.mode")
    challenge = params.get("hub.challenge")
    verify_token = params.get("hub.verify_token")

    print(f"[DEBUG] mode={mode}, challenge={challenge}, verify_token={verify_token}", file=sys.stderr)

    if mode == "subscribe" and verify_token and verify_token.strip() == WEBHOOK_VERIFY_TOKEN.strip():
        print("[DEBUG] Verification successful ✅", file=sys.stderr)
        return PlainTextResponse(challenge)
    else:
        raise HTTPException(
            status_code=403,
            detail=f"Verification failed: got {verify_token!r}, expected {WEBHOOK_VERIFY_TOKEN!r}"
        )

@app.post("/webhook")
async def webhook_receiver(request: Request, x_hub_signature: Optional[str] = Header(None)):
    raw = await request.body()
    #if not verify_signature(raw, x_hub_signature):
    #    raise HTTPException(status_code=403, detail="Invalid signature")
    payload = await request.json()
    print("[DEBUG] Raw webhook payload:", json.dumps(payload, indent=2))
    entry = payload.get("entry", [])
    for e in entry:
        for change in e.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            metadata = value.get("metadata", {})
            phone_id = metadata.get("phone_number_id")
            for msg in messages:
                wa_from = msg.get("from")
                wa_type = msg.get("type")
                text_body = None
                if wa_type == "text":
                    text_body = msg.get("text", {}).get("body")
                await log_whatsapp_message("inbound", wa_from, phone_id, msg)
                await handle_inbound_message(wa_from, phone_id, msg, text_body)
    return {"status":"ok"}

async def handle_inbound_message(from_no: str, to_phone_id: str, msg: dict, text_body: Optional[str]):
    shop_map = None
    try:
        resp = await SUPABASE.table("shop_whatsapp_mappings").select("*").eq("whatsapp_phone_id", to_phone_id).limit(1).execute()
        shop_map = (resp.data or [None])[0]
    except Exception as e:
        print("Error reading shop mapping", e)
    text = (text_body or "").strip().lower() if text_body else ""
    if not text:
        await send_whatsapp_text(from_no, "Sorry, I didn't understand. Reply 'menu' to see options.")
        return
    if text in ("hi","hello","menu"):
        await send_welcome(from_no, shop_map)
        return
    if text.startswith("list") or text == "1":
        await list_items(from_no, shop_map, page=1)
        return
    if text.startswith("view "):
        parts = text.split()
        if len(parts) >= 2:
            item_id = parts[1]
            await view_item(from_no, shop_map, item_id)
            return
    if text.startswith("order "):
        parts = text.split()
        if len(parts) >= 2:
            item_id = parts[1]
            qty = 1
            if "qty" in parts:
                try:
                    idx = parts.index("qty")
                    qty = int(parts[idx+1])
                except Exception:
                    qty = 1
            await create_order_via_whatsapp(from_no, shop_map, item_id, qty)
            return
    if text in ("faq","4"):
        await send_faq(from_no)
        return
    if text == "help":
        await send_whatsapp_text(from_no, "Options:\\n1 List\\n2 View <id>\\n3 Order <id> qty <n>\\n4 FAQ\\nOr ask a question.")
        return
    if shop_map:
        await forward_to_seller(from_no, shop_map, text, msg)
    else:
        await send_whatsapp_text(from_no, "Thanks for your message. A seller will get back to you soon. Reply 'menu' to see options.")

async def send_welcome(to_no: str, shop_map):
    shop_name = "the shop" if not shop_map else f"Shop {shop_map.get('shop_id')}"
    text = f"Hi 👋 — you’re chatting with {shop_name} on edo. Reply: 1 — View listings, 2 — View item (send 'view <ID>'), 3 — Place an order (send 'order <ID> qty <n>'), 4 — FAQs"
    await send_whatsapp_text(to_no, text)

async def list_items(to_no: str, shop_map, page=1):
    try:
        if shop_map:
            seller_id = shop_map.get("seller_user_id")
            resp = await SUPABASE.table("marketplace_items").select("id,title,price,condition,status").eq("seller_id", seller_id).eq("status","available").limit(10).execute()
        else:
            resp = await SUPABASE.table("marketplace_items").select("id,title,price,condition,status").eq("status","available").limit(10).execute()
        items = resp.data or []
    except Exception as e:
        print("error fetching items", e)
        items = []
    if not items:
        await send_whatsapp_text(to_no, "No items found.")
        return
    body_lines = []
    for idx, it in enumerate(items, start=1):
        body_lines.append(f"{idx}) {it['title']} — ₹{it['price']} — ID: {it['id']}")
    body_lines.append("\\nReply 'view <ID>' to see details or 'order <ID> qty 1' to order.")
    await send_whatsapp_text(to_no, "\\n".join(body_lines))

async def view_item(to_no: str, shop_map, item_id: str):
    try:
        resp = await SUPABASE.table("marketplace_items").select("*").eq("id", item_id).limit(1).execute()
        item = (resp.data or [None])[0]
    except Exception as e:
        print("error", e)
        item = None
    if not item:
        await send_whatsapp_text(to_no, "Item not found. Check ID and try again.")
        return
    images = item.get("images") or []
    if isinstance(images, list) and len(images) > 0:
        image_url = images[0]
        # lightweight: send text with image link (image API omitted for brevity)
        await send_whatsapp_text(to_no, f"{item['title']} — ₹{item['price']}\\n{image_url}")
    else:
        await send_whatsapp_text(to_no, f"{item['title']} — ₹{item['price']}\\n{item.get('description','')}")
    await send_whatsapp_text(to_no, f"To order reply: order {item_id} qty 1\\nOr reply 'chat' to message seller.")

async def create_order_via_whatsapp(from_no: str, shop_map, item_id: str, qty: int = 1):
    try:
        resp = await SUPABASE.table("marketplace_items").select("*").eq("id", item_id).limit(1).execute()
        item = (resp.data or [None])[0]
    except Exception as e:
        item = None
    if not item:
        await send_whatsapp_text(from_no, "Item not found.")
        return
    buyer_user_id = None
    try:
        uresp = await SUPABASE.table("users").select("id").eq("phone", from_no).limit(1).execute()
        buyer = (uresp.data or [None])[0]
        buyer_user_id = buyer.get("id") if buyer else None
    except Exception:
        buyer_user_id = None
    order_id = str(uuid4())
    order_payload = {
        "id": order_id,
        "item_id": item_id,
        "buyer_user_id": buyer_user_id,
        "seller_user_id": item.get("seller_id"),
        "quantity": qty,
        "price": item.get("price"),
        "status": "created",
        "whatsapp_thread_id": from_no,
        "created_at": datetime.utcnow().isoformat()
    }
    try:
        await SUPABASE.table("orders").insert(order_payload).execute()
    except Exception as e:
        print("order insert error", e)
        await send_whatsapp_text(from_no, "Unable to create order. Try again later.")
        return
    await send_whatsapp_text(from_no, f"Order created: ORD-{order_id[:8]}. Reply 'confirm ORD-{order_id[:8]}' to confirm.")
    if shop_map:
        seller_no = shop_map.get("whatsapp_phone")
        await send_whatsapp_text(seller_no, f"New order ORD-{order_id[:8]} created for item {item.get('title')}. Buyer: {from_no}. Reply 'accept ORD-{order_id[:8]}' to accept.")

async def forward_to_seller(from_no: str, shop_map, text: str, msg: dict):
    seller_no = shop_map.get("whatsapp_phone")
    if not seller_no:
        await send_whatsapp_text(from_no, "Sorry, the seller is unavailable right now.")
        return
    forwarded = f"Message from {from_no}:\\n\\n{text}\\n\\n(Reply here to message buyer)"
    await send_whatsapp_text(seller_no, forwarded)
    await log_whatsapp_message("outbound", seller_no, from_no, {"forwarded_text": text}, shop_id=shop_map.get("shop_id"))