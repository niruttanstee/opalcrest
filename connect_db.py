from pymongo import MongoClient
import json

async def db_client():
    """
    Connects to MongoDB server.

    Returns:
       client: MongoClient
    """
    # Import token.
    with open('./tokens.json', 'r') as f:
        tokens = json.load(f)
        
    uri = tokens['ATLAS_URI']
    client = MongoClient(uri)

    return client