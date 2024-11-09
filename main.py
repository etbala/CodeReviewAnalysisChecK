from flask import Flask, render_template, request
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
    files_data = response.json() if response.status_code == 200 else {"error": "PR data not found"}

    # Process line numbers for each file's patch
    for file in files_data:
        if "patch" in file:
            file["lines"] = process_patch(file["patch"])

    return files_data

def get_pr_data(owner, repo, pr_number):
    pr_url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pr_number}"
    response = requests.get(pr_url, headers=HEADERS)
    return response.json() if response.status_code == 200 else {"error": "PR data not found"}

def get_repo_data(owner, repo):
    repo_url = f"{GITHUB_API_URL}/repos/{owner}/{repo}"
    response = requests.get(repo_url, headers=HEADERS)
    return response.json() if response.status_code == 200 else {"error": "Repo data not found"}

def process_patch(patch):
    lines = []
    old_line_num = 0
    new_line_num = 0

    for line in patch.splitlines():
        # Check if the line is a line number header like "@ -190,4 +190,4 @@"
        header_match = re.match(r"^@@ -(\d+),\d+ \+(\d+),\d+ @@", line)
        if header_match:
            # Set initial line numbers from the header
            old_line_num = int(header_match.group(1)) - 1
            new_line_num = int(header_match.group(2)) - 1
            continue  # Skip this line in the output

        # Skip lines with "No newline at end of file"
        if line.strip() == "\\ No newline at end of file":
            continue  # Ignore this line

        line_type = ""

        if line.startswith('+'):
            new_line_num += 1
            line_type = "addition"
            old_line_display = ""
            new_line_display = new_line_num
        elif line.startswith('-'):
            old_line_num += 1
            line_type = "deletion"
            old_line_display = old_line_num
            new_line_display = ""
        else:
            old_line_num += 1
            new_line_num += 1
            line_type = "context"
            old_line_display = old_line_num
            new_line_display = new_line_num

        # Append the processed line data to the list
        lines.append({
            "content": line,
            "type": line_type,
            "old_line_num": old_line_display,
            "new_line_num": new_line_display
        })

    return lines

# Home page
@app.route('/')
def homepage():
    return render_template('home.html')

@app.route('/insights', methods=['POST'])
def view_insights():
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
