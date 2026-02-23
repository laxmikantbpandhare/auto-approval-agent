import requests
import time

GITHUB_TOKEN = "xxxxxxxxxxxxx"
OWNER = "laxmikantbpandhare"
REPO = "auto-approval-agent"

BASE_URL = f"https://api.github.com/repos/{OWNER}/{REPO}"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}


def classify_pr(pr, files):
    """
    Classify PR based on labels + file paths + title
    """

    # 1️⃣ Check labels first (most reliable if you use them)
    label_names = [label["name"].lower() for label in pr.get("labels", [])]
    if label_names:
        return ", ".join(label_names)

    # 2️⃣ Check file paths
    file_paths = [f["filename"].lower() for f in files]

    if all(f.startswith("docs/") or f.endswith(".md") for f in file_paths):
        return "Documentation"

    if any("test" in f for f in file_paths):
        return "Tests"

    if any(".yml" in f or ".yaml" in f or ".github/" in f for f in file_paths):
        return "CI/CD"

    if any(f.endswith((".py", ".java", ".js", ".ts", ".go", ".cpp")) for f in file_paths):
        return "Code"

    return "Other"


def get_all_prs():
    prs = []
    page = 1

    while True:
        url = f"{BASE_URL}/pulls?state=all&per_page=100&page={page}"
        response = requests.get(url, headers=HEADERS)
        data = response.json()

        if not data:
            break

        prs.extend(data)
        page += 1
        time.sleep(0.2)

    return prs


def get_pr_files(pr_number):
    url = f"{BASE_URL}/pulls/{pr_number}/files"
    response = requests.get(url, headers=HEADERS)
    return response.json()


if __name__ == "__main__":
    all_prs = get_all_prs()

    print(f"Total PRs: {len(all_prs)}\n")

    for pr in all_prs:
        pr_number = pr["number"]
        files = get_pr_files(pr_number)

        pr_type = classify_pr(pr, files)

        print(f"PR #{pr_number}")
        print("Title:", pr["title"])
        print("Author:", pr["user"]["login"])
        print("State:", pr["state"])
        print("Type:", pr_type)
        print("-" * 60)