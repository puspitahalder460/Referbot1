from flask import Flask, request, jsonify import requests import os from pymongo import MongoClient

app = Flask(name)

BOT_TOKEN = os.getenv("BOT_TOKEN") WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN")

client = MongoClient(os.getenv("MONGO_URI")) db = client['actualearn'] users_collection = db['users']

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

REQUIRED_CHANNELS = [ "@YourChannel1",  # replace with your channel usernames "@YourChannel2" ]

MIN_WITHDRAW_AMOUNT = 16 DAILY_WITHDRAW_LIMIT = 1

---------------------- Helper Functions ----------------------

def send_message(chat_id, text): requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={ "chat_id": chat_id, "text": text })

def is_user_in_channels(user_id): for channel in REQUIRED_CHANNELS: response = requests.get(f"{TELEGRAM_API_URL}/getChatMember", params={ "chat_id": channel, "user_id": user_id }) data = response.json() if data.get("result", {}).get("status") not in ["member", "administrator", "creator"]: return False return True

def get_user(chat_id): user = users_collection.find_one({"chat_id": chat_id}) if not user: users_collection.insert_one({"chat_id": chat_id, "balance": 0, "withdrawals_today": 0}) return {"chat_id": chat_id, "balance": 0, "withdrawals_today": 0} return user

---------------------- Routes ----------------------

@app.route("/webhook", methods=["POST"]) def webhook(): if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET_TOKEN: return "Unauthorized", 403

update = request.get_json()

if "message" in update:
    message = update["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    if not is_user_in_channels(chat_id):
        send_message(chat_id, "❌ Please join all the channels before verifying.")
        return jsonify(status="not_verified")

    if text == "/start":
        send_message(chat_id, "👋 Welcome to Actualearn! You have successfully joined all channels.")

    elif text == "/balance":
        user = get_user(chat_id)
        send_message(chat_id, f"💰 Your balance is ₹{user['balance']}")

    elif text == "/withdraw":
        user = get_user(chat_id)
        if user["balance"] < MIN_WITHDRAW_AMOUNT:
            send_message(chat_id, f"❌ Minimum withdrawal is ₹{MIN_WITHDRAW_AMOUNT}.")
        elif user["withdrawals_today"] >= DAILY_WITHDRAW_LIMIT:
            send_message(chat_id, "❌ You have reached your daily withdrawal limit.")
        else:
            new_balance = user["balance"] - MIN_WITHDRAW_AMOUNT
            users_collection.update_one(
                {"chat_id": chat_id},
                {"$set": {"balance": new_balance}, "$inc": {"withdrawals_today": 1}}
            )
            send_message(chat_id, f"✅ ₹{MIN_WITHDRAW_AMOUNT} withdrawn successfully!")

return jsonify(status="ok")

@app.route("/", methods=["GET"]) def home(): return "✅ Actualearn Bot is Live", 200

---------------------- Main ----------------------

if name == "main": app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

