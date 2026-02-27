from langgraph.graph import StateGraph
from typing import TypedDict
import os
import requests
from github_client import get_pr, get_pr_files, comment_on_pr, approve_pr, merge_pr
from risk_model import calculate_risk
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from transformers import pipeline
import torch

model_id = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
pipe = pipeline(
    "text-generation",
    model="TinyLlama/TinyLlama-1.1B-Chat-v1.0"
)
load_dotenv()
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
    Classify complexity: low, medium, high
    Flag security_risk: true/false
    Patches:
    {patches}
    """

    print("prompt here")
    print(prompt)
    print("prompt ends here")

    chunk_size = 1500  # tokens per chunk (safe under 2048)
    chunks = [patches[i:i+chunk_size] for i in range(0, len(patches), chunk_size)]

    for chunk in chunks:
        prompt = f"Analyze the following PR chunk:\n{chunk}"
        messages = [{"role": "user", "content": prompt}]
        outputs = pipe(messages, max_new_tokens=256)

    # messages = [
    #     {"role": "user", "content": prompt}
    # ]

   # print(len(prompt))

    # outputs = pipe(
    #     messages,
    #     max_new_tokens=256,
    # )
    print("generated text Here")
    print(outputs[0]["generated_text"][-1])
    print("generated text ends Here")

    text = elastic_agent_run("code_analysis", prompt).lower()
    # Invoke
    # response = llm.invoke("Hello!")
    # print(response.content)
    #print(text['choices'][0]['text'])
    # print(text)
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