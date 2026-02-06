from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from app.models import TransferRequest
import uuid
import httpx
import os


def get_transactions_router(accounts, transactions, client, bank_name: str):
    router = APIRouter(tags=["Transactions"])

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
        txns_cursor = transactions.find({"account": user_id}).sort("timestamp", -1)
        txns = await txns_cursor.to_list(length=100)  # limit to last 100 transactions

        # Optional: convert ObjectId to string
        for txn in txns:
            txn["_id"] = str(txn["_id"])

        return {
            "account_id": user_id,
            "name": user.get("name"),
            "bank_name": user.get("bank_name"),
            "transactions": txns,
        }

    @router.post("/internal/credit")
    async def internal_credit(data: dict):
        account_id = data["account_id"]
        amount = data["amount"]

        acc = await accounts.find_one(
            {"account_id": account_id, "bank_name": bank_name}
        )

        if not acc:
            raise HTTPException(status_code=404, detail="Account not found")

        await accounts.update_one(
            {"account_id": account_id, "bank_name": bank_name},
            {"$inc": {"balance": amount}},
        )

        await transactions.insert_one(
            {
                "bank_name": bank_name,
                "txn_id": str(uuid.uuid4()),
                "account_id": account_id,
                "type": "CREDIT",
                "amount": amount,
                "description": f"Inter-bank transfer from {data.get('from_bank', 'external')}",
                "timestamp": now,
            }
        )

        return {"status": "credited"}

    @router.post("/transfer")
    async def transfer_funds(req: TransferRequest):
        sender = await accounts.find_one(
            {"account_id": req.from_account, "bank_name": bank_name}
        )

        receiver = await accounts.find_one(
            {"account_id": req.to_account, "bank_name": bank_name}
        )

        if not sender:
            raise HTTPException(status_code=404, detail="Sender not found")

        if sender["balance"] < req.amount:
            raise HTTPException(status_code=400, detail="Insufficient funds")
        if req.to_bank == bank_name:
            if not receiver:
                raise HTTPException(status_code=404, detail="Receiver not found")

        # Build human-readable description
        if req.to_bank and req.to_bank != bank_name:
            description = f"Inter-bank transfer to {req.to_bank} / {req.to_account}"
        else:
            description = f"Transfer to {req.to_account}"

        # Always debit if THIS bank is the sender
        if req.from_bank == bank_name:

            await accounts.update_one(
                {"account_id": req.from_account, "bank_name": bank_name},
                {"$inc": {"balance": -req.amount}},
            )
            transactions.insert_one(
                {
                    "account": req.from_account,
                    "type": "debit",
                    "amount": req.amount,
                    "counterparty": req.to_account,
                    "counterparty_bank": req.to_bank,
                    "bank": bank_name,
                    "description": f"Transfer to {req.to_account} ({req.to_bank})",
                    "timestamp": now,
                }
            )

        # Credit ONLY if:
        # - same-bank transfer OR
        # - incoming interbank transfer
        print(f"from bank {req.from_bank}, to bank: {req.to_bank}, bank: {bank_name}")
        if req.to_bank == bank_name:
            transactions.insert_one(
                {
                    "account": req.to_account,
                    "type": "credit",
                    "amount": req.amount,
                    "counterparty": req.from_account,
                    "counterparty_bank": req.from_bank,
                    "bank": bank_name,
                    "description": f"Transfer from {req.from_account} ({req.from_bank})",
                    "timestamp": now,
                }
            )

            await accounts.update_one(
                {"account_id": req.to_account, "bank_name": bank_name},
                {"$inc": {"balance": req.amount}},
            )

            return {
                "status": "Transaction Completed",
                "inter_bank": False,
            }

        return {
            "status": "debited",
            "inter_bank": bool(req.to_bank and req.to_bank != bank_name),
        }

    return router
