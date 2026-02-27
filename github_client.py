import os
from github import Github
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME")

github_client = Github(GITHUB_TOKEN)
repo = github_client.get_repo(REPO_NAME)

# -----------------------
# GitHub functions
# -----------------------
def get_pr(pr_number: int):
    return repo.get_pull(pr_number)

def get_all_open_prs():
    """
    Returns a list of all open PRs in the repository
    """
    return repo.get_pulls(state="open")

def get_pr_files(pr):
    files = []
    for file in pr.get_files():
        files.append({
            "filename": file.filename,
            "changes": file.changes,
            "patch": file.patch
        })
    return files

def comment_on_pr(pr, message: str):
    pr.create_issue_comment(message)

def approve_pr(pr):
    pr.create_review(event="APPROVE")

def merge_pr(pr):
    pr.merge()