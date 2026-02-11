from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from app.models import TransferRequest
from app.utils.billers import get_billers
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
                "id": str(uuid.uuid4()),
                "bank_name": bank_name,
                "account_id": account_id,
                "type": "CREDIT",
                "amount": amount,
                "description": f"Inter-bank transfer from {data.get('from_bank', 'external')}",
                "timestamp": now.isoformat(),
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
                    "id": str(uuid.uuid4()),
                    "account": req.from_account,
                    "type": "debit",
                    "amount": req.amount,
                    "counterparty": req.to_account,
                    "counterparty_bank": req.to_bank,
                    "bank": bank_name,
                    "description": f"Transfer to {req.to_account} ({req.to_bank})",
                    "timestamp": now.isoformat(),
                }
            )

        # Credit ONLY if:
        # - same-bank transfer OR
        # - incoming interbank transfer
        print(f"from bank {req.from_bank}, to bank: {req.to_bank}, bank: {bank_name}")
        if req.to_bank == bank_name:
            transactions.insert_one(
                {
                    "id": str(uuid.uuid4()),
                    "account": req.to_account,
                    "type": "credit",
                    "amount": req.amount,
                    "counterparty": req.from_account,
                    "counterparty_bank": req.from_bank,
                    "bank": bank_name,
                    "description": f"Transfer from {req.from_account} ({req.from_bank})",
                    "timestamp": now.isoformat(),
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

    @router.get("/supported-billers")
    async def get_supported_billers():
        """
        Get list of supported billers for this bank
        """
        billers = get_billers(bank_name)
        return billers

    @router.post("/bill-payment")
    async def bill_payment(data: dict):
        """
        Process a bill payment for a customer.
        Required fields: account_holder, biller_code, reference_number, amount
        """
        print(f"\n{'='*60}")
        print(f"📨 Bill Payment Request Received")
        print(f"{'='*60}")
        print(f"Request data: {data}")
        print(f"API Bank: {bank_name}")
        
        account_holder = data.get("account_holder", "").upper()
        biller_code = data.get("biller_code", "").upper()
        reference_number = data.get("reference_number")
        amount = data.get("amount")

        print(f"Parsed - Account: {account_holder}, Biller: {biller_code}, Ref: {reference_number}, Amount: {amount}")

        # Validate required fields
        if not all([account_holder, biller_code, reference_number, amount]):
            error_msg = "Missing required fields: account_holder, biller_code, reference_number, amount"
            print(f"❌ {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        # Check if account exists
        print(f"🔍 Checking account {account_holder} in {bank_name} database...")
        acc = await accounts.find_one(
            {"account_id": account_holder, "bank_name": bank_name}
        )
        if not acc:
            error_msg = f"Account {account_holder} not found"
            print(f"❌ {error_msg}")
            raise HTTPException(status_code=404, detail=error_msg)
        print(f"✅ Account found: {account_holder}")

        # Check if biller is supported by this bank
        print(f"🔍 Loading billers for {bank_name}...")
        billers = get_billers(bank_name)
        print(f"Available billers: {list(billers.keys())}")
        
        # Use case-insensitive lookup - normalize both the input and keys to uppercase
        biller_code_normalized = biller_code.upper()
        billers_normalized = {k.upper(): v for k, v in billers.items()}
        
        if biller_code_normalized not in billers_normalized:
            error_msg = f"Biller {biller_code} not supported. Supported billers: {list(billers.keys())}"
            print(f"❌ {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
        print(f"✅ Biller {biller_code} supported")

        # Check sufficient balance
        print(f"💰 Account balance: PHP {acc['balance']:,}, Payment amount: PHP {amount:,}")
        if acc["balance"] < amount:
            error_msg = "Insufficient funds"
            print(f"❌ {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        # Debit the account
        print(f"💳 Debiting PHP {amount:,} from {account_holder}...")
        await accounts.update_one(
            {"account_id": account_holder, "bank_name": bank_name},
            {"$inc": {"balance": -amount}},
        )

        # Record transaction
        biller_name = billers_normalized[biller_code_normalized].get("name", biller_code)
        await transactions.insert_one(
            {
                "id": str(uuid.uuid4()),
                "account": account_holder,
                "type": "debit",
                "amount": amount,
                "counterparty": biller_code_normalized,
                "counterparty_bank": "external",
                "bank": bank_name,
                "description": f"Bill payment to {biller_name} (Ref: {reference_number})",
                "timestamp": now.isoformat(),
            }
        )
        print(f"✅ Transaction recorded")
        print(f"{'='*60}\n")

        return {
            "message": "Bill payment completed successfully",
            "biller": biller_name,
            "reference_number": reference_number,
            "amount": amount,
        }

    return router
