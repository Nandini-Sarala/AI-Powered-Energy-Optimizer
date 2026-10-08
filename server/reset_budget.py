import os
from pymongo import MongoClient

def reset_daily_usage():
    client = MongoClient('mongodb://localhost:27017/')
    db = client['energy_optimizer']
    
    result = db.appliances.update_many(
        {},
        {
            "$set": {
                "accumulatedKwhToday": 0.0,
                "lockedBySystem": False,
                "lockReason": None,
                "lockDate": None,
                "status": False,
                "active": 0
            }
        }
    )
    print(f"Reset {result.modified_count} appliances for testing.")

if __name__ == "__main__":
    reset_daily_usage()
