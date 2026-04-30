# project_mapper.py - Industrial System Auditor (v2.4)
# ROLE: Forensic Manifest Generator. Extracts hierarchy and Industrial Spec tags.
# COMPLIANCE: Spec 9.0 (Self-Awareness)
# USAGE: python project_mapper.py
# CHANGES:
#   - v2.4: Added Markdown Report generation (SYSTEM_MANIFEST.md).
#   - v2.4: Added Visual Density Bar Charts (ASCII).
#   - v2.3: Added Industrial Metrics: Object line counts and a final Forensic Summary.
#   - v2.2: Added support for AsyncFunctionDef to capture 'async def' methods.

import ast
import os
import re

class IndustrialMapper(ast.NodeVisitor):
    """
    [Spec 9.0] Docstring-Aware Project Auditor.
    Performs a deep AST scan to extract hierarchy and identify [Spec XX.X] markers.
    """
    def __init__(self, filename):
        self.filename = filename
        self.results = []
        self.current_class = None
        self.spec_pattern = re.compile(r"\[Spec ([\d\.]+)\]")

    def get_summary(self, node):
        """Extracts the first non-empty line, Spec tags, and node line count."""
        doc = ast.get_docstring(node)
        summary = "No docstring"
        spec_str = ""
        
        line_count = 0
        if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
            line_count = node.end_lineno - node.lineno + 1

        if doc:
            lines = [line.strip() for line in doc.split('\n') if line.strip()]
            if lines:
                summary = lines[0]
            
            specs = self.spec_pattern.findall(doc)
            unique_specs = sorted(list(set(specs)), key=lambda x: [int(s) if s.isdigit() else s for s in x.split('.')])
            spec_str = ", ".join([f"S{s}" for s in unique_specs]) if unique_specs else ""
        
        return summary, spec_str, line_count

    def visit_Module(self, node):
        """[Spec 9.1] Capture file-level documentation and primary roles."""
        summary, specs, _ = self.get_summary(node)
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                total_lines = len(f.readlines())
        except:
            total_lines = 0

        if summary != "No docstring":
            self.results.append({
                "type": "📄",
                "name": os.path.basename(self.filename),
                "summary": summary,
                "specs": specs,
                "depth": 0,
                "lines": total_lines
            })
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        """[Spec 9.2] Capture class definitions and associated industrial logic."""
        summary, specs, lines = self.get_summary(node)
        self.results.append({
            "type": "🏛️",
            "name": node.name,
            "summary": summary,
            "specs": specs,
            "depth": 0,
            "lines": lines
        })
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = None

    def visit_AsyncFunctionDef(self, node):
        """Redirect async functions to the standard function visitor."""
        self.visit_FunctionDef(node)

    def visit_FunctionDef(self, node):
        """[Spec 9.3] Capture function/method definitions and compliance markers."""
        summary, specs, lines = self.get_summary(node)
        if node.name.startswith('_') and summary == "No docstring":
            return

        self.results.append({
            "type": "🛠️" if self.current_class else "🔧",
            "name": node.name,
            "summary": summary,
            "specs": specs,
            "depth": 1 if self.current_class else 0,
            "lines": lines
        })

def generate_density_bar(lines, max_lines=600):
    """Creates an ASCII bar representing code density."""
    bar_len = 15
    filled = int((lines / max_lines) * bar_len)
    filled = min(filled, bar_len)
    return "[" + "█" * filled + "░" * (bar_len - filled) + "]"

def run_audit():
    """Scans the project and prints a high-fidelity alignment map."""
    header = f"{'FILE':<20} | {'OBJECT':<35} | {'SPEC':<12} | {'LINES':<5} | {'DENSITY':<17} | {'SUMMARY'}"
    print(header)
    print("-" * 165)
    
    paths = [f for f in os.listdir('.') if f.endswith('.py')]
    if os.path.exists('lib'):
        paths += [os.path.join('lib', f) for f in os.listdir('lib') if f.endswith('.py')]
        
    global_stats = {"files": 0, "classes": 0, "functions": 0, "specs": set(), "total_lines": 0}
    report_content = ["# NINELIVES SYSTEM MANIFEST\n", "## Forensic Logic Audit\n"]
    report_content.append("| File | Object | Specs | Lines | Summary |")
    report_content.append("| :--- | :--- | :--- | :--- | :--- |")

    for path in sorted(paths):
        if path == 'project_mapper.py' or any(x in path for x in ['original', 'initial', 'backup']):
            continue
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
            
            visitor = IndustrialMapper(path)
            visitor.visit(tree)
            
            first_row = True
            for res in visitor.results:
                fname = path if first_row else ""
                prefix = "  └─ " if res['depth'] > 0 else ""
                obj_name = f"{res['type']} {res['name']}"
                display_name = f"{prefix}{obj_name}"
                density = generate_density_bar(res['lines'])
                
                # Update stats
                if res['type'] == "📄": 
                    global_stats["files"] += 1
                    global_stats["total_lines"] += res['lines']
                elif res['type'] == "🏛️": global_stats["classes"] += 1
                elif res['type'] in ["🛠️", "🔧"]: global_stats["functions"] += 1
                
                if res['specs']:
                    for s in res['specs'].split(", "):
                        global_stats["specs"].add(s)

                print(f"{fname:<20} | {display_name:<35} | {res['specs']:<12} | {res['lines']:<5} | {density:<17} | {res['summary']}")
                report_content.append(f"| {fname} | {display_name} | {res['specs']} | {res['lines']} | {res['summary']} |")
                first_row = False
            if visitor.results:
                print("-" * 165)
        except Exception as e:
            print(f"{path:<20} | Error: {str(e)[:40]}")

    summary_block = f"\n[FORENSIC SUMMARY]\n"
    summary_block += f"Total Fleet Files:    {global_stats['files']}\n"
    summary_block += f"Total Fleet Lines:    {global_stats['total_lines']}\n"
    summary_block += f"Total Logical Classes: {global_stats['classes']}\n"
    summary_block += f"Total Control Points:  {global_stats['functions']}\n"
    summary_block += f"Compliance Density:    {len(global_stats['specs'])} Industrial Specs Identified\n"
    
    print(summary_block)
    
    # Save Report
    with open("SYSTEM_MANIFEST.md", "w", encoding="utf-8") as rf:
        rf.write("\n".join(report_content))
        rf.write(f"\n\n## Summary\n{summary_block.replace('[FORENSIC SUMMARY]', '')}")
    
    print(f"Report generated: SYSTEM_MANIFEST.md")

if __name__ == "__main__":
    run_audit()