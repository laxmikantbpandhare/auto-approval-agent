import requests
import os
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

load_dotenv()
INDEX_NAME = os.environ["INDEX_NAME"]
ELASTICSEARCH_ENDPOINT = os.environ["ELASTICSEARCH_ENDPOINT"]
ELASTICSEARCH_API_KEY = os.environ["ELASTICSEARCH_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
KIBANA_URL = os.environ["KIBANA_URL"]
KIBANA_HEADERS={
    "kbn-xsrf": "true",
    "Content-Type": "application/json",
    "Authorization": f"ApiKey {ELASTICSEARCH_API_KEY}",
}

es_client = Elasticsearch(ELASTICSEARCH_ENDPOINT, api_key=ELASTICSEARCH_API_KEY) # Elasticsearch client


github_pr_data_tool = {
    "id": "github_pr_data-search",
    "type": "index_search",
    "description": "Search PR Data stored, files, code changes, commits, and owner. Uses semantic search powered by ELSER to find relevant security information even without exact keyword matches. Returns documents with severity assessment and affected systems.",
    "tags": ["pr", "code_changes", "decision"],
    "configuration": {
        "pattern": INDEX_NAME,
    },
}

try:
    response = requests.post(
        f"{KIBANA_URL}/api/agent_builder/tools",
        headers=KIBANA_HEADERS,
        json=github_pr_data_tool,
    )

    if response.status_code == 200:
        print("Security semantic search tool created successfully")    
    else:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error creating tool: {e}")


pr_index_mapping = {
    "mappings": {
        "properties": {
            "pr_number": {"type": "integer"},
            "metadata.total_changes": {"type": "integer"},
            "metadata.file_count": {"type": "integer"},
            "metadata.touches_core": {"type": "boolean"},
            "metadata.files": {
                "type": "nested",
                "properties": {
                    "filename": {"type": "text", "copy_to": "semantic_field"},
                    "changes": {"type": "integer"},
                    "patch": {"type": "text", "copy_to": "semantic_field"}
                }
            },
            "semantic_field": {"type": "semantic_text"}
        }
    }
}


if es_client.indices.exists(index=INDEX_NAME) is False:
    es_client.indices.create(index=INDEX_NAME, body=pr_index_mapping)
    print(f"Index '{INDEX_NAME}' created with semantic_text field for ELSER")
else:
    print(f"Index '{INDEX_NAME}' already exists, skipping creation")