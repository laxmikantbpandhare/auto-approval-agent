from langgraph.graph import StateGraph
from typing import TypedDict
import os
import requests

from github_client import get_pr, get_pr_files, comment_on_pr, approve_pr, merge_pr
from risk_model import calculate_risk
from dotenv import load_dotenv

load_dotenv()
ELASTIC_HOST = os.environ["ELASTIC_HOST"]
ELASTIC_API_KEY = os.environ["ELASTIC_API_KEY"]

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
    url = f"{ELASTIC_HOST}/api/agents/run"
    headers = {"Authorization": f"ApiKey {ELASTIC_API_KEY}", "Content-Type": "application/json"}
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
    Classify complexity: low, medium, high
    Flag security_risk: true/false
    Patches:
    {patches}
    """
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
    url = f"{ELASTIC_HOST}/github-prs-analysis/_doc/{state['pr_number']}"
    headers = {"Authorization": f"ApiKey {ELASTIC_API_KEY}", "Content-Type": "application/json"}
    requests.put(url, headers=headers, json=state)
    return state

# -----------------------
# Build LangGraph workflow
# -----------------------
def build_graph():
    graph = StateGraph(PRState)

    graph.add_node("metadata", metadata_agent)
    graph.add_node("analysis", code_analysis_agent)
    graph.add_node("risk", risk_agent)
    graph.add_node("decision", decision_agent)
    graph.add_node("executor", executor_agent)

    graph.set_entry_point("metadata")

    graph.add_edge("metadata", "analysis")
    graph.add_edge("analysis", "risk")
    graph.add_edge("risk", "decision")
    graph.add_edge("decision", "executor")

    return graph