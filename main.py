from flask import Flask, request
import requests
import pymongo
import time
import os

app = Flask(name)

ENV variables

BOT_TOKEN = os.environ.get("BOT_TOKEN") MONGO_URI = os.environ.get("MONGO_URI") ADMIN_ID = int(os.environ.get("ADMIN_ID", 0)) REQUIRED_CHANNELS = os.environ.get("REQUIRED_CHANNELS", "").split(',')

MongoDB setup

client = pymongo.MongoClient(MONGO_URI) db = client["actualearn"] users = db["users"]

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

Helper functions

def send_message(chat_id, text, reply_markup=None): data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"} if reply_markup: data["reply_markup"] = reply_markup requests.post(f"{TELEGRAM_API}/sendMessage", json=data)

def get_user(user_id): return users.find_one({"user_id": user_id})

def is_user_joined_all_channels(user_id): for channel in REQUIRED_CHANNELS: url = f"{TELEGRAM_API}/getChatMember?chat_id={channel}&user_id={user_id}" r = requests.get(url).json() status = r.get("result", {}).get("status", "left") if status not in ["member", "administrator", "creator"]: return False return True

@app.route(f"/{BOT_TOKEN}", methods=["POST"]) def webhook(): data = request.get_json()

if "message" in data:
    message = data["message"]
    text = message.get("text", "")
    user_id = message["from"]["id"]
    chat_id = message["chat"]["id"]
    username = message["from"].get("username", "")

    user = get_user(user_id)

    if text == "/start":
        if not user:
            users.insert_one({"user_id": user_id, "username": username, "balance": 0, "referrer": None, "awaiting_upi": False})

        if not is_user_joined_all_channels(user_id):
            buttons = [[{"text": "🔗 Join Channel", "url": f"https://t.me/{channel.replace('@', '')}"}] for channel in REQUIRED_CHANNELS]
            buttons.append([{"text": "✅ I've Joined", "callback_data": "verify_join"}])
            reply_markup = {"inline_keyboard": buttons}
            send_message(chat_id, "👋 Welcome to Actualearn! Join the required channels to continue.", reply_markup)
            return "", 200

        send_message(chat_id, "🎉 You're already verified! Use /balance or /withdraw.")

    elif text == "/balance":
        balance = user.get("balance", 0) if user else 0
        send_message(chat_id, f"💰 Your Balance: ₹{balance}")

    elif text == "/withdraw":
        if user:
            balance = user.get("balance", 0)
            last_withdrawal = user.get("last_withdrawal", 0)
            now = time.time()

            if now - last_withdrawal < 86400:
                send_message(chat_id, "❌ You can only withdraw once every 24 hours.")
            elif balance >= 16:
                send_message(chat_id, "📥 Please send your UPI ID to proceed with the withdrawal.")
                users.update_one({"user_id": user_id}, {"$set": {"awaiting_upi": True}})
            else:
                send_message(chat_id, "❌ Minimum withdrawal is ₹16. Earn more by referring others.")
        else:
            send_message(chat_id, "ℹ️ You are not registered yet. Send /start first.")

    elif user and user.get("awaiting_upi"):
        upi_id = text.strip()
        balance = user.get("balance", 0)

        send_message(chat_id, f"✅ Withdrawal request received.\n💰 Amount: ₹{balance}\n🔢 UPI: {upi_id}")

        if ADMIN_ID:
            send_message(ADMIN_ID, f"📥 <b>Withdraw Request</b>\n👤 User: @{username} ({user_id})\n💰 Amount: ₹{balance}\n🔢 UPI ID: <code>{upi_id}</code>")

        users.update_one({"user_id": user_id}, {"$set": {"balance": 0, "awaiting_upi": False, "last_withdrawal": time.time()}})

elif "callback_query" in data:
    query = data


# Health Check Route
@app.route("/", methods=["GET"])
def home():
    return "✅ Actualearn Bot is Live", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
