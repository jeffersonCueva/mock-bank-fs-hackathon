"""
Seed sample user accounts for BPI and GCash banks
Run this script to populate initial test data
"""

from app.database import get_database
import asyncio
import uuid

SAMPLE_USERS = {
    "bpi": [
        {
            "account_id": "BPI001",
            "name": "John Smith",
            "balance": 50000,
            "bank_name": "bpi",
            "id": str(uuid.uuid4()),
        },
        {
            "account_id": "BPI002",
            "name": "Maria Garcia",
            "balance": 35000,
            "bank_name": "bpi",
            "id": str(uuid.uuid4()),
        },
        {
            "account_id": "BPI003",
            "name": "Carlos Rodriguez",
            "balance": 75000,
            "bank_name": "bpi",
            "id": str(uuid.uuid4()),
        },
    ],
    "gcash": [
        {
            "account_id": "GCASH001",
            "name": "Ana Santos",
            "balance": 25000,
            "bank_name": "gcash",
            "id": str(uuid.uuid4()),
        },
        {
            "account_id": "GCASH002",
            "name": "Miguel Lopez",
            "balance": 45000,
            "bank_name": "gcash",
            "id": str(uuid.uuid4()),
        },
        {
            "account_id": "GCASH003",
            "name": "Rosa Flores",
            "balance": 60000,
            "bank_name": "gcash",
            "id": str(uuid.uuid4()),
        },
    ],
}


async def seed_users():
    """Insert sample users into both banks' databases"""
    
    for bank_name, users in SAMPLE_USERS.items():
        print(f"\n{'='*50}")
        print(f"Seeding {bank_name.upper()} database...")
        print(f"{'='*50}")
        
        try:
            db = get_database(bank_name)
            accounts = db["accounts"]
            
            for user in users:
                # Check if user already exists
                existing = await accounts.find_one(
                    {"account_id": user["account_id"], "bank_name": bank_name}
                )
                
                if existing:
                    print(f"⏭️  Account {user['account_id']} already exists, skipping...")
                else:
                    # Insert new user
                    await accounts.insert_one(user)
                    print(f"✅ Created account: {user['account_id']} ({user['name']}) - Balance: PHP {user['balance']:,}")
                    
        except Exception as e:
            print(f"❌ Error seeding {bank_name}: {e}")
    
    print(f"\n{'='*50}")
    print("✨ Sample users seeding complete!")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    asyncio.run(seed_users())
