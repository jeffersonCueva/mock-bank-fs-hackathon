# Mock Bank FS Hackathon

A multi-service FastAPI project that simulates two banks (`gcash`, `bpi`) and a clearing house for inter-bank transfers.

## What This Repository Is For

This repository is a sandbox for:
- same-bank transfers
- inter-bank transfers through a clearing house
- bill payments with idempotency support
- transaction history and balance checks
- bank-specific biller catalogs

It is intended for local development, demos, and backend experimentation.

## How It Works

The system runs **3 API servers**:

1. `gcash` bank API on `http://localhost:8000`
2. `bpi` bank API on `http://localhost:8001`
3. clearing house API on `http://localhost:9000`

### Flow overview

1. Each bank API reads/writes from its own Cosmos DB database:
   - `${COSMOS_DATABASE_PREFIX}-gcash`
   - `${COSMOS_DATABASE_PREFIX}-bpi`
2. Same-bank transfer:
   - client calls `POST /transfer` on a bank
   - sender is debited
   - receiver in the same bank is credited
3. Inter-bank transfer:
   - client calls `POST /interbank-transfer` on clearing house
   - clearing house calls source bank `POST /transfer` (debit)
   - clearing house calls destination bank `POST /internal/credit` (credit)
4. Bill payment:
   - client calls `POST /bill-payment` on a bank
   - bank validates supported biller from `data/billers/<bank>_billers.json`
   - account is debited and transaction is recorded
   - optional `idempotency_key` prevents duplicate processing

## Tech Stack

- Python 3.13
- FastAPI + Uvicorn
- Azure Cosmos DB (`azure-cosmos` SDK)
- `httpx` for service-to-service calls

## Project Structure

```text
app/
  main.py                   # Bank app factory
  database.py               # Cosmos DB connection + container wrapper
  models.py                 # Request models
  routes/
    accounts.py             # Balance endpoints
    transactions.py         # Transfers + transaction history + internal credit
    pay_bills.py            # Bill payment + supported billers
  utils/billers.py          # Loads bank billers from JSON

clearing_house/main.py      # Inter-bank transfer orchestrator
run_bank_gcash.py           # GCash entrypoint
run_bank_bpi.py             # BPI entrypoint
seed_sample_users.py        # Seeds sample accounts
data/billers/*.json         # Supported billers per bank
run_all_mac.sh              # Starts 3 services on macOS Terminal
run_all.bat                 # Starts 3 services on Windows CMD
```

## Prerequisites

- Python `3.13.x`
- An Azure Cosmos DB account with endpoint + key
- `git`

## Environment Setup

Create a `.env` file in the project root:

```dotenv
COSMOS_ENDPOINT="https://<your-account>.documents.azure.com:443/"
COSMOS_KEY="<your-cosmos-key>"
COSMOS_DATABASE_PREFIX="mock-bank-db"
```

Notes:
- `COSMOS_ENDPOINT` and `COSMOS_KEY` are required.
- `COSMOS_DATABASE_PREFIX` is optional; default is `mock-bank-db`.
- Do not commit real secrets.

## Installation

```bash
git clone https://github.com/jeffersonCueva/mock-bank-fs-hackathon.git
cd mock-bank-fs-hackathon
```

| OS / Shell | Setup commands |
| --- | --- |
| macOS (zsh/bash) | `python3.13 -m venv .venv`<br>`source .venv/bin/activate`<br>`pip install -r requirements.txt` |
| Linux (bash) | `python3.13 -m venv .venv`<br>`source .venv/bin/activate`<br>`pip install -r requirements.txt` |
| Windows (PowerShell) | `py -3.13 -m venv .venv`<br>`.\\.venv\\Scripts\\Activate.ps1`<br>`pip install -r requirements.txt` |
| Windows (Command Prompt) | `py -3.13 -m venv .venv`<br>`.venv\\Scripts\\activate`<br>`pip install -r requirements.txt` |

## Seed Sample Data

After environment setup:

```bash
python seed_sample_users.py
```

This creates sample accounts for both banks if they do not already exist.

## Run the Services

### Option A: One-command launcher scripts

