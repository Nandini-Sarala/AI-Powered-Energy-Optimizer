# from pymongo import MongoClient

# client = MongoClient("mongodb+srv://kanishkagurav52_db_user:d1pG7Da8zneyRt1W@cluster0.syt7gcz.mongodb.net/energy_optimizer")
# db = client.energy_optimizer
import os
from dotenv import load_dotenv
from pymongo import MongoClient
# Load the variables from the .env file
load_dotenv()
# Grab the MONGO_URI string automatically
client = MongoClient(os.getenv("MONGO_URI"))
db = client.get_default_database()
db.users.update_many({}, {"$set": {"reward_wallet_balance": 0.0, "last_closed_month": ""}})
print("All wallets reset!")
