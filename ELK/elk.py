import os
import requests
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

load_dotenv()

ELASTICSEARCH_ENDPOINT = os.getenv("ELASTICSEARCH_ENDPOINT")
ELASTICSEARCH_API_KEY = os.getenv("ELASTICSEARCH_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
KIBANA_URL = os.getenv("KIBANA_URL")

INDEX_NAME = "pr_data"
KIBANA_HEADERS = {
    "kbn-xsrf": "true",
    "Content-Type": "application/json",
    "Authorization": f"ApiKey {ELASTICSEARCH_API_KEY}",
}

# Elasticsearch client
es_client = Elasticsearch(
    ELASTICSEARCH_ENDPOINT,
    api_key=ELASTICSEARCH_API_KEY
)

# PR-data-search tool creation
pr_data_search_tool = {
    "id": "pr_data_search",
    "type": "index_search",
    "description": (
        "Search internal security documents including incident reports, "
        "pentests, internal CVEs, security guidelines, and architecture decisions. "
        "Uses semantic search powered by ELSER to find relevant security information "
        "even without exact keyword matches. Returns documents with severity assessment "
        "and affected systems."
    ),
    "tags": ["security", "semantic", "vulnerabilities"],
    "configuration": {
        "pattern": INDEX_NAME,
    },
}

try:
    response = requests.post(
        f"{KIBANA_URL}/api/agent_builder/tools",
        headers=KIBANA_HEADERS,
        json=pr_data_search_tool,
    )
    if response.status_code == 200:
        print("Security pr-data search tool created successfully")
    else:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error creating tool: {e}")