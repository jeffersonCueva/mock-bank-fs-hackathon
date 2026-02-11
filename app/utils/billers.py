import json
import os
from pathlib import Path

def get_billers(bank_name: str) -> dict:
    """
    Load billers for a specific bank from JSON file.
    Returns empty dict if bank file not found.
    """
    billers_dir = Path(__file__).parent.parent.parent / "data" / "billers"
    biller_file = billers_dir / f"{bank_name.lower()}_billers.json"
    
    if not biller_file.exists():
        return {}
    
    try:
        with open(biller_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading billers for {bank_name}: {e}")
        return {}
