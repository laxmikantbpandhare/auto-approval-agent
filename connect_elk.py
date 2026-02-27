from elasticsearch import Elasticsearch

# Configuration from your GCP deployment
ELASTIC_HOST = "https://my-elasticsearch-project-cf6846.es.us-central1.gcp.elastic.cloud"
ELASTIC_API_KEY = "MnhnX2pwd0JBSi1hVjVZN3VkWVM6bjVhME5pdHNDT1NSdTdoVHRkXzBEUQ=="

# 1. Initialize the client
es = Elasticsearch(
    ELASTIC_HOST,
    api_key=ELASTIC_API_KEY
)

# 2. Verify connection
if es.ping():
    print("Connected to Elasticsearch!")
else:
    print("Could not connect.")

# 3. Call Agents/Search Data (Example: search agent logs)
# You can use specific index patterns for agent data
index_pattern = "logs-*" 

response = es.search(
    index=index_pattern,
    body={
        "query": {
            "match_all": {}
        },
        "size": 10
    }
)

# 4. Print results
for hit in response['hits']['hits']:
    print(hit['_source'])
