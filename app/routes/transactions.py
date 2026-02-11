from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from app.models import TransferRequest
from app.utils.billers import get_billers
import uuid
import httpx
import os


def get_transactions_router(accounts, transactions, client, bank_name: str):
    router = APIRouter(tags=["Transactions"])
    bank_name = bank_name.lower()

    now = datetime.now(timezone.utc)
    print(bank_name)

    @router.get("/transactions/{user_id}")
    async def get_transaction_history(user_id: str):
        """
        Get all transactions for a given user (both debit and credit)
        """
        # Check if user exists
        user = await accounts.find_one({"account_id": user_id})
        if not user:
            raise HTTPException(status_code=404, detail="Account not found")

        # Fetch all transactions for this account
        transactionlist = await transactions.find({"account_id": user_id})

        return {
            "account_id": user_id,
            "name": user.get("name"),
            "bank_name": user.get("bank_name"),
            "transactions": transactionlist,
        }

    @router.post("/internal/credit")
    async def internal_credit(data: dict):

        print(f"\n{'='*60}")
        print("📨 Internal Credit Initiated")
        print(f"{'='*60}")
        print(f"Request data: {data}")
        print(f"API Bank: {bank_name}")

        account_id = data["account_id"]
        amount = data["amount"]
        print(f"🔍 Checking account {account_id} in {bank_name} database...")
        acc = await accounts.find_one(
            {"account_id": account_id, "bank_name": bank_name}
        )

        if not acc:
            error_msg = f"Account {account_id} not found"
            print(f"❌ {error_msg}")
            raise HTTPException(status_code=404, detail="Account not found")
        print(f"✅ Account found: {account_id}")

        await accounts.update_one(
            {"account_id": account_id, "bank_name": bank_name},
            {"$inc": {"balance": amount}},
        )

        print(
            f"✅ Credit Successful. {amount} to {account_id} in {bank_name} database..."
        )

        await transactions.insert_one(
            {
                "id": str(uuid.uuid4()),
                "bank": bank_name,
                "account_id": account_id,
                "type": "CREDIT",
                "amount": amount,
                "description": f"Inter-bank transfer from {data.get('from_bank', 'external')}",
                "timestamp": now.isoformat(),
            }
        )

        print("✅ Transaction recorded")
        print(f"{'='*60}\n")

        return {"status": "credited"}

    @router.post("/transfer")
    async def transfer_funds(req: TransferRequest):
        to_bank = req.to_bank.lower()

        print(f"\n{'='*60}")
        print("📨 Transfer Initiated")
        print(f"{'='*60}")
        print(f"Request data: {req}")
        print(f"API Bank: {bank_name}")

        account_name = req.from_account
        print(f"🔍 Checking account {account_name} in {bank_name} database...")
        sender = await accounts.find_one(
            {"account_id": req.from_account, "bank_name": bank_name}
        )
        if not sender:
            error_msg = f"Account {account_name} not found"
            print(f"❌ {error_msg}")
            raise HTTPException(status_code=404, detail="Sender not found")

        print(f"✅ Account found: {account_name}")

        receiver = await accounts.find_one(
            {"account_id": req.to_account, "bank_name": bank_name}
        )

        if sender["balance"] < req.amount:
            raise HTTPException(status_code=400, detail="Insufficient funds")
        if to_bank == bank_name:
            receiver_name = req.to_account
            print(f"🔍 Checking account {receiver_name} in {bank_name} database...")
            if not receiver:
                error_msg = f"Account {receiver_name} not found"
                print(f"❌ {error_msg}")
                raise HTTPException(status_code=404, detail="Receiver not found")
            print(f"✅ Account found: {receiver_name}")

        # Build human-readable description
        if to_bank and to_bank != bank_name:
            description = f"Inter-bank transfer to {to_bank} / {req.to_account}"
        else:
            description = f"Transfer to {req.to_account}"
        await accounts.update_one(
            {"account_id": req.from_account, "bank_name": bank_name},
            {"$inc": {"balance": -req.amount}},
        )
        print(
            f"✅ Debit Successful. {req.amount} from {account_name} in {bank_name} database..."
        )

        await transactions.insert_one(
            {
                "id": str(uuid.uuid4()),
                "account_id": req.from_account,
                "type": "debit",
                "amount": req.amount,
                "counterparty": req.to_account,
                "counterparty_bank": to_bank,
                "bank": bank_name,
                "description": description,
                "timestamp": now.isoformat(),
            }
        )

        print(f"✅ Transaction Added")

        # Credit ONLY if:
        # - same-bank transfer OR
        # - incoming interbank transfer
        print(f"from bank {req.from_bank}, to bank: {to_bank}, bank: {bank_name}")
        if to_bank == bank_name:
            await accounts.update_one(
                {"account_id": req.to_account, "bank_name": bank_name},
                {"$inc": {"balance": req.amount}},
            )

            print(
                f"✅ Credit Successful. {req.amount} to {req.to_account} in {bank_name} database..."
            )
            await transactions.insert_one(
                {
                    "id": str(uuid.uuid4()),
                    "account_id": req.to_account,
                    "type": "credit",
                    "amount": req.amount,
                    "counterparty": req.from_account,
                    "counterparty_bank": req.from_bank,
                    "bank": bank_name,
                    "description": f"Transfer from {req.from_account} ({req.from_bank})",
                    "timestamp": now.isoformat(),
                }
            )

            print("✅ Transaction recorded")
            print(f"{'='*60}\n")

            return {
                "status": "Transaction Completed",
                "inter_bank": False,
            }
        print(f"{'='*60}\n")
        return {
            "status": "debited",
            "inter_bank": bool(to_bank and to_bank != bank_name),
        }

    return router
