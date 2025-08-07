from flask import Flask, request
import requests
import os
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)

# Set your tokens and config
BOT_TOKEN = "YOUR_BOT_TOKEN"
MONGO_URI = "YOUR_MONGODB_URI"
CHANNELS = ["@yourchannel1", "@yourchannel2"]
MIN_WITHDRAW = 16
ADMIN_ID = 123456789  # replace with your Telegram ID

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client["actualearn"]
users_col = db["users"]

# Utils
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=data)

def check_membership(user_id):
    for channel in CHANNELS:
        check_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember?chat_id={channel}&user_id={user_id}"
        response = requests.get(check_url).json()
        status = response.get("result", {}).get("status", "")
        if status not in ["member", "administrator", "creator"]:
            return False
    return True

def get_user(user_id):
    return users_col.find_one({"user_id": user_id})

def update_balance(user_id, amount):
    users_col.update_one({"user_id": user_id}, {"$inc": {"balance": amount}}, upsert=True)

# Routes
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        user_id = message["from"]["id"]
        text = message.get("text", "")

        user = get_user(user_id)
        if not user:
            users_col.insert_one({
                "user_id": user_id,
                "balance": 0,
                "ref_by": None,
                "withdrawals": [],
            })

        if text.startswith("/start"):
            if not check_membership(user_id):
                join_text = "❌ Please join all the channels before verifying:\n"
                for ch in CHANNELS:
                    join_text += f"➡️ {ch}\n"
                send_message(chat_id, join_text)
                return "ok"

            parts = text.split()
            if len(parts) > 1:
                ref_id = int(parts[1])
                if ref_id != user_id:
                    ref_user = get_user(user_id)
                    if not ref_user or not ref_user.get("ref_by"):
                        users_col.update_one(
                            {"user_id": user_id}, {"$set": {"ref_by": ref_id}}, upsert=True
                        )
                        update_balance(ref_id, 2)
                        send_message(ref_id, "🎉 You got ₹2 for a referral!")

            send_message(chat_id, "✅ You're verified and logged in!")

        elif text == "/balance":
            balance = get_user(user_id).get("balance", 0)
            send_message(chat_id, f"💰 Your balance: ₹{balance}")

        elif text == "/withdraw":
            user_data = get_user(user_id)
            balance = user_data.get("balance", 0)
            today = datetime.utcnow().date()
            withdrawals = user_data.get("withdrawals", [])
            if any(wd.get("date") == str(today) for wd in withdrawals):
                send_message(chat_id, "❌ You can only withdraw once per day.")
                return "ok"

            if balance < MIN_WITHDRAW:
                send_message(chat_id, f"❌ Minimum ₹{MIN_WITHDRAW} required to withdraw.")
            else:
                users_col.update_one(
                    {"user_id": user_id},
                    {"$inc": {"balance": -MIN_WITHDRAW}, "$push": {"withdrawals": {"date": str(today)}}}
                )
                send_message(chat_id, "✅ Withdrawal request sent to admin!")
                send_message(ADMIN_ID, f"📤 User {user_id} requested withdrawal.")

    return "ok"

# Set webhook
@app.route("/setwebhook", methods=["GET"])
def set_webhook():
    webhook_url = f"https://YOUR_KOYEB_URL/{BOT_TOKEN}"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
    response = requests.get(url)
    return response.text

# Run the app
if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
