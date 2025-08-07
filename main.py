from flask import Flask, request import requests import os import time from pymongo import MongoClient

app = Flask(name)

BOT_TOKEN = "your_bot_token_here" API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/" MONGO_URL = "your_mongodb_url_here" CHANNEL_USERNAME = "@yourchannel" MIN_WITHDRAW = 16 REWARD_PER_REFERRAL = 2

client = MongoClient(MONGO_URL) db = client.actualearn users = db.users withdrawals = db.withdrawals

def send_message(chat_id, text): requests.post(API_URL + "sendMessage", json={ "chat_id": chat_id, "text": text })

def is_member(user_id): try: url = f"{API_URL}getChatMember?chat_id={CHANNEL_USERNAME}&user_id={user_id}" resp = requests.get(url).json() status = resp['result']['status'] return status in ["member", "creator", "administrator"] except: return False

@app.route(f"/{BOT_TOKEN}", methods=["POST"]) def webhook(): data = request.get_json()

if "message" not in data:
    return "ok"

message = data["message"]
chat_id = message["chat"]["id"]
user_id = message["from"]["id"]
text = message.get("text", "")

if text.startswith("/start"):
    ref = text.split(" ")[1] if " " in text else None
    user = users.find_one({"user_id": user_id})
    if not user:
        users.insert_one({"user_id": user_id, "balance": 0, "referred_by": ref, "joined": False})
        if ref and str(user_id) != ref:
            ref_user = users.find_one({"user_id": int(ref)})
            if ref_user:
                users.update_one({"user_id": int(ref)}, {"$inc": {"balance": REWARD_PER_REFERRAL}})
                send_message(int(ref), f"🎉 You got ₹{REWARD_PER_REFERRAL} for inviting a friend!")
    send_message(chat_id, "👋 Welcome to Actualearn! Join the channel and then send /balance to get ₹2.")

elif text == "/balance":
    if not is_member(user_id):
        send_message(chat_id, f"❌ Please join {CHANNEL_USERNAME} to check your balance.")
        return "ok"

    user = users.find_one({"user_id": user_id})
    if not user:
        send_message(chat_id, "Please use /start first.")
        return "ok"

    if not user.get("joined"):
        users.update_one({"user_id": user_id}, {"$inc": {"balance": REWARD_PER_REFERRAL}, "$set": {"joined": True}})
        send_message(chat_id, f"✅ You've received ₹{REWARD_PER_REFERRAL} for joining!")

    balance = users.find_one({"user_id": user_id}).get("balance", 0)
    send_message(chat_id, f"💰 Your balance is ₹{balance}")

elif text == "/withdraw":
    user = users.find_one({"user_id": user_id})
    if not user:
        send_message(chat_id, "Please use /start first.")
        return "ok"

    balance = user.get("balance", 0)
    last_withdrawal = withdrawals.find_one({"user_id": user_id})
    now = int(time.time())

    if balance < MIN_WITHDRAW:
        send_message(chat_id, f"❌ Minimum ₹{MIN_WITHDRAW} required to withdraw.")
    elif last_withdrawal and now - last_withdrawal.get("timestamp", 0) < 86400:
        send_message(chat_id, "⏳ You can only withdraw once every 24 hours.")
    else:
        withdrawals.update_one({"user_id": user_id}, {"$set": {"timestamp": now}}, upsert=True)
        users.update_one({"user_id": user_id}, {"$inc": {"balance": -MIN_WITHDRAW}})
        send_message(chat_id, "✅ Withdrawal request received. You will be paid manually soon.")

return "ok"

@app.route("/") def index(): return "Bot is running."

if name == "main": app.run(debug=False, host="0.0.0.0", port=5000)

