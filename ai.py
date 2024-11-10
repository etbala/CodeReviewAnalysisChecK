import re
import markdown
from openai import OpenAI
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Initialize the OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_summary(pr_files):
    # Calculate total additions and deletions across all files
    total_additions = sum(file.get("additions", 0) for file in pr_files)
    total_deletions = sum(file.get("deletions", 0) for file in pr_files)

    # Include only key information from each file to guide the model
    file_summaries = "\n".join(
        f"- `{file.get('filename')}`: {file.get('additions', 0)} additions, {file.get('deletions', 0)} deletions."
        for file in pr_files[:5]  # Limit to the first 5 files for brevity
    )

    # Refine the input to get a more specific, detailed summary of the changes
    input_text = (
        f"Summarize the main changes introduced in this pull request. "
        f"The pull request affects {len(pr_files)} files with {total_additions} additions and {total_deletions} deletions. "
        f"Please identify notable changes in functionality, logic, and any significant modifications. Here are the most affected files:\n"
        f"{file_summaries}\n\n"
        "Avoid general statements and focus on specifics, such as major updates, new feature introductions, "
        "refactoring efforts, or improvements to code structure."
    )

    # Use the gpt-4o-mini model to generate a detailed summary
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a technical assistant summarizing pull request changes."},
            {"role": "user", "content": input_text}
        ]
    )

    # Extract and format the generated summary
    pr_summary = completion.choices[0].message.content.strip()

    # Replace newlines with <br> for proper HTML line breaks while keeping markdown format
    cleaned_summary = pr_summary.replace('\n', '<br>')
    pr_summary_html = markdown.markdown(cleaned_summary)
    return pr_summary_html

def get_scores(pr_files):
    # Format each file entry for the prompt
    files_info = "\n".join([
        f"Filename: {file['filename']}\nPatch:\n{file['patch']}" 
        for file in pr_files if 'patch' in file
    ])

    prompt = f"""
    I am providing you with a list of files modified in a pull request. For each file, assess if it contains security vulnerabilities. If a security vulnerability is found, include a one-sentence description of it. Otherwise, assign an importance score based on how critical it is that the code be reviewed, on a scale of 1 to 10 (with 10 being the most critical).

    Use the following criteria to assign the importance score:
    - Higher importance (7-10): Files that define new classes, structs, core functions, or modules that will be frequently used or have significant functionality. Also prioritize files that involve security-sensitive areas like authentication, data handling, or network communication.
    - Medium importance (4-6): Files that contain modifications to existing code, minor functionality, or helper functions.
    - Lower importance (1-3): Files that primarily contain imports, basic configuration, or boilerplate code that is unlikely to impact core functionality.

    Output your results in JSON format with the following structure:
    {{
        "files": [
            {{
                "filename": "name_of_the_file",
                "status": "vulnerable" or "secure",
                "importance_score": importance_score (integer between 1 and 10),
                "vulnerability_summary": "brief summary if vulnerable, otherwise null"
            }},
            ...
        ]
    }}

    Here are the files and their diffs:
    {files_info}
    """
    
    completion = client.chat.completions.create(
      model="gpt-4o-mini",
      messages=[{"role": "user", "content": prompt}],
      max_tokens=1500,
      temperature=0.2
    )

    # Access the content directly from the response
    result_text = completion.choices[0].message.content.strip()
    result_json = re.sub(r"^```json|```$", "", result_text.strip(), flags=re.MULTILINE)

    try:
        result = json.loads(result_json)
    except json.JSONDecodeError:
        print("The response could not be parsed as JSON. Here is the raw response:")
        print(result_json)
        return None
    
    return result