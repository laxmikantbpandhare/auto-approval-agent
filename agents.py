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
import os

model_id = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
pipe = pipeline(
    "text-generation",
    model="TinyLlama/TinyLlama-1.1B-Chat-v1.0"
)

model_id = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
pipe = pipeline("text-generation", model=model_id)

local_llm = LocalLLM(pipe, max_tokens=256)

load_dotenv()


ES_HOST = os.environ["ELASTICSEARCH_ENDPOINT"]
ES_API_KEY = os.environ["ELASTICSEARCH_API_KEY"]

es = Elasticsearch(
    [ES_HOST],
    api_key=ES_API_KEY
)
ELASTICSEARCH_ENDPOINT = os.environ["ELASTICSEARCH_ENDPOINT"]
ELASTICSEARCH_API_KEY = os.environ["ELASTICSEARCH_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# llm = ChatOpenAI(
#     model="gpt-4o-mini", temperature=0, openai_api_key=OPENAI_API_KEY
# )

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
# Elastic agent call
# -----------------------
def elastic_agent_run(task_name: str, task_input: str) -> str:
    url = f"{ELASTICSEARCH_ENDPOINT}/api/agents/run"
    headers = {"Authorization": f"ApiKey {ELASTICSEARCH_API_KEY}", "Content-Type": "application/json"}
    payload = {"name": task_name, "input": task_input}
    try:
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json().get("output_text", "")
    except:
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
        "files": files
    }
    return state


def code_analysis_agent(state: PRState):
    patches = "\n".join(f"{f['filename']}:\n{f['patch']}" for f in state["metadata"]["files"] if f.get("patch"))

    prompt = f"""
    Analyze the following PR patches.
    Ignore debug prints (print statements) and focus on code logic.
    Classify complexity: low, medium, high
    Flag security_risk: true/false
    Patches:
    {patches}
    Explain your reasoning step by step, considering factors like code structure, deeply nested logic, use of complex libraries, and any security-sensitive code patterns. Be concise but thorough in your analysis.
    """

    print(len(prompt))

    chunk_size = 1500  # tokens per chunk (safe under 2048)
    chunks = [patches[i:i+chunk_size] for i in range(0, len(patches), chunk_size)]

    for chunk in chunks:
        prompt = f"Analyze the following PR chunk:\n{chunk}"
        messages = [{"role": "user", "content": prompt}]
        outputs = pipe(messages, max_new_tokens=256)

    print("generated text start Here\n")
    print(outputs[0]["generated_text"][-1])
    print("generated text ends Here\n")

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
    comment = f"""
    🔍 PR Risk Assessment
    Risk Score: {state['risk_score']}/100
    Complexity: {state['analysis']['complexity']}
    Security Risk: {state['analysis']['security_risk']}
    Decision: {state['decision'].upper()}
    """
    comment_on_pr(pr, comment)

    # Only merge if PR author is not token user
    token_user = pr.user.login
    if state["decision"] == "merge" and pr.user.login != token_user:
        approve_pr(pr)
        merge_pr(pr)

    # Push to Elastic for search/audit
    url = f"{ELASTICSEARCH_ENDPOINT}/github-prs-analysis/_doc/{state['pr_number']}"
    headers = {"Authorization": f"ApiKey {ELASTICSEARCH_API_KEY}", "Content-Type": "application/json"}
    requests.put(url, headers=headers, json=state)
    return state


# ----------------------------------------
# Helper To Call Elastic Agent Builder MCP
# ----------------------------------------
def elastic_mcp_tool_run(tool_name: str, query: str, api_key: str, kibana_url: str) -> dict:
    """
    Calls an Elastic Agent Builder MCP tool with a query.
    """
    mcp_url = f"{kibana_url}/api/agent_builder/mcp"
    payload = {
        "tool": tool_name,
        "input": query
    }
    headers = {
        "Authorization": f"ApiKey {api_key}",
        "Content-Type": "application/json"
    }
    resp = requests.post(mcp_url, json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()


def elastic_search_agent(state: PRState):
    # Make sure 'analysis' exists
    if "analysis" not in state:
        state["analysis"] = {}

    query_text = f"PR #{state['pr_number']} risky patterns"
    query_body = {
        "size": 5,
        "query": {
            "match": {
                "patches": query_text
            }
        }
    }
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