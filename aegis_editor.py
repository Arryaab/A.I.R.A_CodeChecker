"""Aegis-Lite Web Editor — Programiz-style Python editor with AI auto-fix.

Run:
    set AEGIS_API_KEY=your-key-here
    python aegis_editor.py

Then open http://localhost:5000 in your browser.

Features:
- CodeMirror-powered Python editor with syntax highlighting
- Real-time syntax checking as you type
- One-click AI-powered bug fixing via Gemini
- Code execution with output display
- Side-by-side original vs fixed code view
- Dark theme professional UI
"""

from __future__ import annotations

import ast
import json
import os
import sys
import time
import re
import subprocess
from pathlib import Path

from flask import Flask, request, jsonify, render_template_string

# Add project root to path for aegis imports
sys.path.insert(0, str(Path(__file__).parent))

from aegis.llm import GeminiProvider, SYSTEM_PROMPT

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("AEGIS_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
MODEL = os.environ.get("AEGIS_MODEL", "gemini-3.8-flash")

def get_provider():
    """Get LLM provider — Gemini if key available, otherwise Mock."""
    if API_KEY:
        return GeminiProvider(api_key=API_KEY, model=MODEL)
    return None

def extract_errors(code: str, stderr: str = "") -> list:
    """Extract all distinct syntax and runtime errors from code/stderr."""
    errors = []
    
    # 1. Syntax Errors
    try:
        ast.parse(code)
    except SyntaxError as e:
        errors.append({
            "id": f"err_syn_{int(time.time()*1000)}",
            "type": "SyntaxError",
            "message": e.msg,
            "line": e.lineno,
            "source": "check"
        })
        return errors  # Python won't run if there's a syntax error
    except Exception as e:
        pass
        
    # 2. Runtime Errors
    if stderr:
        lines = stderr.strip().splitlines()
        if lines:
            last_line = lines[-1]
            err_type = last_line.split(":")[0] if ":" in last_line else "RuntimeError"
            
            line_no = None
            for line in reversed(lines):
                m = re.search(r'line (\d+)', line)
                if m:
                    line_no = int(m.group(1))
                    break
                    
            errors.append({
                "id": f"err_run_{int(time.time()*1000)}",
                "type": err_type.strip(),
                "message": last_line.strip(),
                "line": line_no,
                "source": "run"
            })
            
    return errors

# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    mode = "gemini" if API_KEY else "ollama"
    model_name = MODEL if API_KEY else (MODEL.replace("ollama/", "") if MODEL.startswith("ollama/") else "qwen2.5-coder")
    return render_template_string(EDITOR_HTML, mode=mode, model_name=model_name)


@app.route("/api/run", methods=["POST"])
def run_code():
    """Execute Python code and return output."""
    code = request.json.get("code", "")
    if not code.strip():
        return jsonify({"output": "", "error": "", "exit_code": 0, "errors": []})

    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=10,
            cwd=str(Path(__file__).parent),
        )
        
        errs = extract_errors(code, result.stderr if result.returncode != 0 else "")
        
        return jsonify({
            "output": result.stdout,
            "error": result.stderr,
            "exit_code": result.returncode,
            "errors": errs
        })
    except subprocess.TimeoutExpired:
        errs = [{"id": f"err_run_{int(time.time()*1000)}", "type": "TimeoutError", "message": "Execution timed out (10s limit)", "line": None, "source": "run"}]
        return jsonify({"output": "", "error": "⏱ Execution timed out (10s limit)", "exit_code": 1, "errors": errs})
    except Exception as e:
        errs = [{"id": f"err_run_{int(time.time()*1000)}", "type": "SystemError", "message": str(e), "line": None, "source": "run"}]
        return jsonify({"output": "", "error": str(e), "exit_code": 1, "errors": errs})


@app.route("/api/check", methods=["POST"])
def check_code():
    """Check Python syntax only (no execution) — called on every keystroke."""
    code = request.json.get("code", "")
    if not code.strip():
        return jsonify({"valid": True, "errors": []})

    errs = extract_errors(code)
    
    return jsonify({
        "valid": len(errs) == 0,
        "syntax_errors": [e["message"] for e in errs],
        "errors": errs,
        "runtime_errors": [],
    })