| OS | Command(s) |
| --- | --- |
| macOS | `chmod +x run_all_mac.sh`<br>`./run_all_mac.sh` |
| Linux | Use Option B (manual start). `run_all_mac.sh` uses AppleScript/Terminal integration. |
| Windows (CMD/PowerShell) | `run_all.bat` |

Windows note:
- `run_all.bat` currently activates `mock_bank\Scripts\activate`.
- If your venv is `.venv`, update that line to: `call .venv\Scripts\activate`

### Option B: Manual start (all OS)

| Service | macOS / Linux | Windows (CMD) |
| --- | --- | --- |
| GCash API (`:8000`) | `BANK_NAME=gcash python -m uvicorn run_bank_gcash:app --port 8000 --reload` | `set BANK_NAME=gcash && python -m uvicorn run_bank_gcash:app --port 8000 --reload` |
| BPI API (`:8001`) | `BANK_NAME=bpi python -m uvicorn run_bank_bpi:app --port 8001 --reload` | `set BANK_NAME=bpi && python -m uvicorn run_bank_bpi:app --port 8001 --reload` |
| Clearing House (`:9000`) | `python -m uvicorn clearing_house.main:app --port 9000 --reload` | `python -m uvicorn clearing_house.main:app --port 9000 --reload` |

## API Quick Checks

Swagger docs:
- `http://localhost:8000/docs` (GCash)
- `http://localhost:8001/docs` (BPI)
- `http://localhost:9000/docs` (Clearing House)

### Swagger-first test flow

1. Open one of the `/docs` URLs.
2. Click `Try it out` on the target endpoint.
3. For `POST` endpoints, paste the matching JSON body below.
4. Click `Execute`.

### Endpoint matrix

| Use case | Service | Method | Path |
| --- | --- | --- | --- |
| Check balance | GCash/BPI | `GET` | `/balance/{account_id}` |
| Same-bank transfer | GCash/BPI | `POST` | `/transfer` |
| Inter-bank transfer | Clearing House | `POST` | `/interbank-transfer` |
| Bill payment | GCash/BPI | `POST` | `/bill-payment` |
| Supported billers | GCash/BPI | `GET` | `/supported-billers` |
| Transaction history | GCash/BPI | `GET` | `/transactions/{user_id}` |

### Request body templates (paste into Swagger)

`POST /transfer` (same-bank transfer)

```json
{
  "from_account": "GCASH001",
  "to_account": "GCASH002",
  "amount": 500,
  "to_bank": "gcash",
  "from_bank": "gcash"
}
```

`POST /interbank-transfer` (clearing house)

```json
{
  "from_bank": "gcash",
  "to_bank": "bpi",
  "from_account": "GCASH001",
  "to_account": "BPI001",
  "amount": 1200
}
```

`POST /bill-payment`

```json
{
  "account_holder": "BPI001",
  "biller_code": "MERALCO",
  "reference_number": "INV-1001",
  "amount": 350,
  "idempotency_key": "demo-payment-001"
}
```

### Optional CLI quick checks (`curl`)

```bash
curl http://localhost:8000/balance/GCASH001
```

## Supported Billers

Bank billers are loaded from JSON files:
- `data/billers/gcash_billers.json`
- `data/billers/bpi_billers.json`

To add a biller, edit the appropriate file and restart the target bank API.

## Common Issues

1. `COSMOS_ENDPOINT and COSMOS_KEY must be set`
- `.env` is missing or malformed.
- Confirm values are loaded in your shell.

2. `COSMOS_KEY appears invalid (base64 decode failed)`
- Remove extra spaces/newlines in `COSMOS_KEY`.

3. `Account not found`
- Run `python seed_sample_users.py`.
- Use uppercase account IDs like `GCASH001`, `BPI001`.

4. Port already in use
- Stop existing processes using `8000`, `8001`, `9000`.

5. Windows launcher fails on activate
- Update `run_all.bat` activation path to your actual venv.

## Developer Notes

- This codebase currently contains debug `print()` logs designed for demo visibility.
- Cosmos DB containers are auto-created per bank database (`accounts`, `transactions`).
- If you reset data, use a new `COSMOS_DATABASE_PREFIX` or clear Cosmos containers manually.

## License

Hackathon/demo project. Provided as-is.
