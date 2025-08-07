from flask import Flask, request, jsonify
import requests
import os
from pymongo import MongoClient

app = Flask(__name__)

BOT_TOKEN = "YOUR_BOT_TOKEN"
BOT_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
client = MongoClient("YOUR_MONGODB_URI")
db = client["actualearn"]
users = db["users"]

def send_message(chat_id, text):
    requests.post(f"{BOT_URL}/sendMessage", json={"chat_id": chat_id, "text": text})

def get_user_balance(user_id):
    user = users.find_one({"user_id": user_id})
    if user:
        return user.get("balance", 0)
    else:
        users.insert_one({"user_id": user_id, "balance": 0})
        return 0

def update_balance(user_id, amount):
    users.update_one({"user_id": user_id}, {"$inc": {"balance": amount}}, upsert=True)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")
        user_id = data["message"]["from"]["id"]

        if text == "/start":
            send_message(chat_id, "👋 Welcome to Actualearn Bot!\nEarn ₹2 per referral.")
        elif text == "/balance":
            balance = get_user_balance(user_id)
            send_message(chat_id, f"💰 Your balance is ₹{balance}")
        elif text == "/withdraw":
            balance = get_user_balance(user_id)
            if balance >= 16:
                send_message(chat_id, "✅ Withdraw request received. You'll be paid soon.")
                users.update_one({"user_id": user_id}, {"$set": {"balance": 0}})
            else:
                send_message(chat_id, "❌ Minimum ₹16 required to withdraw.")
        else:
            send_message(chat_id, "❓ Unknown command.")
    return jsonify(success=True)

@app.route("/", methods=["GET"])
def home():
    return "Bot is running!"

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)                send_message(chat_id, f"❌ Minimum ₹{MIN_WITHDRAW} required to withdraw.")

    return "ok", 200

@app.route("/")
def home():
    return "✅ Actualearn Bot is Live", 200

if __name__ == "__main__":
    app.run()
