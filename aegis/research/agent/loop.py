from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from aegis.research.models.base import ModelProvider, ModelResponse, ToolCall
from aegis.research.sandbox.isolation import AgentSandbox
from aegis.research.tools.workspace_tools import ToolExecutionResult, WorkspaceToolSet

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert autonomous software engineer working inside a sandboxed repository.
Your task is to fix a bug in the codebase.

You have access to the following workspace tools:
- `list_files`: Inspect the repository layout.
- `read_file`: Read source code or test files.
- `write_file`: Overwrite or create a file with complete content.
- `edit_file`: Replace an exact snippet of code in a file.
- `run_tests`: Run pytest to observe baseline failures and verify your fix.
- `finish`: Complete the task and provide a diagnosis summary.

GUIDELINES:
1. Always first inspect the repository and run existing tests to see what fails.
2. Read the source file where the bug resides.
3. Apply the minimal correct change using `edit_file` or `write_file`.
4. Re-run tests using `run_tests` to verify your solution passes.
5. When all visible tests pass and you are satisfied, call `finish`.

Return your tool calls directly as function calls.
"""


def redact_secrets(text: str) -> str:
    """Redact sensitive patterns (API keys, authorization tokens, passwords)."""
    if not text:
        return ""
    # Redact common key prefixes
    patterns = [
        r'(?:sk-[a-zA-Z0-9_-]{20,})',
        r'(?:AIza[0-9A-Za-z-_]{30,})',
        r'(?:AQ\.[a-zA-Z0-9_-]{30,})',
        r'(?:bearer\s+[a-zA-Z0-9_\-\.]{20,})',
        r'(?:ghp_[a-zA-Z0-9]{36})',
    ]
    redacted = text
    for p in patterns:
        redacted = re.sub(p, "[REDACTED_SECRET]", redacted, flags=re.IGNORECASE)
    return redacted


@dataclass
class AgentStepRecord:
    step_index: int
    timestamp: float
    request_messages_count: int
    model_response_content: Optional[str]
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    prompt_tokens: int
    completion_tokens: int
    duration_seconds: float


@dataclass
class AgentRunResult:
    task_id: str
    success_signaled: bool
    termination_reason: str
    steps: List[AgentStepRecord]
    modified_files: List[str]
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    agent_duration_seconds: float
    error_message: Optional[str] = None


class AgentExecutionLoop:
    """Orchestrates real tool-based iterative coding agent execution."""

    def __init__(
        self,
        provider: ModelProvider,
        sandbox: AgentSandbox,
        max_iterations: int = 8,
    ):
        self.provider = provider
        self.sandbox = sandbox
        self.max_iterations = max_iterations
        self.tool_set = WorkspaceToolSet(sandbox)

    def execute(self, task_id: str, problem_md: str, metadata: Dict[str, Any]) -> AgentRunResult:
        start_time = time.time()
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Task ID: {task_id}\n\n"
                    f"Problem Description:\n{problem_md}\n\n"
                    f"Please investigate the repository, reproduce the issue by running tests, "
                    f"apply the fix, and verify it passes."
                ),
            },
        ]

        steps: List[AgentStepRecord] = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        success_signaled = False
        termination_reason = "MAX_ITERATIONS"
        error_message = None
        tool_schemas = self.tool_set.get_tool_schemas()

        for step_idx in range(1, self.max_iterations + 1):
            step_start = time.time()

            try:
                resp: ModelResponse = self.provider.generate(
                    messages=messages,
                    tools=tool_schemas,
                )
            except Exception as e:
                logger.error(f"Model generation error on step {step_idx}: {e}")
                error_message = str(e)
                termination_reason = "MODEL_FAILURE"
                break

            total_prompt_tokens += resp.prompt_tokens
            total_completion_tokens += resp.completion_tokens

            step_tool_calls_log: List[Dict[str, Any]] = []
            step_tool_results_log: List[Dict[str, Any]] = []

            # 1. Handle tool calls
            if resp.has_tool_calls:
                # Add assistant turn to message history (preserving provider continuation metadata)
                messages.append({
                    "role": "assistant",
                    "content": resp.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": tc.arguments},
                            "provider_metadata": tc.provider_metadata,
                        }
                        for tc in resp.tool_calls
                    ],
                    "provider_parts": resp.provider_parts,
                })

                for tc in resp.tool_calls:
                    exec_res: ToolExecutionResult = self.tool_set.execute(tc.name, tc.arguments)

                    step_tool_calls_log.append({
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments,
                    })

                    # Safe serialized output for prompt and logging
                    clean_output_str = redact_secrets(json.dumps(exec_res.output, indent=2))

                    step_tool_results_log.append({
                        "id": tc.id,
                        "name": tc.name,
                        "output": exec_res.output,
                        "is_error": exec_res.is_error,
                        "duration_seconds": exec_res.duration_seconds,
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": clean_output_str,
                        "output_dict": exec_res.output,
                    })

                    if tc.name == "finish":
                        success_signaled = True
                        termination_reason = "FINISHED"

                step_record = AgentStepRecord(
                    step_index=step_idx,
                    timestamp=step_start,
                    request_messages_count=len(messages),
                    model_response_content=redact_secrets(resp.content or ""),
                    tool_calls=step_tool_calls_log,
                    tool_results=step_tool_results_log,
                    prompt_tokens=resp.prompt_tokens,
                    completion_tokens=resp.completion_tokens,
                    duration_seconds=time.time() - step_start,
                )
                steps.append(step_record)

                if success_signaled:
                    break

            else:
                # No tool call returned
                content = resp.content or ""
                messages.append({"role": "assistant", "content": content})

                # Check if assistant announced finish in free text
                if "finish" in content.lower() or "fixed" in content.lower():
                    # Give assistant one chance to call finish or test
                    messages.append({
                        "role": "user",
                        "content": "If you have completed and tested your fix, please call the `finish` tool with a summary. Otherwise, use `run_tests` or `edit_file`.",
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": "Please use one of the available tools (`list_files`, `read_file`, `edit_file`, `run_tests`, or `finish`).",
                    })

                step_record = AgentStepRecord(
                    step_index=step_idx,
                    timestamp=step_start,
                    request_messages_count=len(messages),
                    model_response_content=redact_secrets(content),
                    tool_calls=[],
                    tool_results=[],
                    prompt_tokens=resp.prompt_tokens,
                    completion_tokens=resp.completion_tokens,
                    duration_seconds=time.time() - step_start,
                )
                steps.append(step_record)

        total_duration = time.time() - start_time
        return AgentRunResult(
            task_id=task_id,
            success_signaled=success_signaled,
            termination_reason=termination_reason,
            steps=steps,
            modified_files=sorted(list(self.tool_set.modified_files)),
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            agent_duration_seconds=total_duration,
            error_message=error_message,
        )
