from langgraph.graph import StateGraph
from typing import TypedDict
import os
import requests
from github_client import get_pr, get_pr_files, comment_on_pr, approve_pr, merge_pr
from risk_model import calculate_risk
from dotenv import load_dotenv
from transformers import pipeline
from llm.local_llm import LocalLLM
from elasticsearch import Elasticsearch

load_dotenv()

# -----------------------
# Setup LLM
# -----------------------
MODEL_ID = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
pipe = pipeline("text-generation", model=MODEL_ID)
local_llm = LocalLLM(pipe, max_tokens=256)

# -----------------------
# Elasticsearch & API Keys
# -----------------------
ELASTICSEARCH_ENDPOINT = os.environ["ELASTICSEARCH_ENDPOINT"]
ELASTICSEARCH_API_KEY = os.environ["ELASTICSEARCH_API_KEY"]
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")  # optional
ES_HOST = ELASTICSEARCH_ENDPOINT
ES_API_KEY = ELASTICSEARCH_API_KEY

es = Elasticsearch([ES_HOST], api_key=ES_API_KEY)

# -----------------------
# PR State
# -----------------------
class PRState(TypedDict):
    pr_number: int
    metadata: dict
    analysis: dict
    risk_score: int
    decision: str

# -----------------------
# Elastic Agent Runner
# -----------------------
def elastic_agent_run(task_name: str, task_input: str) -> str:
    url = f"{ELASTICSEARCH_ENDPOINT}/api/agents/run"
    headers = {
        "Authorization": f"ApiKey {ELASTICSEARCH_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"name": task_name, "input": task_input}
    try:
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json().get("output_text", "")
    except Exception:
        return ""  # fallback if Elastic agent fails

# -----------------------
# Agents
# -----------------------
def metadata_agent(state: PRState):
    pr = get_pr(state["pr_number"])
    files = get_pr_files(pr)
    touches_core = any("auth" in f["filename"] or "core" in f["filename"] for f in files)
    state["metadata"] = {
        "total_changes": sum(f["changes"] for f in files),
        "file_count": len(files),
        "touches_core": touches_core,
        "files": files,
    }
    return state

def code_analysis_agent(state: PRState):
    patches = "\n".join(
        f"{f['filename']}:\n{f['patch']}" for f in state["metadata"]["files"] if f.get("patch")
    )
    prompt = (
        "Analyze the following PR patches.\n"
        "Ignore debug prints and focus on code logic.\n"
        "Classify complexity: low, medium, high\n"
        "Flag security_risk: true/false\n"
        f"Patches:\n{patches}\n"
        "Explain your reasoning step by step, considering code structure, "
        "nested logic, complex libraries, and security-sensitive patterns. "
        "Be concise but thorough."
    )

    chunk_size = 1500
    chunks = [patches[i:i + chunk_size] for i in range(0, len(patches), chunk_size)]

    for chunk in chunks:
        chunk_prompt = f"Analyze the following PR chunk:\n{chunk}"
        messages = [{"role": "user", "content": chunk_prompt}]
        outputs = pipe(messages, max_new_tokens=256)

    text = elastic_agent_run("code_analysis", prompt).lower()
    complexity = "low"
    if "high" in text:
        complexity = "high"
    elif "medium" in text:
        complexity = "medium"
    security_risk = "true" in text
    state["analysis"] = {"complexity": complexity, "security_risk": security_risk}
    return state

def risk_agent(state: PRState):
    state["risk_score"] = calculate_risk(state["metadata"], state["analysis"])
    return state

def decision_agent(state: PRState):
    r = state["risk_score"]
    if r < 30:
        state["decision"] = "merge"
    elif r < 70:
        state["decision"] = "review"
    else:
        state["decision"] = "block"
    return state

def executor_agent(state: PRState):
    pr = get_pr(state["pr_number"])
    comment = (
        f"🔍 PR Risk Assessment\n"
        f"Risk Score: {state['risk_score']}/100\n"
        f"Complexity: {state['analysis']['complexity']}\n"
        f"Security Risk: {state['analysis']['security_risk']}\n"
        f"Decision: {state['decision'].upper()}"
    )
    comment_on_pr(pr, comment)

    token_user = pr.user.login
    if state["decision"] == "merge" and pr.user.login != token_user:
        approve_pr(pr)
        merge_pr(pr)

    url = f"{ELASTICSEARCH_ENDPOINT}/github-prs-analysis/_doc/{state['pr_number']}"
    headers = {"Authorization": f"ApiKey {ELASTICSEARCH_API_KEY}", "Content-Type": "application/json"}
    requests.put(url, headers=headers, json=state)
    return state

# -----------------------
# Elastic MCP Tool Runner
# -----------------------
def elastic_mcp_tool_run(tool_name: str, query: str, api_key: str, kibana_url: str) -> dict:
    mcp_url = f"{kibana_url}/api/agent_builder/mcp"
    payload = {"tool": tool_name, "input": query}
    headers = {"Authorization": f"ApiKey {api_key}", "Content-Type": "application/json"}
    resp = requests.post(mcp_url, json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()

def elastic_search_agent(state: PRState):
    if "analysis" not in state:
        state["analysis"] = {}
    query_text = f"PR #{state['pr_number']} risky patterns"
    query_body = {"size": 5, "query": {"match": {"patches": query_text}}}
    res = es.search(index="github-prs-analysis", body=query_body)
    hits = [hit["_source"]["patches"] for hit in res["hits"]["hits"]]
    state["analysis"]["elastic_context"] = hits
    return state

# -----------------------
# Build LangGraph workflow
# -----------------------
def build_graph():
    graph = StateGraph(PRState)

    graph.add_node("metadata", metadata_agent)
    graph.add_node("elastic_search", elastic_search_agent)
    graph.add_node("analysis", code_analysis_agent)
    graph.add_node("risk", risk_agent)
    graph.add_node("decision", decision_agent)
    graph.add_node("executor", executor_agent)

    graph.set_entry_point("metadata")

    graph.add_edge("metadata", "elastic_search")
    graph.add_edge("elastic_search", "analysis")
    graph.add_edge("analysis", "risk")
    graph.add_edge("risk", "decision")
    graph.add_edge("decision", "executor")

    return graph