@app.route("/api/fix", methods=["POST"])
def fix_code():
    """Send code + error to LLM and get a fix."""
    code = request.json.get("code", "")
    error_info = request.json.get("error", "")

    if not API_KEY:
        return jsonify({
            "success": False,
            "error": "No API key configured. Set AEGIS_API_KEY environment variable.",
        })

    # If no error info provided, try running the code to get one
    if not error_info or not error_info.strip():
        try:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True, timeout=5,
            )
            if proc.returncode != 0 and proc.stderr:
                error_info = proc.stderr
            else:
                # Also check syntax
                errs = extract_errors(code)
                if errs:
                    error_info = "\n".join([e["message"] for e in errs])
                else:
                    return jsonify({"success": False, "error": "No errors found in the code!"})
        except Exception as e:
            error_info = str(e)

    prompt = f"""Fix this Python code. The code has the following error:

Error:
```
{error_info}
```

Code:
```python
{code}
```

Make the ABSOLUTE MINIMAL changes necessary to resolve the error.
Only fix the logic or syntax error. Do NOT rewrite the entire code, do NOT change variable names unnecessarily, and preserve the original structure as much as possible.

Return ONLY valid JSON in this exact format (wrapped in ```json fences):
```json
{{
    "diagnosis": "Brief explanation of what was wrong",
    "fixed_code": "The complete corrected Python code"
}}
```"""

    try:
        # Determine if we should use Ollama or Gemini
        use_ollama = not API_KEY or MODEL.startswith("ollama/")
        
        if use_ollama:
            ollama_model = MODEL.replace("ollama/", "") if MODEL.startswith("ollama/") else "qwen2.5-coder"
            payload = {
                "model": ollama_model,
                "prompt": prompt,
                "system": SYSTEM_PROMPT,
                "stream": False,
                "options": {"temperature": 0.2}
            }
            req = urllib.request.Request("http://localhost:11434/api/generate", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            try:
                res = urllib.request.urlopen(req, timeout=120)
                result = json.loads(res.read().decode())
                content = result.get("response", "")
                actual_model = f"ollama/{ollama_model}"
            except Exception as e:
                return jsonify({"success": False, "error": f"Failed to connect to local AI (Ollama). Install Ollama from ollama.com and run 'ollama run {ollama_model}'. Error: {e}"})
        else:
            # Single-attempt API call — no long retry loops for the web UI
            import google.generativeai as genai
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel(
                model_name=MODEL,
                system_instruction=SYSTEM_PROMPT
            )
            gen_config = genai.types.GenerationConfig(temperature=0.2)

            response = model.generate_content(prompt, generation_config=gen_config)
            content = response.text.strip()
            actual_model = MODEL

        # Extract JSON from code fences
        json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1).strip()

        data = json.loads(content)

        return jsonify({
            "success": True,
            "fixed_code": data.get("fixed_code", code),
            "diagnosis": data.get("diagnosis", "Fix applied"),
            "model": actual_model,
        })

    except json.JSONDecodeError:
        # If JSON parsing fails, try to extract code directly
        code_match = re.search(r'```python\s*(.*?)\s*```', content, re.DOTALL)
        if code_match:
            return jsonify({
                "success": True,
                "fixed_code": code_match.group(1),
                "diagnosis": "Fix extracted from response",
                "model": actual_model,
            })
        return jsonify({"success": False, "error": "Could not parse AI response. Try again."})

    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower():
            return jsonify({
                "success": False,
                "error": "Rate limited — please wait 60 seconds and try again. (Free tier: 5 requests/min)"
            })
        return jsonify({"success": False, "error": f"AI error: {err}"})


