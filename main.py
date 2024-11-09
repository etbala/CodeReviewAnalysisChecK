from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import requests
import os
import re

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

GITHUB_API_URL = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

def get_pr_files(owner, repo, pr_number):
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pr_number}/files"
    response = requests.get(url, headers=HEADERS)
    return response.json() if response.status_code == 200 else {"error": "PR data not found"}

def get_pr_data(owner, repo, pr_number):
    pr_url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pr_number}"
    response = requests.get(pr_url, headers=HEADERS)
    return response.json() if response.status_code == 200 else {"error": "PR data not found"}

def get_repo_data(owner, repo):
    repo_url = f"{GITHUB_API_URL}/repos/{owner}/{repo}"
    response = requests.get(repo_url, headers=HEADERS)
    return response.json() if response.status_code == 200 else {"error": "Repo data not found"}

# Home page
@app.route('/')
def homepage():
    return render_template('home.html')

@app.route('/pr-insights', methods=['POST'])
def view_pr_insights():
    pr_url = request.form.get("pr_url")
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not match:
        return {"error": "Invalid GitHub PR URL format"}, 400

    owner, repo, pr_number = match.groups()
    pr_data = get_pr_data(owner, repo, pr_number)
    repo_data = get_repo_data(owner, repo)
    pr_files = get_pr_files(owner, repo, pr_number)

    # Extract necessary details
    org_name = repo_data.get("owner", {}).get("login", "Unknown Org")
    org_logo = repo_data.get("owner", {}).get("avatar_url", "")
    org_url = repo_data.get("owner", {}).get("html_url", "")
    repo_name = repo_data.get("name", "Unknown Repo")
    repo_url = repo_data.get("html_url", "")
    pr_title = pr_data.get("title", "PR title unavailable")
    pr_number = pr_data.get("number", "")
    pr_link = pr_data.get("html_url", "")

    # Pass data to the template
    return render_template("insights.html",
                           org_name=org_name,
                           org_logo=org_logo,
                           org_url=org_url,
                           repo_name=repo_name,
                           repo_url=repo_url,
                           pr_title=pr_title,
                           pr_number=pr_number,
                           pr_link=pr_link,
                           pr_files=pr_files)

if __name__ == "__main__":
    app.run(debug=False)