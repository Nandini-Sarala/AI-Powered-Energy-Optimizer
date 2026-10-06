from pymongo import MongoClient

client = MongoClient("mongodb+srv://kanishkagurav52_db_user:d1pG7Da8zneyRt1W@cluster0.syt7gcz.mongodb.net/energy_optimizer")
db = client.energy_optimizer
db.users.update_many({}, {"$set": {"reward_wallet_balance": 0.0, "last_closed_month": ""}})
print("All wallets reset!")
