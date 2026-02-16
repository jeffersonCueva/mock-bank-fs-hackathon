from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from app.models import TransferRequest, BillPaymentRequest
from app.utils.billers import get_billers
import uuid
import httpx
import os


def get_pay_bills_router(accounts, transactions, client, bank_name: str):
    router = APIRouter(tags=["Pay Bills"])
    bank_name = bank_name.lower()

    now = datetime.now(timezone.utc)
    print(bank_name)

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
        Optional field: idempotency_key (for idempotent requests)
        """
        print(f"\n{'='*60}")
        print("📨 Bill Payment Request Received")
        print(f"{'='*60}")
        print(f"Request data: {data}")
        print(f"API Bank: {bank_name}")

        account_holder = data.get("account_holder", "").upper()
        biller_code = data.get("biller_code", "").upper()
        reference_number = data.get("reference_number")
        amount = data.get("amount")
        idempotency_key = data.get("idempotency_key")

        print(
            f"Parsed - Account: {account_holder}, Biller: {biller_code}, Ref: {reference_number}, Amount: {amount}"
        )

        # Validate required fields
        if not all([account_holder, biller_code, reference_number, amount]):
            error_msg = "Missing required fields: account_holder, biller_code, reference_number, amount"
            print(f"❌ {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        # Check for duplicate request using idempotency key
        if idempotency_key:
            print(f"🔑 Idempotency key provided: {idempotency_key}")
            existing_transaction = await transactions.find_one(
                {"idempotency_key": idempotency_key, "bank": bank_name}
            )
            if existing_transaction:
                print(f"✅ Duplicate request detected. Returning cached response.")
                return {
                    "message": "Duplicate payment request detected. Previous payment already processed.",
                    "biller": existing_transaction.get("counterparty"),
                    "reference_number": existing_transaction.get("reference_number"),
                    "amount": existing_transaction.get("amount"),
                    "duplicate": True,
                }
            print(f"✅ Idempotency key is new. Processing payment...")
        else:
            print(f"⚠️  No idempotency key provided. Request is not idempotent.")

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
        print(
            f"💰 Account balance: PHP {acc['balance']:,}, Payment amount: PHP {amount:,}"
        )
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
        biller_name = billers_normalized[biller_code_normalized].get(
            "name", biller_code
        )
        transaction_record = {
            "id": str(uuid.uuid4()),
            "account_id": account_holder,
            "type": "bill_payment",
            "amount": amount,
            "counterparty": biller_code_normalized,
            "counterparty_bank": "external",
            "bank": bank_name,
            "description": f"Bill payment to {biller_name} (Ref: {reference_number})",
            "timestamp": now.isoformat(),
            "reference_number": reference_number,
        }
        if idempotency_key:
            transaction_record["idempotency_key"] = idempotency_key
        await transactions.insert_one(transaction_record)
        print("✅ Transaction recorded")
        print(f"{'='*60}\n")

        return {
            "message": "Bill payment completed successfully",
            "biller": biller_name,
            "reference_number": reference_number,
            "amount": amount,
        }

    return router
