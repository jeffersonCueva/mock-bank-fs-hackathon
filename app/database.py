from azure.cosmos import CosmosClient, PartitionKey
from dotenv import load_dotenv
import os
import base64

load_dotenv()

# Azure Cosmos DB connection details
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
# Strip whitespace/newlines from the key to avoid base64 padding errors
COSMOS_KEY = os.getenv("COSMOS_KEY", "").strip()
COSMOS_DATABASE_PREFIX = os.getenv("COSMOS_DATABASE_PREFIX", "mock-bank-db")

if not COSMOS_ENDPOINT or not COSMOS_KEY:
    raise RuntimeError("COSMOS_ENDPOINT and COSMOS_KEY must be set in your environment variables.")

# Validate that COSMOS_KEY looks like valid base64 to provide a clearer error
try:
    base64.b64decode(COSMOS_KEY)
except Exception:
    raise RuntimeError(
        "COSMOS_KEY appears invalid (base64 decode failed). Check for extra spaces/newlines and ensure the key is correct."
    )

# Initialize Cosmos Client
cosmos_client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)


class CosmosContainer:
    """Wrapper to provide MongoDB-like interface for Azure Cosmos DB operations"""
    
    def __init__(self, container):
        self.container = container
    
    async def find_one(self, query: dict, projection: dict = None):
        """Find a single document matching query"""
        try:
            # Build SQL query from dict query
            sql_query = self._build_sql_where(query)
            items = list(self.container.query_items(query=sql_query, enable_cross_partition_query=True))
            return items[0] if items else None
        except Exception as e:
            print(f"Error in find_one: {e}")
            return None
    
    async def find(self, query: dict):
        """Find multiple documents matching query"""
        try:
            sql_query = self._build_sql_where(query)
            return self.container.query_items(query=sql_query, enable_cross_partition_query=True)
        except Exception as e:
            print(f"Error in find: {e}")
            return []
    
    async def insert_one(self, document: dict):
        """Insert a single document"""
        try:
            return self.container.create_item(body=document)
        except Exception as e:
            print(f"Error in insert_one: {e}")
            raise
    
    async def update_one(self, query: dict, update: dict):
        """Update a single document"""
        try:
            # Get the document first
            item = await self.find_one(query)
            if not item:
                return None
            
            # Apply update operations
            if "$inc" in update:
                for field, value in update["$inc"].items():
                    item[field] = item.get(field, 0) + value
            elif "$set" in update:
                for field, value in update["$set"].items():
                    item[field] = value
            else:
                item.update(update)
            
            # Replace the item
            return self.container.replace_item(item=item["id"], body=item)
        except Exception as e:
            print(f"Error in update_one: {e}")
            raise
    
    def _build_sql_where(self, query: dict) -> str:
        """Convert MongoDB-style query dict to SQL WHERE clause"""
        conditions = []
        for key, value in query.items():
            if isinstance(value, str):
                conditions.append(f"c.{key} = '{value}'")
            elif isinstance(value, (int, float)):
                conditions.append(f"c.{key} = {value}")
            elif value is None:
                conditions.append(f"c.{key} IS NULL")
            else:
                conditions.append(f"c.{key} = {repr(value)}")
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return f"SELECT * FROM c WHERE {where_clause}"


def get_database(db_name: str):
    try:
        # Create database name from bank name: "bpi" → "mock-bank-db-bpi"
        database_name = f"{COSMOS_DATABASE_PREFIX}-{db_name.lower()}"
        
        # Get or create database
        try:
            database = cosmos_client.get_database_client(database_name)
            # Try to read to verify it exists
            database.read()
            print(f"✅ Using existing database: {database_name}")
        except Exception:
            # Database doesn't exist, create it
            print(f"📦 Creating database: {database_name}")
            database = cosmos_client.create_database(database_name)
        
        # Get or create accounts container
        try:
            accounts_container = database.get_container_client("accounts")
            accounts_container.read()
            print(f"✅ Using existing container: accounts")
        except Exception:
            print(f"📦 Creating container: accounts")
            accounts_container = database.create_container(
                id="accounts",
                partition_key=PartitionKey(path="/bank_name")
            )
        
        # Get or create transactions container
        try:
            transactions_container = database.get_container_client("transactions")
            transactions_container.read()
            print(f"✅ Using existing container: transactions")
        except Exception:
            print(f"📦 Creating container: transactions")
            transactions_container = database.create_container(
                id="transactions",
                partition_key=PartitionKey(path="/bank_name")
            )
        
        return {
            "client": cosmos_client,
            "accounts": CosmosContainer(accounts_container),
            "transactions": CosmosContainer(transactions_container),
            "bank_name": db_name,
        }
    except Exception as e:
        print(f"Error connecting to Cosmos DB: {e}")
        raise
