import os
from pathlib import Path

def generate_structure_md(root_dir, output_file):
    root_path = Path(root_dir)
    ignore_dirs = {'.venv', '.git', '__pycache__', '.pytest_cache', 'data', '.gemini'}
    ignore_files = {'.DS_Store'}
    
    lines = ["# Project Directory Structure\n\n"]
    lines.append("## Overview\nThis document provides a comprehensive view of the project's directory structure and a brief description of each file.\n\n")
    
    # Generate tree
    lines.append("## Tree Structure\n```text\n")
    
    # We will also collect files for the detailed descriptions section
    all_files = []
    
    def walk_tree(dir_path, prefix=""):
        entries = list(dir_path.iterdir())
        entries.sort(key=lambda x: (x.is_file(), x.name.lower()))
        
        # Filter entries
        valid_entries = []
        for e in entries:
            if e.is_dir() and e.name in ignore_dirs:
                continue
            if e.is_file() and e.name in ignore_files:
                continue
            valid_entries.append(e)
            
        count = len(valid_entries)
        for i, entry in enumerate(valid_entries):
            is_last = (i == count - 1)
            connector = "└── " if is_last else "├── "
            
            lines.append(f"{prefix}{connector}{entry.name}\n")
            
            if entry.is_dir():
                extension = "    " if is_last else "│   "
                walk_tree(entry, prefix + extension)
            else:
                all_files.append(entry)

    lines.append(f"{root_path.name}/\n")
    walk_tree(root_path)
    lines.append("```\n\n")
    
    # Generate descriptions
    lines.append("## File Descriptions\n\n")
    
    # Try to group by directory
    current_dir = None
    
    for file_path in all_files:
        rel_dir = file_path.parent.relative_to(root_path)
        
        if rel_dir != current_dir:
            lines.append(f"### `/{rel_dir if str(rel_dir) != '.' else ''}`\n")
            current_dir = rel_dir
            
        # Try to read the file for a description (docstring or just general)
        desc = "No description available."
        
        if file_path.suffix in ['.py']:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read(2000) # read first 2000 chars
                    import ast
                    try:
                        node = ast.parse(content)
                        doc = ast.get_docstring(node)
                        if doc:
                            desc = doc.strip().split('\n')[0] # Get first line of docstring
                        else:
                            desc = "Python script."
                    except:
                        desc = "Python script."
            except:
                desc = "Python script."
        elif file_path.suffix == '.md':
            desc = "Markdown documentation file."
        elif file_path.suffix == '.txt':
            desc = "Text file (e.g., requirements)."
        elif file_path.suffix == '.jsonl' or file_path.suffix == '.json':
            desc = "JSON data file."
        elif file_path.suffix == '.env':
            desc = "Environment configuration."
            
        lines.append(f"- **`{file_path.name}`**: {desc}\n")
        
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
        
if __name__ == "__main__":
    generate_structure_md(".", "DIRECTORY_STRUCTURE.md")
