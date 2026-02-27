from elasticsearch import Elasticsearch
import os
from dotenv import load_dotenv

load_dotenv()

es_client = Elasticsearch(
    os.getenv("ELASTICSEARCH_ENDPOINT"),
    api_key=os.getenv("ELASTICSEARCH_API_KEY")
)

# List all indices
indices = es_client.indices.get_alias(name="*")
print("Existing indices:", list(indices.keys()))