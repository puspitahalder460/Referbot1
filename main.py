from flask import Flask, request
import requests
import pymongo
import datetime

TOKEN = "YOUR_BOT_TOKEN"
BOT_URL = f"https://api.telegram.org/bot{TOKEN}"
VERIFY_CHANNEL_ID = -1001234567890  # Replace with your channel ID
MONGO_URI = "YOUR_MONGO_DB_URL"

REWARD_AMOUNT = 2
MIN_WITHDRAW = 16

client = pymongo.MongoClient(MONGO_URI)
db = client["actualearn"]
users_col = db["users"]
withdrawals_col = db["withdrawals"]

app = Flask(__name__)

def send_message(chat_id, text):
    url = f"{BOT_URL}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def is_user_in_channel(user_id):
    url = f"{BOT_URL}/getChatMember"
    params = {"chat_id": VERIFY_CHANNEL_ID, "user_id": user_id}
    res = requests.get(url, params=params).json()
    status = res.get("result", {}).get("status", "")
    return status in ["member", "administrator", "creator"]

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        msg = data["message"]
        text = msg.get("text", "")
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        name = msg["from"].get("first_name", "")

        user = users_col.find_one({"user_id": user_id})
        if not user:
            users_col.insert_one({"user_id": user_id, "balance": 0, "referrals": [], "joined": datetime.datetime.utcnow()})

        if text.startswith("/start"):
            parts = text.split()
            if len(parts) == 2:
                referrer_id = int(parts[1])
                if referrer_id != user_id:
                    referrer = users_col.find_one({"user_id": referrer_id})
                    if referrer and user_id not in referrer.get("referrals", []):
                        if is_user_in_channel(user_id):
                            users_col.update_one(
                                {"user_id": referrer_id},
                                {"$inc": {"balance": REWARD_AMOUNT}, "$push": {"referrals": user_id}}
                            )
                            send_message(referrer_id, f"🎉 You earned ₹{REWARD_AMOUNT} from a new verified referral!")
            send_message(chat_id, "👋 Welcome to Actualearn! Use /balance to check your wallet or /withdraw to request a withdrawal.")

        elif text.startswith("/balance"):
            user = users_col.find_one({"user_id": user_id})
            balance = user.get("balance", 0)
            send_message(chat_id, f"💰 Your current balance: ₹{balance}")

        elif text.startswith("/withdraw"):
            user = users_col.find_one({"user_id": user_id})
            balance = user.get("balance", 0)
            if balance >= MIN_WITHDRAW:
                today = datetime.datetime.utcnow().date()
                already_withdrew = withdrawals_col.find_one({
                    "user_id": user_id,
                    "date": today
                })
                if already_withdrew:
                    send_message(chat_id, "⚠️ You can withdraw only once per day.")
                else:
                    withdrawals_col.insert_one({
                        "user_id": user_id,
                        "amount": balance,
                        "date": today,
                        "status": "pending"
                    })
                    users_col.update_one({"user_id": user_id}, {"$set": {"balance": 0}})
                    send_message(chat_id, f"✅ Withdrawal of ₹{balance} requested. You will receive it soon.")
            else:
                send_message(chat_id, f"❌ Minimum ₹{MIN_WITHDRAW} required to withdraw.")

    return "ok"

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
