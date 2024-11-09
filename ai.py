import re
import markdown
from openai import OpenAI
import os
from dotenv import load_dotenv

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
