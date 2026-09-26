import json
import time
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

@dataclass
class TraceSpan:
    name: str
    start_time: float
    end_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def complete(self, **kwargs):
        self.end_time = time.time()
        self.metadata.update(kwargs)

@dataclass
class AgentTrace:
    trace_id: str
    project_dir: str
    spans: List[TraceSpan] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    
    def add_span(self, name: str, **metadata) -> TraceSpan:
        span = TraceSpan(name=name, start_time=time.time(), metadata=metadata)
        self.spans.append(span)
        return span
        
    def save(self):
        trace_dir = Path(".aegis/traces")
        trace_dir.mkdir(parents=True, exist_ok=True)
        file_path = trace_dir / f"{self.trace_id}.json"
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

_current_trace: Optional[AgentTrace] = None

def start_trace(trace_id: str, project_dir: str) -> AgentTrace:
    global _current_trace
    _current_trace = AgentTrace(trace_id=trace_id, project_dir=project_dir)
    return _current_trace

def get_current_trace() -> Optional[AgentTrace]:
    return _current_trace
