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
