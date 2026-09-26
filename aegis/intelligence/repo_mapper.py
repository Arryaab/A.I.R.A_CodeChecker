import ast
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

@dataclass
class Symbol:
    name: str
    type: str  # "class" or "function"
    line_start: int
    line_end: int
    docstring: str | None

@dataclass
class FileMap:
    filepath: str
    imports: List[str]
    symbols: List[Symbol]

class RepoMapper:
    """Builds an AST-based intelligence map of a Python repository."""
    
    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.files: Dict[str, FileMap] = {}

    def map_repository(self) -> Dict[str, Any]:
        """Scans the repository and builds a semantic map."""
        for file_path in self.root_dir.rglob("*.py"):
            # Skip hidden dirs, virtualenvs, etc.
            if any(part.startswith('.') or part in ('venv', 'env', '__pycache__') for part in file_path.parts):
                continue
                
            try:
                self._map_file(file_path)
            except Exception as e:
                print(f"Warning: Failed to parse {file_path}: {e}")

        return {k: asdict(v) for k, v in self.files.items()}

    def _map_file(self, file_path: Path):
        rel_path = str(file_path.relative_to(self.root_dir)).replace("\\", "/")
        source = file_path.read_text(encoding="utf-8")
        
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            return  # Skip files with syntax errors

        imports = []
        symbols = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
            
            elif isinstance(node, ast.ClassDef):
                docstring = ast.get_docstring(node)
                symbols.append(Symbol(
                    name=node.name,
                    type="class",
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    docstring=docstring
                ))
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                docstring = ast.get_docstring(node)
                symbols.append(Symbol(
                    name=node.name,
                    type="function",
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    docstring=docstring
                ))

        self.files[rel_path] = FileMap(
            filepath=rel_path,
            imports=list(set(imports)),
            symbols=symbols
        )

    def generate_prompt_context(self) -> str:
        """Generates a compressed string representation of the repository for LLM context."""
        lines = ["# Repository Structure Map"]
        for filepath, fmap in self.files.items():
            lines.append(f"\n## File: {filepath}")
            if fmap.imports:
                lines.append(f"Imports: {', '.join(fmap.imports)}")
            for sym in fmap.symbols:
                lines.append(f"- {sym.type} {sym.name} (Lines {sym.line_start}-{sym.line_end})")
                if sym.docstring:
                    first_line = sym.docstring.split('\\n')[0][:100]
                    lines.append(f"  Doc: {first_line}")
        return "\n".join(lines)

if __name__ == "__main__":
    import sys
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    mapper = RepoMapper(target)
    mapper.map_repository()
    print(mapper.generate_prompt_context())
