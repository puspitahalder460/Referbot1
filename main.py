from flask import Flask, request
import requests
import os
from pymongo import MongoClient
from datetime import datetime, timedelta

app = Flask(__name__)

# Telegram Bot Token
BOT_TOKEN = "YOUR_BOT_TOKEN"
# MongoDB Connection
MONGO_URL = "YOUR_MONGO_URL"
client = MongoClient(MONGO_URL)
db = client['actualearn']
users_col = db['users']
withdrawals_col = db['withdrawals']

# Withdraw Config
MIN_WITHDRAW = 16
REWARD_AMOUNT = 2

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    requests.post(url, data=data)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        user_id = message["from"]["id"]
        text = message.get("text", "")

        user = users_col.find_one({"user_id": user_id})
        if not user:
            users_col.insert_one({
                "user_id": user_id,
                "balance": 0,
                "referred_by": None,
                "last_withdraw": None
            })

        if text.startswith("/start"):
            parts = text.split()
            if len(parts) > 1:
                ref_code = parts[1]
                ref_id = int(ref_code)
                if ref_id != user_id:
                    ref_user = users_col.find_one({"user_id": ref_id})
                    if ref_user:
                        if user and not user.get("referred_by"):
                            users_col.update_one({"user_id": user_id}, {"$set": {"referred_by": ref_id}})
                            users_col.update_one({"user_id": ref_id}, {"$inc": {"balance": REWARD_AMOUNT}})
                            send_message(ref_id, f"🎉 You earned ₹{REWARD_AMOUNT} for referring!")
            send_message(chat_id, "👋 Welcome to Actualearn! Use /balance to check your earnings.")

        elif text == "/balance":
            user = users_col.find_one({"user_id": user_id})
            balance = user.get("balance", 0)
            send_message(chat_id, f"💰 Your current balance is ₹{balance}")

        elif text == "/withdraw":
            user = users_col.find_one({"user_id": user_id})
            balance = user.get("balance", 0)
            last_withdraw = user.get("last_withdraw")

            if balance < MIN_WITHDRAW:
                send_message(chat_id, f"❌ Minimum ₹{MIN_WITHDRAW} required to withdraw.")
                return "ok"

            if last_withdraw and datetime.now() - last_withdraw < timedelta(days=1):
                send_message(chat_id, "❌ You can only withdraw once every 24 hours.")
                return "ok"

            users_col.update_one({"user_id": user_id}, {
                "$inc": {"balance": -MIN_WITHDRAW},
                "$set": {"last_withdraw": datetime.now()}
            })

            withdrawals_col.insert_one({
                "user_id": user_id,
                "amount": MIN_WITHDRAW,
                "timestamp": datetime.now(),
                "status": "pending"
            })

            send_message(chat_id, "✅ Withdrawal request received. You will be paid shortly.")

    return "ok"

@app.route("/setwebhook", methods=["GET"])
def set_webhook():
    webhook_url = f"https://YOUR_KOYEB_URL/{BOT_TOKEN}"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
    response = requests.get(url)
    return response.text

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
