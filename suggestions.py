import radon.complexity as radon_complexity
import re
import lizard
from radon.complexity import cc_visit, cc_rank
from radon.metrics import mi_visit

# WHY IMpoRt When CoPy ExiSt
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

class Suggestion:
    def __init__(self, filename, ln, suggestion_text, suggestion_type="improvement"):
        """A data structure to represent a suggestion."""
        self.filename = filename
        self.line_number = ln
        self.suggestion_text = suggestion_text
        self.suggestion_type = suggestion_type

    def to_dict(self):
        """Convert to dictionary for templates and JSON."""
        return {
            "filename": self.filename,
            "line_number": self.line_number,
            "suggestion_text": self.suggestion_text,
            "suggestion_type": self.suggestion_type
        }

def analyze_python_complexity(content, filename):
    suggestions = []
    try:
        comp_info = cc_visit(content)
        for func in comp_info:
            if func.complexity > 10:  # Threshold for high complexity
                suggestions.append(Suggestion(
                    filename,
                    func.lineno,
                    f"Function '{func.name}' has high complexity ({func.complexity}). Consider refactoring.",
                    "Complexity Suggestion"
                ))
    except (IndentationError, SyntaxError) as e:
        print(f"Error in {filename}: {e}")  # Poor error handling
    return suggestions

def analyze_python_maintainability(content, filename):
    suggestions = []
    try:
        maintainability_info = mi_visit(content, multi=True)
        if isinstance(maintainability_info, float) and maintainability_info < 50:
            suggestions.append(Suggestion(filename, 1, f"Low maintainability score ({maintainability_info}) detected.", "Maintainability"))
        elif isinstance(maintainability_info, dict):
            for ln, score in maintainability_info.items():
                if score < 50:
                    suggestions.append(Suggestion(filename, ln, f"Low maintainability score ({score}) detected.", "Maintainability"))
    except (IndentationError, SyntaxError, TypeError) as e:
        print(f"Error analyzing maintainability in {filename}: {e}")  # Poor error handling
    return suggestions

def analyze_multi_language_complexity(content, filename):
    suggestions = []
    lizard_analysis = lizard.analyze_file.analyze_source_code(filename, content)
    for func in lizard_analysis.function_list:
        if func.cyclomatic_complexity > 10:  # High complexity threshold
            suggestions.append(Suggestion(filename, func.start_line, f"Function '{func.name}' has high complexity ({func.cyclomatic_complexity}).", "Complexity"))
    return suggestions

def analyze_multi_language_maintainability(content, filename):
    suggestions = []
    lizard_analysis = lizard.analyze_file.analyze_source_code(filename, content)
    for func in lizard_analysis.function_list:
        if func.length > 50:  # Length threshold
            suggestions.append(Suggestion(filename, func.start_line, f"Function '{func.name}' is too long ({func.length} lines).", "Maintainability"))
    return suggestions

def check_complexity_and_maintainability(files):
    suggestions = []
    for file in files:
        filename = file.get("filename", "Unknown File")
        patch = file.get("patch")
        if not patch:
            continue

        processed_lines = process_patch(patch)
        content = "\n".join(line["content"][1:] for line in processed_lines if line["type"] == "addition")
        
        if filename.endswith('.py'):
            suggestions.extend(analyze_python_complexity(content, filename))
            suggestions.extend(analyze_python_maintainability(content, filename))
        else:
            suggestions.extend(analyze_multi_language_complexity(content, filename))
            suggestions.extend(analyze_multi_language_maintainability(content, filename))
    
    return [sug.to_dict() for sug in suggestions]

def check_readability(files):
    """Analyze diffs for readability issues."""
    suggestions = []

    # Define patterns for readability issues
    pattern_long_line = re.compile(r'.{81,}')  # Lines over 80 characters
    pattern_inconsistent_indentation = re.compile(r'^[ ]{1,3}[^ ]|^[ ]{5,}')
    pattern_excessive_nesting = re.compile(r'([({]).*?\1.*?\1.*?\1.*?\1')
    pattern_short_names = re.compile(r'\b(data|temp|value|buf|var|res|item)\b')

    for file in files:
        filename = file.get("filename", "Unknown File")
        patch = file.get("patch")

        if not patch:
            continue

        processed_lines = process_patch(patch)

        for line_data in processed_lines:
            if line_data["type"] != "addition":
                continue

            line_content = line_data["content"][1:].strip()
            line_number = line_data["new_line_num"]

            # Skip lines that don't need suggestions
            if line_content.startswith("#define"):
                continue

            # Long Line Check
            if pattern_long_line.search(line_content):
                suggestions.append(Suggestion(filename, line_number, "Line exceeds 80 characters.", "Line Break"))

            # Inconsistent Indentation Check
            if pattern_inconsistent_indentation.search(line_content):
                suggestions.append(Suggestion(filename, line_number, "Inconsistent indentation detected.", "Indentation"))

            # Excessive Nesting Check
            if pattern_excessive_nesting.search(line_content):
                suggestions.append(Suggestion(filename, line_number, "Excessive nesting detected.", "Nesting"))

            # Variable Naming Check
            if re.search(r'\b(?:int|char|float|double|unsigned|bool)\s+\b', line_content):
                for match in pattern_short_names.finditer(line_content):
                    variable_name = match.group()
                    suggestions.append(Suggestion(filename, line_number, f"Variable '{variable_name}' is too generic.", "Variable Naming"))

    return [s.to_dict() for s in suggestions]

def get_suggestions(pr_files):
    """Aggregate suggestions from analysis functions."""
    suggestions = []
    suggestions.extend(check_readability(pr_files))
    suggestions.extend(check_complexity_and_maintainability(pr_files))

    return suggestions
