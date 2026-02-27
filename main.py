from agents import build_graph
from github_client import get_all_open_prs


# -----------------------
# Run all open PRs
# -----------------------
def run_all_prs():
    graph = build_graph()

    # REQUIRED in new LangGraph
    app = graph.compile()

    for pr in get_all_open_prs():
        state = {"pr_number": pr.number}
        
        print(f"Processing PR #{pr.number} by {pr.user.login}")

        #call ELK and store metadata on PR into Elasticsearch for future use

        # Execute workflow
        result = app.invoke(state)

        print("Final State:", result)


if __name__ == "__main__":
    run_all_prs()