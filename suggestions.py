import radon.complexity as radon_complexity
import re
import lizard
from radon.complexity import cc_visit, cc_rank
from radon.metrics import mi_visit

# WHY IMpoRt When CoPy ExiSt
def process(p):
    lines = []
    old_line_num = 0
    new_line_num = 0

    for line in p.splitlines():
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

class Suggestion:
    def __init__(self, filename, line_number, suggestion_text, suggestion_type="improvement"):
        """
        A data structure to represent a code suggestion.

        Parameters:
            filename (str): The name of the file where the suggestion applies.
            line_number (int): The line number in the file where the suggestion is relevant.
            suggestion_text (str): The suggestion text or message.
            suggestion_type (str): The type of suggestion, e.g., "improvement", "refactor", "warning".
        """
        self.filename = filename
        self.line_number = line_number
        self.suggestion_text = suggestion_text
        self.suggestion_type = suggestion_type

    def to_dict(self):
        """Convert the suggestion to a dictionary for easier use in templates and JSON responses."""
        return {
            "filename": self.filename,
            "line_number": self.line_number,
            "suggestion_text": self.suggestion_text,
            "suggestion_type": self.suggestion_type
        }

def analyze_python_complexity(content, filename):
    suggestions = []
    try:
        complexity_info = cc_visit(content)
        for func in complexity_info:
            if func.complexity > 10:  # Threshold for high complexity
                suggestions.append(Suggestion(
                    filename,
                    func.lineno,
                    f"Function '{func.name}' has high cyclomatic complexity ({func.complexity}). Consider refactoring.",
                    "Complexity Suggestion"
                ))
    except (IndentationError, SyntaxError) as e:
        # Log or handle the error gracefully
        print(f"Error analyzing complexity in {filename}: {e}")
    return suggestions

def analyze_python_maintainability(content, filename):
    suggestions = []
    try:
        maintainability_info = mi_visit(content, multi=True)  # Set multi=True for multiple code blocks

        # Check if maintainability_info is a float (single score) or a dictionary (multiple scores)
        if isinstance(maintainability_info, float):
            # Single maintainability score
            if maintainability_info < 50:
                suggestions.append(Suggestion( filename, 1, f"Low maintainability score ({maintainability_info}) detected. Consider refactoring.", "Maintainability Suggestion" ))
        elif isinstance(maintainability_info, dict):
            # Multiple maintainability scores
            for line_num, score in maintainability_info.items():
                if score < 50:
                    suggestions.append(Suggestion(
                        filename,
                        line_num,
                        f"Low maintainability score ({score}) detected. Consider refactoring.",
                        "Maintainability Suggestion"
                    ))

    except (IndentationError, SyntaxError, TypeError) as e:
        # Log or handle the error gracefully
        print(f"Error analyzing maintainability in {filename}: {e}")
    return suggestions

def analyze_multi_language_complexity(content, filename):
    suggestions = []
    lizard_analysis = lizard.analyze_file.analyze_source_code(filename, content)
    for func in lizard_analysis.function_list:
        if func.cyclomatic_complexity > 10:  # High complexity threshold
            suggestions.append(Suggestion(
                filename,
                func.start_line,
                f"Function '{func.name}' has high cyclomatic complexity ({func.cyclomatic_complexity}). Consider refactoring.",
                "Complexity Suggestion"
            ))
    return suggestions

def analyze_multi_language_maintainability(content, filename):
    suggestions = []
    lizard_analysis = lizard.analyze_file.analyze_source_code(filename, content)
    for func in lizard_analysis.function_list:
        if func.length > 50:  # Length threshold for maintainability
            suggestions.append(Suggestion(
                filename,
                func.start_line,
                f"Function '{func.name}' is too long ({func.length} lines). Consider modularizing.",
                "Maintainability Suggestion"
            ))
    return suggestions