# ---------------------------------------------------------------------------
# HTML Template — Full Editor UI
# ---------------------------------------------------------------------------
EDITOR_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aegis-Lite Editor — AI-Powered Python Editor</title>

    <!-- CodeMirror 6 via CDN -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.18/codemirror.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.18/theme/material-darker.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.18/addon/hint/show-hint.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.18/codemirror.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.18/mode/python/python.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.18/addon/edit/matchbrackets.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.18/addon/edit/closebrackets.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.18/addon/selection/active-line.min.js"></script>

    <style>
        :root {
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --bg-tertiary: #0f3460;
            --accent: #e94560;
            --accent-hover: #ff6b81;
            --text: #eee;
            --text-muted: #999;
            --success: #2ed573;
            --warning: #ffa502;
            --error: #ff4757;
            --border: #2a2a4a;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text);
            min-height: 100vh;
        }

        /* Header */
        .header {
            background: var(--bg-secondary);
            border-bottom: 2px solid var(--accent);
            padding: 12px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .header h1 {
            font-size: 20px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .header h1 .logo { color: var(--accent); font-size: 24px; }
        .header h1 span { color: var(--text-muted); font-weight: 300; font-size: 14px; }

        .header-controls { display: flex; gap: 10px; align-items: center; }

        .status-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }
        .status-badge.connected { background: rgba(46, 213, 115, 0.2); color: var(--success); }
        .status-badge.disconnected { background: rgba(255, 71, 87, 0.2); color: var(--error); }

        /* Main Layout */
        .main {
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: 1fr auto;
            height: calc(100vh - 56px);
        }

        /* Panels */
        .panel {
            display: flex;
            flex-direction: column;
            border: 1px solid var(--border);
        }

        .panel-header {
            background: var(--bg-secondary);
            padding: 8px 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            min-height: 40px;
        }

        .panel-header h3 {
            font-size: 13px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-muted);
        }

        .panel-body { flex: 1; overflow: auto; position: relative; }

        /* Buttons */
        .btn {
            padding: 6px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .btn:disabled { opacity: 0.5; cursor: not-allowed; }

        .btn-run { background: var(--success); color: #000; }
        .btn-run:hover:not(:disabled) { background: #7bed9f; }

        .btn-fix { background: var(--accent); color: #fff; }
        .btn-fix:hover:not(:disabled) { background: var(--accent-hover); }

        .btn-clear { background: transparent; color: var(--text-muted); border: 1px solid var(--border); }
        .btn-clear:hover:not(:disabled) { color: var(--text); border-color: var(--text-muted); }

        .btn-group { display: flex; gap: 8px; }

        /* CodeMirror customization */
        .CodeMirror {
            height: 100% !important;
            font-size: 15px;
            font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
            line-height: 1.6;
        }

        /* Output panel */
        .output-area {
            background: #0d1117;
            color: #c9d1d9;
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            font-size: 14px;
            padding: 16px;
            white-space: pre-wrap;
            height: 100%;
            overflow: auto;
            line-height: 1.5;
        }

        .output-error { color: var(--error); }
        .output-success { color: var(--success); }

        /* Error banner */
        .error-banner {
            background: rgba(255, 71, 87, 0.15);
            border-left: 3px solid var(--error);
            padding: 8px 16px;
            font-size: 13px;
            display: none;
            align-items: center;
            gap: 8px;
        }

        .error-banner.visible { display: flex; }

        .error-banner .error-text { flex: 1; color: var(--error); }
        .error-banner .fix-hint { color: var(--text-muted); font-size: 12px; }
        
        .banner-close {
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 18px;
            cursor: pointer;
            padding: 0 4px;
        }
        .banner-close:hover { color: var(--text); }

        /* Diagnosis box */
        .diagnosis-box {
            background: rgba(46, 213, 115, 0.1);
            border-left: 3px solid var(--success);
            padding: 10px 16px;
            margin: 0;
            font-size: 13px;
            display: none;
        }
        .diagnosis-box.visible { display: block; }
        .diagnosis-box strong { color: var(--success); }

        /* Loading spinner */
        .spinner {
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 2px solid transparent;
            border-top: 2px solid currentColor;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Toast notifications & stacking popups */
        .toast-container {
            position: fixed;
            bottom: 24px;
            right: 24px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            z-index: 100;
        }

        .toast {
            position: relative;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 15px;
            background: #2a2a4a;
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 14px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            animation: slideIn 0.3s ease;
            opacity: 1;
        }

        .toast.success { border-left: 4px solid var(--success); }
        .toast.error { border-left: 4px solid var(--error); }
        
        @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        @keyframes slideOut { to { transform: translateX(100%); opacity: 0; } }
        
        .toast.hiding { animation: slideOut 0.3s ease forwards; }

        .toast-content { display: flex; flex-direction: column; gap: 4px; flex: 1; }
        .toast-title { font-weight: bold; font-size: 13px; }
        .toast-msg { font-size: 12px; color: var(--text-muted); }
        
        .toast-actions { display: flex; gap: 8px; align-items: center; }
        
        .toast-btn { 
            background: var(--accent); 
            color: white; 
            border: none; 
            padding: 6px 10px; 
            border-radius: 4px; 
            font-size: 12px; 
            cursor: pointer; 
            font-weight: bold;
        }
        .toast-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .toast-btn:hover:not(:disabled) { background: var(--accent-hover); }
        
        .toast-close { 
            background: none; 
            border: none; 
            color: var(--text-muted); 
            cursor: pointer; 
            font-size: 18px; 
            margin-left: 4px; 
            padding: 0 4px; 
        }
        .toast-close:hover { color: white; }

        /* Status line */
        .status-line {
            background: var(--bg-secondary);
            border-top: 1px solid var(--border);
            padding: 4px 16px;
            font-size: 12px;
            color: var(--text-muted);
            display: flex;
            justify-content: space-between;
            grid-column: 1 / -1;
        }

        /* Responsive */
        @media (max-width: 900px) {
            .main { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>

<div class="header">
    <h1>
        <span class="logo">⚡</span> Aegis-Lite Editor
        <span>AI-Powered Python Editor</span>
    </h1>
    <div class="header-controls">
        {% if mode == 'gemini' %}
        <span class="status-badge connected">🟢 Gemini Connected</span>
        {% else %}
        <span class="status-badge" style="background: rgba(255, 165, 2, 0.2); color: var(--warning);">🟡 Local AI (Ollama: {{ model_name }})</span>
        {% endif %}
        <div class="btn-group">
            <button class="btn btn-run" onclick="runCode()" id="btnRun">▶ Run</button>
            <button class="btn btn-fix" onclick="fixCode()" id="btnFix">
                🔧 Auto Fix
            </button>
            <button class="btn btn-clear" onclick="clearOutput()">Clear</button>
        </div>
    </div>
</div>

<div class="main">
    <!-- Editor Panel -->
    <div class="panel">
        <div class="panel-header">
            <h3>📝 Code Editor</h3>
            <span id="syntaxStatus" style="font-size:12px; color:var(--success);">✓ Ready</span>
        </div>
        <div class="error-banner" id="errorBanner">
            <span class="error-text" id="errorText"></span>
            <span class="fix-hint">Press Ctrl+F to auto-fix</span>
            <button class="banner-close" onclick="dismissBanner()">×</button>
        </div>
        <div class="panel-body">
            <textarea id="codeEditor">
# Welcome to Aegis-Lite Editor!
# Write Python code here and press Run (▶) to execute.
# If there's an error, click Auto Fix (🔧) to let AI fix it.

def greet(name):
    return "Hello, " + name + "!"

print(greet("World"))
print(greet("Aegis"))
</textarea>
        </div>
    </div>

    <!-- Output Panel -->
    <div class="panel">
        <div class="panel-header">
            <h3>📤 Output</h3>
            <span id="runTime" style="font-size:12px; color:var(--text-muted);"></span>
        </div>
        <div class="diagnosis-box" id="diagnosisBox">
            <strong>🔍 AI Diagnosis:</strong> <span id="diagnosisText"></span>
        </div>
        <div class="panel-body">
            <div class="output-area" id="outputArea">Click ▶ Run to execute your code...</div>
        </div>
    </div>

    <!-- Status Line -->
    <div class="status-line">
        <span id="statusLeft">Line 1, Col 1</span>
        <span id="statusRight">Python {{ "3.x" }} | Aegis-Lite Editor</span>
    </div>
</div>

<div id="toastContainer" class="toast-container"></div>

<script>
    // Initialize CodeMirror
    const textarea = document.getElementById('codeEditor');
    const editor = CodeMirror.fromTextArea(textarea, {
        mode: 'python',
        theme: 'material-darker',
        lineNumbers: true,
        matchBrackets: true,
        autoCloseBrackets: true,
        styleActiveLine: true,
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: false,
        lineWrapping: true,
        extraKeys: {
            'Ctrl-Enter': () => runCode(),
            'Ctrl-F': () => fixCode(),
            'Ctrl-S': (cm) => { showToast('Auto-saved!', 'success'); },
            'Tab': (cm) => cm.replaceSelection('    '),
        }
    });

    // Cursor position tracking
    editor.on('cursorActivity', () => {
        const pos = editor.getCursor();
        document.getElementById('statusLeft').textContent =
            `Line ${pos.line + 1}, Col ${pos.ch + 1} | ${editor.getValue().length} chars`;
    });

    // Auto-check syntax as you type (debounced)
    let checkTimer = null;
    editor.on('change', () => {
        clearTimeout(checkTimer);
        checkTimer = setTimeout(checkSyntax, 800);
    });

    // ---- API calls ----

    async function checkSyntax() {
        const code = editor.getValue();
        if (!code.trim()) {
            setSyntaxOk();
            return;
        }

        try {
            const res = await fetch('/api/check', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code }),
            });
            const data = await res.json();

            if (data.valid) {
                setSyntaxOk();
            } else {
                // For typing check, just show the banner, don't spawn popups to prevent spam
                const errors = [...(data.syntax_errors || []), ...(data.runtime_errors || [])];
                setSyntaxError(errors.join('\n'));
            }
        } catch (e) {
            console.error('Check failed:', e);
        }
    }

    async function runCode() {
        const code = editor.getValue();
        const btn = document.getElementById('btnRun');
        const output = document.getElementById('outputArea');

        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Running...';
        output.className = 'output-area';
        output.textContent = 'Running...\n';

        const start = performance.now();

        try {
            const res = await fetch('/api/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code }),
            });
            const data = await res.json();
            const elapsed = ((performance.now() - start) / 1000).toFixed(2);

            document.getElementById('runTime').textContent = `${elapsed}s`;

            if (data.error && data.exit_code !== 0) {
                output.innerHTML = '';
                if (data.output) {
                    const outSpan = document.createElement('span');
                    outSpan.textContent = data.output;
                    output.appendChild(outSpan);
                }
                const errSpan = document.createElement('span');
                errSpan.className = 'output-error';
                errSpan.textContent = data.error;
                output.appendChild(errSpan);

                setSyntaxError(data.error.split('\n').pop());
                
                // Spawn individual popups for each distinct error found
                if (data.errors && data.errors.length > 0) {
                    data.errors.forEach(err => spawnToast('', 'error', err));
                }
            } else {
                output.innerHTML = '';
                const outSpan = document.createElement('span');
                outSpan.className = 'output-success';
                outSpan.textContent = data.output || '(No output)';
                output.appendChild(outSpan);
                setSyntaxOk();
            }
        } catch (e) {
            output.innerHTML = `<span class="output-error">Request failed: ${e.message}</span>`;
        }

        btn.disabled = false;
        btn.innerHTML = '▶ Run';
    }

    async function fixCode(specificError = null) {
        const code = editor.getValue();
        let errorInfo = specificError;
        
        if (!errorInfo || typeof errorInfo !== 'string') {
            const errorText = document.getElementById('errorText').textContent;
            const outputArea = document.getElementById('outputArea');
            errorInfo = errorText;
            if (!errorInfo) {
                const outputEl = outputArea.querySelector('.output-error');
                if (outputEl) errorInfo = outputEl.textContent;
            }
            if (!errorInfo) {
                await runCode();
                const outputEl = outputArea.querySelector('.output-error');
                if (outputEl) {
                    errorInfo = outputEl.textContent;
                } else {
                    showToast('No errors found — code looks good!', 'success');
                    return;
                }
            }
        }

        const btn = document.getElementById('btnFix');
        const origText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Fixing...';

        try {
            const res = await fetch('/api/fix', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code, error: errorInfo }),
            });
            const data = await res.json();

            if (data.success) {
                // Apply the fix
                editor.setValue(data.fixed_code);

                // Show diagnosis
                const diagBox = document.getElementById('diagnosisBox');
                const diagText = document.getElementById('diagnosisText');
                diagText.textContent = data.diagnosis;
                diagBox.classList.add('visible');

                setSyntaxOk();
                showToast('✨ Code fixed by AI!', 'success');

                // Auto-run the fixed code
                setTimeout(() => runCode(), 500);
            } else {
                showToast('Fix failed: ' + data.error, 'error');
            }
        } catch (e) {
            showToast('Request failed: ' + e.message, 'error');
        }

        btn.disabled = false;
        btn.innerHTML = origText;
    }
    
    async function fixSpecificError(id, errorMsg) {
        const toast = document.getElementById(id);
        if (toast) {
            const btn = toast.querySelector('.toast-btn');
            if (btn) {
                btn.disabled = true;
                btn.textContent = "Fixing...";
            }
        }
        await fixCode(errorMsg);
        dismissToast(id);
    }

    // ---- UI Helpers ----

    function setSyntaxOk() {
        document.getElementById('syntaxStatus').innerHTML = '<span style="color:var(--success)">✓ No errors</span>';
        document.getElementById('errorBanner').classList.remove('visible');
    }

    function setSyntaxError(msg) {
        document.getElementById('syntaxStatus').innerHTML = '<span style="color:var(--error)">✗ Error detected</span>';
        document.getElementById('errorText').textContent = msg;
        document.getElementById('errorBanner').classList.add('visible');
    }
    
    function dismissBanner() {
        document.getElementById('errorBanner').classList.remove('visible');
    }

    function clearOutput() {
        document.getElementById('outputArea').textContent = 'Click ▶ Run to execute your code...';
        document.getElementById('outputArea').className = 'output-area';
        document.getElementById('diagnosisBox').classList.remove('visible');
        document.getElementById('errorBanner').classList.remove('visible');
        document.getElementById('runTime').textContent = '';
        setSyntaxOk();
    }
    
    function spawnToast(msg, type = 'info', errData = null) {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        const id = 'toast_' + Date.now() + Math.floor(Math.random() * 1000);
        toast.id = id;
        
        if (errData) {
            const lineInfo = errData.line ? ` (Line ${errData.line})` : '';
            
            const content = document.createElement('div');
            content.className = 'toast-content';
            content.innerHTML = `<span class="toast-title">${errData.type}${lineInfo}</span><span class="toast-msg">${errData.message}</span>`;
            
            const actions = document.createElement('div');
            actions.className = 'toast-actions';
            
            const fixBtn = document.createElement('button');
            fixBtn.className = 'toast-btn';
            fixBtn.innerHTML = '🔧 Fix this';
            fixBtn.onclick = () => fixSpecificError(id, errData.message);
            
            const closeBtn = document.createElement('button');
            closeBtn.className = 'toast-close';
            closeBtn.innerHTML = '×';
            closeBtn.onclick = () => dismissToast(id);
            
            actions.appendChild(fixBtn);
            actions.appendChild(closeBtn);
            
            toast.appendChild(content);
            toast.appendChild(actions);
        } else {
            const content = document.createElement('div');
            content.className = 'toast-content';
            content.innerHTML = `<span class="toast-msg">${msg}</span>`;
            
            const closeBtn = document.createElement('button');
            closeBtn.className = 'toast-close';
            closeBtn.innerHTML = '×';
            closeBtn.onclick = () => dismissToast(id);
            
            toast.appendChild(content);
            toast.appendChild(closeBtn);
            
            setTimeout(() => dismissToast(id), 3000);
        }
        
        container.appendChild(toast);
    }

    function dismissToast(id) {
        const toast = document.getElementById(id);
        if (toast) {
            toast.classList.add('hiding');
            setTimeout(() => toast.remove(), 300);
        }
    }

    function showToast(msg, type) {
        spawnToast(msg, type);
    }

    // Initial syntax check
    setTimeout(checkSyntax, 500);
</script>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print()
    print("=" * 50)
    print("  Aegis-Lite Editor")
    print("  AI-Powered Python Editor")
    print("=" * 50)
    print()

    if API_KEY:
        print(f"  [OK] AI Connected (Gemini model: {MODEL})")
    else:
        ollama_model = MODEL.replace("ollama/", "") if MODEL.startswith("ollama/") else "qwen2.5-coder"
        print(f"  [OK] Local AI Mode Enabled (Ollama model: {ollama_model})")
        print("       Ensure Ollama is running (`ollama serve`)")
    print()
    print("  Open in browser: http://localhost:5000")
    print("  Press Ctrl+C to stop")
    print()

    app.run(host="0.0.0.0", port=5000, debug=False)
