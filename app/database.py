from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")


def get_database(db_name: str):
    client = AsyncIOMotorClient(MONGO_URI, tls=True, serverSelectionTimeoutMS=10000)

    db = client[db_name]

    return {
        "client": client,
        "accounts": db.accounts,
        "transactions": db.transactions,
        "bank_name": db_name,
    }