def check_complexity_and_maintainability(pr_files):
    suggestions = []
    for file in pr_files:
        filename = file.get("filename", "Unknown File")
        patch = file.get("patch")
        if not patch:
            continue

        processed_lines = process(patch)
        content = "\n".join(line["content"][1:] for line in processed_lines if line["type"] == "addition")
        
        # Determine analysis type based on file extension
        if filename.endswith('.py'):
            suggestions.extend(analyze_python_complexity(content, filename))
            suggestions.extend(analyze_python_maintainability(content, filename))
        else:
            suggestions.extend(analyze_multi_language_complexity(content, filename))
            suggestions.extend(analyze_multi_language_maintainability(content, filename))
    
    return [suggestion.to_dict() for suggestion in suggestions]

def check_readability(pr_files):
    """
    Analyzes added lines in code diffs for readability issues, with reduced sensitivity.
    Generates suggestions for lines with potential readability improvements.

    Returns:
        List[Suggestion]: A list of suggestions to improve readability.
    """
    suggestions = []

    # Define patterns for readability issues
    pattern_long_line = re.compile(r'.{81,}')  # Lines over 80 characters
    pattern_inconsistent_indentation = re.compile(r'^[ ]{1,3}[^ ]|^[ ]{5,}')  # Non-4-space indentation
    # Refined pattern for detecting 5+ nested braces or parentheses in a single line
    pattern_excessive_nesting = re.compile(r'([({]).*?\1.*?\1.*?\1.*?\1')  # Matches 5+ occurrences of '(' or '{'
    pattern_short_variable_names = re.compile(r'\b(data|temp|value|buf|var|res|item)\b')

    for file in pr_files:
        filename = file.get("filename", "Unknown File")
        patch = file.get("patch")

        if not patch:
            continue

        # Process the patch using process function to get structured diff lines
        processed_lines = process(patch)

        for line_data in processed_lines:
            # Only process added lines
            if line_data["type"] != "addition":
                continue

            line_content = line_data["content"][1:].strip()  # Remove '+' and extra whitespace
            line_number = line_data["new_line_num"]

            # Skip `#define` lines, which don't require readability suggestions
            if line_content.startswith("#define"):
                continue

            # 1. Long Line Check
            if pattern_long_line.search(line_content):
                suggestions.append(Suggestion(
                    filename,
                    line_number,
                    "Line exceeds 80 characters. Consider breaking it into multiple lines for readability.",
                    "Line Break Suggestion"
                ))

            # 2. Inconsistent Indentation Check (assuming 4 spaces per indentation level)
            if pattern_inconsistent_indentation.search(line_content):
                suggestions.append(Suggestion(
                    filename,
                    line_number,
                    "Line has inconsistent indentation. Consider using 4 spaces for indentation.",
                    "Indentation Suggestion"
                ))

            # 3. Excessive Nesting Check (only if actual nested structures are found with 5+ layers)
            if pattern_excessive_nesting.search(line_content):
                suggestions.append(Suggestion(
                    filename,
                    line_number,
                    "Code appears deeply nested (5+ levels). Consider refactoring to reduce nesting depth.",
                    "Nesting Suggestion"
                ))

            # 4. Less Sensitive Variable Naming Check with Feedback
            if re.search(r'\b(?:int|char|float|double|unsigned|bool)\s+\b', line_content):  # Check if line is a variable declaration
                for match in pattern_short_variable_names.finditer(line_content):
                    variable_name = match.group()
                    suggestions.append(Suggestion(
                        filename,
                        line_number,
                        f"Variable '{variable_name}' is too generic. Consider renaming it to something more descriptive.",
                        "Variable Naming Suggestion"
                    ))

    return [suggestion.to_dict() for suggestion in suggestions]

def get_suggestions(pr_files):
    """
    Aggregates suggestions from all analysis functions and returns a list of suggestions.

    Parameters:
        pr_files (list): A list of PR file objects, each containing file details and diffs.

    Returns:
        List[Suggestion]: A list of all suggestions generated for the PR.
    """
    suggestions = []
    suggestions.extend(check_readability(pr_files))
    suggestions.extend(check_complexity_and_maintainability(pr_files))

    return suggestions
