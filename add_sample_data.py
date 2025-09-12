#!/usr/bin/env python3
"""Add sample data to AstraDB collections for testing"""

import os
from dotenv import load_dotenv
from langchain_astradb import AstraDBVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document

# Load environment variables
load_dotenv()

# Get credentials
token = os.getenv("ASTRADB_APPLICATION_TOKEN")
endpoint = os.getenv("ASTRADB_API_ENDPOINT")
keyspace = os.getenv("ASTRADB_KEYSPACE", "default_keyspace")
openai_key = os.getenv("OPENAI_API_KEY")

print("Adding sample data to AstraDB collections...")

# Initialize embeddings
embeddings = OpenAIEmbeddings(api_key=openai_key)

# Sample data for definitions collection
definitions_data = [
    {
        "content": "A home owner levy is a monthly or annual fee paid by property owners in a sectional title scheme or estate. It covers the costs of maintaining common areas, security, insurance, and management of the property.",
        "metadata": {"category": "definitions", "subcategory": "financial", "importance": "high"}
    },
    {
        "content": "Special levy is an additional contribution required from owners for unexpected expenses or major repairs not covered by the regular levy, such as roof repairs or infrastructure upgrades.",
        "metadata": {"category": "definitions", "subcategory": "financial", "importance": "medium"}
    },
    {
        "content": "Body corporate refers to the legal entity formed by all the owners of units in a sectional title scheme. It is responsible for managing and maintaining common property.",
        "metadata": {"category": "definitions", "subcategory": "legal", "importance": "high"}
    }
]

# Add to definitions collection
try:
    definitions_store = AstraDBVectorStore(
        token=token,
        api_endpoint=endpoint,
        collection_name="definitions_collection",
        namespace=keyspace,
        embedding=embeddings
    )
    
    # Create documents
    docs = [
        Document(page_content=item["content"], metadata=item["metadata"]) 
        for item in definitions_data
    ]
    
    # Add documents
    ids = definitions_store.add_documents(docs)
    print(f"✅ Added {len(ids)} documents to definitions collection")
    
except Exception as e:
    print(f"❌ Error adding to definitions: {e}")

print("\nSample data addition complete!")
