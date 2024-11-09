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
    """
    Fetches the list of files (with diffs) for a given PR from GitHub.
    """
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pr_number}/files"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        return {"error": f"GitHub API request failed with status code {response.status_code}"}

    # Extract relevant information (diffs) from each file in the PR
    files = response.json()
    pr_data = []
    for file in files:
        pr_data.append({
            "filename": file["filename"],
            "status": file["status"],
            "additions": file["additions"],
            "deletions": file["deletions"],
            "changes": file["changes"],
            "patch": file.get("patch")  # Contains the actual diff
        })
    
    return pr_data

@app.route('/fetch-pr-diffs', methods=['POST'])
def fetch_pr_diffs():
    """
    Accepts a GitHub PR URL, parses it, and fetches PR diffs from GitHub.
    """
    data = request.get_json()
    pr_url = data.get("pr_url")

    # Validate and parse the PR URL
    match = re.match(r"https://github.com/([^/]+)/([^/]+)/pulls/(\d+)", pr_url)
    if not match:
        return jsonify({"error": "Invalid GitHub PR URL format"}), 400

    owner, repo, pr_number = match.groups()

    # Fetch PR files with diffs
    pr_files = get_pr_files(owner, repo, pr_number)
    
    # If GitHub API request failed, return error
    if "error" in pr_files:
        return jsonify(pr_files), 500
    
    return jsonify({
        "pr_url": pr_url,
        "files": pr_files
    })

# Home page
@app.route('/')
def homepage():
    return render_template('home.html')

@app.route('/pr-insights', methods=['POST'])
def view_pr_insights():
    pr_url = request.form.get("pr_url")
    
    # Validate and parse the PR URL
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not match:
        return jsonify({"error": "Invalid GitHub PR URL format"}), 400
    
    owner, repo, pr_number = match.groups()
    pr_files = get_pr_files(owner, repo, pr_number)
    
    if "error" in pr_files:
        return jsonify(pr_files), 500
    
    return render_template("results.html", pr_url=pr_url, pr_files=pr_files)

if __name__ == "__main__":
    app.run(debug=False)