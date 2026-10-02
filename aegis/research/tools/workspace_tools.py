from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from aegis.research.sandbox.isolation import AgentSandbox, SandboxSecurityViolation

logger = logging.getLogger(__name__)


@dataclass
class ToolExecutionResult:
    tool_name: str
    arguments: Dict[str, Any]
    output: Any
    is_error: bool = False
    duration_seconds: float = 0.0
    files_modified: List[str] = field(default_factory=list)


class WorkspaceToolSet:
    """Provides safe repository inspection, modification, and test execution tools."""

    def __init__(self, sandbox: AgentSandbox):
        self.sandbox = sandbox
        self.modified_files: Set[str] = set()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return function calling schemas for model providers."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files and subdirectories inside the workspace directory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "directory": {
                                "type": "string",
                                "description": "Relative path of directory to inspect (default '.')",
                            }
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the text contents of a file from the workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Relative file path inside workspace.",
                            },
                            "start_line": {
                                "type": "integer",
                                "description": "Optional 1-indexed start line number.",
                            },
                            "end_line": {
                                "type": "integer",
                                "description": "Optional 1-indexed end line number.",
                            },
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write or overwrite the complete content of a file in the workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Relative file path inside workspace.",
                            },
                            "content": {
                                "type": "string",
                                "description": "Full new content for the file.",
                            },
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Replace an exact target snippet in a file with replacement content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Relative file path inside workspace.",
                            },
                            "target": {
                                "type": "string",
                                "description": "Exact text substring to find and replace.",
                            },
                            "replacement": {
                                "type": "string",
                                "description": "New replacement text substring.",
                            },
                        },
                        "required": ["path", "target", "replacement"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_tests",
                    "description": "Run pytest against repository test suite to verify code changes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "test_target": {
                                "type": "string",
                                "description": "Optional specific test file or directory (default 'tests')",
                            }
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "finish",
                    "description": "Signal that the repair task is completed.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "summary": {
                                "type": "string",
                                "description": "Explanation of the root cause and the fix applied.",
                            }
                        },
                        "required": ["summary"],
                    },
                },
            },
        ]

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """Execute tool and return structured execution result."""
        start_time = time.time()
        files_modified: List[str] = []

        try:
            if tool_name == "list_files":
                directory = arguments.get("directory", ".")
                out = self._tool_list_files(directory)
            elif tool_name == "read_file":
                path = arguments.get("path") or arguments.get("filepath")
                if not path:
                    return ToolExecutionResult(tool_name, arguments, {"error": "Missing 'path' or 'filepath' argument"}, True)
                start = arguments.get("start_line")
                end = arguments.get("end_line")
                out = self._tool_read_file(path, start, end)
            elif tool_name == "write_file":
                path = arguments.get("path") or arguments.get("filepath")
                content = arguments.get("content") if "content" in arguments else arguments.get("code", "")
                if not path:
                    return ToolExecutionResult(tool_name, arguments, {"error": "Missing 'path' or 'filepath' argument"}, True)
                out = self._tool_write_file(path, content)
                files_modified.append(path)
                self.modified_files.add(path)
            elif tool_name == "edit_file":
                path = arguments.get("path") or arguments.get("filepath")
                target = arguments.get("target") or arguments.get("old_str") or arguments.get("old_content")
                replacement = arguments.get("replacement") or arguments.get("new_str") or arguments.get("new_content") or ""
                if not path or target is None:
                    return ToolExecutionResult(tool_name, arguments, {"error": "Missing 'path' or 'target' argument"}, True)
                out = self._tool_edit_file(path, target, replacement)
                files_modified.append(path)
                self.modified_files.add(path)
            elif tool_name == "run_tests":
                target = arguments.get("test_target")
                out = self._tool_run_tests(target)
            elif tool_name == "finish":
                summary = arguments.get("summary", "Task marked as finished.")
                out = {"status": "FINISHED", "summary": summary}
            else:
                out = {"error": f"Unknown tool: '{tool_name}'"}
                return ToolExecutionResult(
                    tool_name=tool_name,
                    arguments=arguments,
                    output=out,
                    is_error=True,
                    duration_seconds=time.time() - start_time,
                )

            duration = time.time() - start_time
            is_error = isinstance(out, dict) and "error" in out
            return ToolExecutionResult(
                tool_name=tool_name,
                arguments=arguments,
                output=out,
                is_error=is_error,
                duration_seconds=duration,
                files_modified=files_modified,
            )

        except SandboxSecurityViolation as e:
            duration = time.time() - start_time
            logger.warning(f"Sandbox violation in tool {tool_name}: {e}")
            return ToolExecutionResult(
                tool_name=tool_name,
                arguments=arguments,
                output={"error": f"SandboxSecurityViolation: {e}"},
                is_error=True,
                duration_seconds=duration,
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Error executing tool {tool_name}: {e}")
            return ToolExecutionResult(
                tool_name=tool_name,
                arguments=arguments,
                output={"error": str(e)},
                is_error=True,
                duration_seconds=duration,
            )

    def _tool_list_files(self, rel_dir: str) -> Dict[str, Any]:
        target_dir = self.sandbox.validate_path(rel_dir)
        if not target_dir.exists():
            return {"error": f"Directory not found: {rel_dir}"}
        if not target_dir.is_dir():
            return {"error": f"Not a directory: {rel_dir}"}

        items = []
        file_names = []
        for p in sorted(target_dir.iterdir()):
            if p.name in ("__pycache__", ".pytest_cache"):
                continue
            is_dir = p.is_dir()
            size = 0 if is_dir else p.stat().st_size
            items.append({
                "name": p.name,
                "is_directory": is_dir,
                "size_bytes": size,
                "relative_path": str(p.relative_to(self.sandbox.workspace_dir)).replace("\\", "/")
            })
            file_names.append(p.name)
        return {"directory": rel_dir, "items": items, "files": file_names, "count": len(items)}

    def _tool_read_file(self, rel_path: str, start: Optional[int], end: Optional[int]) -> Dict[str, Any]:
        target_file = self.sandbox.validate_path(rel_path)
        if not target_file.exists():
            return {"error": f"File not found: {rel_path}"}
        if not target_file.is_file():
            return {"error": f"Path is not a regular file: {rel_path}"}

        text = target_file.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines(keepends=True)
        total_lines = len(lines)

        s_idx = max(0, (start - 1)) if start is not None else 0
        e_idx = min(total_lines, end) if end is not None else total_lines
        content = "".join(lines[s_idx:e_idx])

        return {
            "path": rel_path,
            "total_lines": total_lines,
            "start_line": s_idx + 1 if lines else 0,
            "end_line": e_idx,
            "content": content
        }

    def _tool_write_file(self, rel_path: str, content: str) -> Dict[str, Any]:
        target_file = self.sandbox.validate_path(rel_path)
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content, encoding="utf-8")
        return {
            "path": rel_path,
            "status": "written",
            "lines_count": len(content.splitlines()),
            "bytes_written": len(content.encode("utf-8"))
        }

    def _tool_edit_file(self, rel_path: str, target: str, replacement: str) -> Dict[str, Any]:
        target_file = self.sandbox.validate_path(rel_path)
        if not target_file.exists():
            return {"error": f"File not found: {rel_path}"}

        text = target_file.read_text(encoding="utf-8", errors="replace")
        if target not in text:
            # Try indentation-resilient line matching
            target_lines = target.splitlines()
            file_lines = text.splitlines()
            match_idx = -1
            match_indent = ""
            for i in range(len(file_lines) - len(target_lines) + 1):
                window = file_lines[i : i + len(target_lines)]
                if [w.strip() for w in window] == [t.strip() for t in target_lines]:
                    indent = window[0][: len(window[0]) - len(window[0].lstrip())]
                    if match_idx == -1:
                        match_idx = i
                        match_indent = indent
                    else:
                        match_idx = -2
                        break

            if match_idx >= 0:
                original_chunk = "\n".join(file_lines[match_idx : match_idx + len(target_lines)])
                repl_lines = replacement.splitlines()
                reindented_repl = "\n".join(
                    (match_indent + r.lstrip() if r.strip() else r) for r in repl_lines
                )
                target = original_chunk
                replacement = reindented_repl
            elif match_idx == -2:
                return {"error": f"Target snippet matches multiple locations. Please provide more context."}
            else:
                return {"error": f"Target snippet not found in {rel_path}. Make sure target matches exact indentation and whitespace."}

        count = text.count(target)
        if count > 1:
            return {"error": f"Target snippet matches multiple ({count}) locations. Please provide a more specific snippet."}

        new_text = text.replace(target, replacement, 1)
        target_file.write_text(new_text, encoding="utf-8")
        return {
            "path": rel_path,
            "status": "replaced",
            "occurrences_replaced": 1
        }

    def _tool_run_tests(self, test_target: Optional[str]) -> Dict[str, Any]:
        cmd = [sys.executable, "-m", "pytest"]
        if test_target:
            self.sandbox.validate_path(test_target)
            cmd.append(test_target)
        else:
            if (self.sandbox.workspace_dir / "tests").exists():
                cmd.append("tests")

        cmd.extend(["-v", "--tb=short", "--color=no", "-p", "no:cacheprovider"])
        exit_code, stdout, stderr, duration = self.sandbox.execute_in_sandbox(cmd, timeout=30.0)
        passed = (exit_code == 0)

        return {
            "exit_code": exit_code,
            "passed": passed,
            "stdout": stdout,
            "stderr": stderr,
            "duration_seconds": duration
        }
