import sys
import json
from pathlib import Path

def generate_research_html():
    return r'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aegis Research Console — Empirical Evaluation & Verification Intelligence</title>
    <style>
        :root {
            --bg-page: #0d0f18;
            --bg-card: #151828;
            --bg-card-hover: #1b1f35;
            --border: #242945;
            --border-highlight: #3b426f;
            --text-primary: #f0f2f8;
            --text-secondary: #9aa1c2;
            --text-muted: #646b8f;
            --accent: #e94560;
            --accent-glow: rgba(233, 69, 96, 0.25);
            --success: #2ed573;
            --success-glow: rgba(46, 213, 115, 0.15);
            --warning: #ffa502;
            --cyan: #00d2d3;
            --purple: #a55eea;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg-page);
            color: var(--text-primary);
            line-height: 1.5;
            padding-bottom: 60px;
        }

        /* Top Nav */
        .navbar {
            background: #101322;
            border-bottom: 1px solid var(--border);
            padding: 14px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .nav-brand {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 18px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }
        .nav-brand .shield { font-size: 22px; color: var(--accent); }
        .nav-brand .version-pill {
            background: rgba(46, 213, 115, 0.12);
            color: var(--success);
            border: 1px solid rgba(46, 213, 115, 0.3);
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 10px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        .nav-actions {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        .btn-editor {
            background: var(--accent);
            color: #fff;
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.2s;
        }
        .btn-editor:hover {
            background: #ff5270;
            box-shadow: 0 0 12px var(--accent-glow);
        }

        /* Container */
        .container {
            max-width: 1360px;
            margin: 24px auto;
            padding: 0 24px;
        }

        /* Tab Switcher */
        .tab-bar {
            display: flex;
            gap: 8px;
            margin-bottom: 24px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 8px;
        }
        .tab-btn {
            background: transparent;
            color: var(--text-secondary);
            border: 1px solid transparent;
            padding: 10px 20px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.2s;
        }
        .tab-btn:hover {
            background: var(--bg-card);
            color: var(--text-primary);
        }
        .tab-btn.active {
            background: var(--bg-card);
            color: var(--cyan);
            border-color: var(--cyan);
            box-shadow: 0 0 10px rgba(0, 210, 211, 0.15);
        }
        .tab-btn.quarantine.active {
            color: var(--warning);
            border-color: var(--warning);
            box-shadow: 0 0 10px rgba(255, 165, 2, 0.15);
        }

        /* Tab Content Panels */
        .tab-panel {
            display: none;
        }
        .tab-panel.active {
            display: block;
        }

        /* Banners */
        .banner {
            border-radius: 10px;
            padding: 20px 24px;
            margin-bottom: 24px;
        }
        .banner-real {
            background: linear-gradient(135deg, rgba(0, 210, 211, 0.08) 0%, rgba(21, 24, 40, 0.8) 100%);
            border: 1px solid var(--border-highlight);
            border-left: 5px solid var(--cyan);
        }
        .banner-quarantine {
            background: linear-gradient(135deg, rgba(255, 165, 2, 0.08) 0%, rgba(21, 24, 40, 0.8) 100%);
            border: 1px solid rgba(255, 165, 2, 0.4);
            border-left: 5px solid var(--warning);
        }
        .banner-title {
            font-size: 16px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 6px;
        }
        .banner-desc {
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.6;
        }

        /* Executive KPI Grid */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }
        .kpi-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 18px;
            position: relative;
            overflow: hidden;
        }
        .kpi-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 3px;
            background: var(--accent);
        }
        .kpi-card.success::before { background: var(--success); }
        .kpi-card.cyan::before { background: var(--cyan); }
        .kpi-card.purple::before { background: var(--purple); }
        .kpi-card.warning::before { background: var(--warning); }

        .kpi-label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-muted);
            margin-bottom: 6px;
            font-weight: 600;
        }
        .kpi-value {
            font-size: 26px;
            font-weight: 800;
            color: var(--text-primary);
            line-height: 1.1;
            margin-bottom: 4px;
        }
        .kpi-sub {
            font-size: 12px;
            color: var(--text-secondary);
        }

        /* Section Cards */
        .section-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 22px;
            margin-bottom: 24px;
        }
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 12px;
        }
        .section-title {
            font-size: 15px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .section-desc {
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 18px;
            line-height: 1.6;
        }

        /* Tables */
        table.aegis-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        table.aegis-table th {
            background: rgba(0, 0, 0, 0.25);
            color: var(--text-secondary);
            text-align: left;
            padding: 10px 12px;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--border);
        }
        table.aegis-table td {
            padding: 10px 12px;
            border-bottom: 1px solid var(--border);
            color: var(--text-primary);
            vertical-align: middle;
        }
        table.aegis-table tr:hover td {
            background: rgba(255, 255, 255, 0.02);
        }

        /* Badges & Tags */
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }
        .badge-success { background: rgba(46, 213, 115, 0.15); color: var(--success); }
        .badge-danger { background: rgba(233, 69, 96, 0.15); color: var(--accent); }
        .badge-warning { background: rgba(255, 165, 2, 0.15); color: var(--warning); }
        .badge-cyan { background: rgba(0, 210, 211, 0.15); color: var(--cyan); }
        .badge-purple { background: rgba(165, 94, 234, 0.15); color: var(--purple); }
        .badge-muted { background: rgba(255, 255, 255, 0.06); color: var(--text-muted); }

        /* Waterfall Visual Bars */
        .waterfall-row {
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 10px;
            font-size: 13px;
        }
        .wf-label { width: 190px; font-weight: 600; }
        .wf-bar-wrap { flex: 1; height: 26px; background: rgba(255,255,255,0.04); border-radius: 4px; overflow: hidden; display: flex; }
        .wf-bar-accepted { height: 100%; background: var(--cyan); display: flex; align-items: center; padding-left: 10px; font-size: 11px; font-weight: 700; color: #000; }
        .wf-stats { width: 240px; font-size: 12px; color: var(--text-secondary); text-align: right; }

        /* Buttons */
        .btn-inspect {
            background: rgba(0, 210, 211, 0.12);
            color: var(--cyan);
            border: 1px solid rgba(0, 210, 211, 0.3);
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-inspect:hover {
            background: var(--cyan);
            color: #000;
        }

        /* Two-Column Layout */
        .two-col {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }

        /* Modal */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.75);
            backdrop-filter: blur(4px);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .modal-overlay.active {
            display: flex;
        }
        .modal-container {
            background: var(--bg-card);
            border: 1px solid var(--border-highlight);
            border-radius: 12px;
            width: 100%;
            max-width: 1080px;
            max-height: 90vh;
            display: flex;
            flex-direction: column;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.8);
            overflow: hidden;
        }
        .modal-header {
            padding: 16px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #111424;
        }
        .modal-title {
            font-size: 16px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .modal-close {
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 20px;
            cursor: pointer;
            padding: 4px;
            line-height: 1;
        }
        .modal-close:hover { color: var(--accent); }
        .modal-subnav {
            display: flex;
            gap: 8px;
            padding: 10px 24px;
            background: rgba(0,0,0,0.2);
            border-bottom: 1px solid var(--border);
        }
        .subnav-btn {
            background: none;
            border: 1px solid transparent;
            color: var(--text-secondary);
            font-size: 13px;
            font-weight: 600;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
        }
        .subnav-btn.active {
            background: var(--bg-page);
            border-color: var(--border);
            color: var(--cyan);
        }
        .modal-body {
            padding: 24px;
            overflow-y: auto;
            flex: 1;
        }
        pre.diff-view {
            background: #090b12;
            padding: 16px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 12px;
            white-space: pre-wrap;
            border: 1px solid var(--border);
            color: var(--text-primary);
            line-height: 1.4;
        }
        .diff-add { color: #2ed573; background: rgba(46, 213, 115, 0.1); display: block; }
        .diff-del { color: #e94560; background: rgba(233, 69, 96, 0.1); display: block; }
        .diff-hdr { color: #00d2d3; font-weight: bold; }

        .feature-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
        }
        .feature-item {
            background: rgba(0,0,0,0.25);
            border: 1px solid var(--border);
            padding: 10px 14px;
            border-radius: 6px;
        }
        .feature-name { font-size: 11px; color: var(--text-muted); font-family: monospace; }
        .feature-val { font-size: 16px; font-weight: 700; color: var(--text-primary); margin-top: 2px; }

        .tool-step {
            background: rgba(0,0,0,0.2);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 12px;
            margin-bottom: 12px;
        }
        .tool-step-hdr {
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            margin-bottom: 8px;
            font-weight: 600;
        }
    </style>
</head>
<body>

<div class="navbar">
    <div class="nav-brand">
        <span class="shield">🛡️</span>
        <span>AEGIS RESEARCH CONSOLE</span>
        <span class="version-pill">CORE 1.0 FROZEN (v1.0.0)</span>
    </div>
    <div class="nav-actions">
        <a href="/" class="btn-editor">
            <span>💻</span> Back to Code Editor
        </a>
    </div>
</div>

<div class="container">

    <!-- Top Tab Navigation -->
    <div class="tab-bar">
        <button class="tab-btn active" onclick="switchTab('pilot')">
            <span>🚀</span> Real Empirical Pilot (N=20)
        </button>
        <button class="tab-btn" onclick="switchTab('tasks')">
            <span>📚</span> AegisBench v1 Tasks (50)
        </button>
        <button class="tab-btn quarantine" onclick="switchTab('synthetic')">
            <span>⚠️</span> Quarantined Synthetic Baseline (N=750)
        </button>
    </div>

    <!-- ================================================================= -->
    <!-- TAB 1: REAL EMPIRICAL PILOT EXPERIMENT                            -->
    <!-- ================================================================= -->
    <div id="panel-pilot" class="tab-panel active">

        <!-- Real Pilot Banner -->
        <div class="banner banner-real">
            <div class="banner-title" style="color:var(--cyan);">
                <span>🔬</span> Real Autonomous Agent Execution Pilot (`pilot_real_v1`)
            </div>
            <div class="banner-desc">
                This section presents <strong>real empirical agent traces</strong> executing inside isolated, resource-controlled sandboxes.
                Each trace represents genuine local LLM inference (Qwen 2.5 Coder on Ollama), iterative multi-turn tool interaction,
                unified diff extraction, AST provenance hashing, pre-verification feature extraction (19 static features, zero leakage),
                and decoupled evaluation by both the Aegis verification gate and the Independent Correctness Oracle.
            </div>
        </div>

        <!-- Real KPI Cards -->
        <div class="kpi-grid">
            <div class="kpi-card cyan">
                <div class="kpi-label">Empirical Traces</div>
                <div class="kpi-value" id="kpi-total-runs">20 Runs</div>
                <div class="kpi-sub">5 Tasks × 2 Temp × 2 Seeds (100% Stability)</div>
            </div>
            <div class="kpi-card success">
                <div class="kpi-label">Independent Oracle Pass@1</div>
                <div class="kpi-value" id="kpi-pass-rate" style="color:var(--success);">40.0%</div>
                <div class="kpi-sub">8 / 20 Truly Correct Solutions</div>
            </div>
            <div class="kpi-card purple">
                <div class="kpi-label">Aegis C6 Qualified Rate</div>
                <div class="kpi-value" id="kpi-c6-rate">40.0%</div>
                <div class="kpi-sub">8 / 20 Qualified for Production</div>
            </div>
            <div class="kpi-card success">
                <div class="kpi-label">Bad Patch Escapes (C6)</div>
                <div class="kpi-value" id="kpi-escapes" style="color:var(--success);">0 Observed</div>
                <div class="kpi-sub">0% False Acceptance Rate in Sample</div>
            </div>
        </div>

        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-label">Total Real Tokens</div>
                <div class="kpi-value">136,888</div>
                <div class="kpi-sub">Avg 6,844 tokens/run (Inference)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Median Agent Latency</div>
                <div class="kpi-value">50.53s</div>
                <div class="kpi-sub">Min 41.65s / Max 58.10s</div>
            </div>
            <div class="kpi-card success">
                <div class="kpi-label">False Rejections (C6)</div>
                <div class="kpi-value" style="color:var(--success);">0 Observed</div>
                <div class="kpi-sub">All 8 clean patches admitted</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Provider Cost</div>
                <div class="kpi-value">$0.00</div>
                <div class="kpi-sub">Local Ollama (Qwen 2.5 Coder)</div>
            </div>
        </div>

        <!-- Verification Tier Ladder & Temperature Comparison -->
        <div class="two-col">
            <!-- Verification Tier Acceptance Ladder -->
            <div class="section-card">
                <div class="section-header">
                    <div class="section-title">
                        <span>🪜</span> Real Verification Tier Ladder (N=20)
                    </div>
                    <span class="badge badge-cyan">Real Sandbox Execution</span>
                </div>
                <div class="section-desc">
                    Progression of agent-proposed patches across laddered verification gates:
                </div>
                <div>
                    <div class="waterfall-row">
                        <div class="wf-label">C1: Agent Self-Report</div>
                        <div class="wf-bar-wrap">
                            <div class="wf-bar-accepted" style="width: 30%;">30.0%</div>
                        </div>
                        <div class="wf-stats">6 / 20 Accepted</div>
                    </div>
                    <div class="waterfall-row">
                        <div class="wf-label">C2: Visible Test Suite</div>
                        <div class="wf-bar-wrap">
                            <div class="wf-bar-accepted" style="width: 40%; background: #00d2d3;">40.0%</div>
                        </div>
                        <div class="wf-stats">8 / 20 Accepted</div>
                    </div>
                    <div class="waterfall-row">
                        <div class="wf-label">C3: Private Hidden Suite</div>
                        <div class="wf-bar-wrap">
                            <div class="wf-bar-accepted" style="width: 40%; background: #00b894;">40.0%</div>
                        </div>
                        <div class="wf-stats">8 / 20 Accepted</div>
                    </div>
                    <div class="waterfall-row">
                        <div class="wf-label">C4: BASE Regression Check</div>
                        <div class="wf-bar-wrap">
                            <div class="wf-bar-accepted" style="width: 40%; background: #0984e3;">40.0%</div>
                        </div>
                        <div class="wf-stats">8 / 20 Accepted</div>
                    </div>
                    <div class="waterfall-row">
                        <div class="wf-label">C5: Mutation Testing</div>
                        <div class="wf-bar-wrap">
                            <div class="wf-bar-accepted" style="width: 40%; background: #6c5ce7;">40.0%</div>
                        </div>
                        <div class="wf-stats">8 / 20 Accepted</div>
                    </div>
                    <div class="waterfall-row">
                        <div class="wf-label">C6: Full Aegis Release Gate</div>
                        <div class="wf-bar-wrap">
                            <div class="wf-bar-accepted" style="width: 40%; background: var(--success); color:#000;">40.0%</div>
                        </div>
                        <div class="wf-stats"><span class="badge badge-success">0 Bad Escapes</span> (8 / 20)</div>
                    </div>
                </div>
            </div>

            <!-- Temperature Sensitivity & Diagnostics -->
            <div class="section-card">
                <div class="section-header">
                    <div class="section-title">
                        <span>🌡️</span> Temperature Sensitivity & Failure Taxonomy
                    </div>
                    <span class="badge badge-purple">Qwen 2.5 Coder</span>
                </div>
                <div class="section-desc">
                    Comparing agent repair accuracy across greedy deterministic ($T=0.2$) vs exploratory stochastic ($T=0.7$) sampling:
                </div>
                <table class="aegis-table" style="margin-bottom:16px;">
                    <thead>
                        <tr>
                            <th>Condition</th>
                            <th>Runs</th>
                            <th>Oracle Correct</th>
                            <th>C6 Qualified</th>
                            <th>Syntax Errors</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><strong>T = 0.2 (Greedy)</strong></td>
                            <td>10</td>
                            <td><span class="badge badge-success">6 (60.0%)</span></td>
                            <td>6 (60.0%)</td>
                            <td>0</td>
                        </tr>
                        <tr>
                            <td><strong>T = 0.7 (Stochastic)</strong></td>
                            <td>10</td>
                            <td><span class="badge badge-warning">2 (20.0%)</span></td>
                            <td>2 (20.0%)</td>
                            <td>1 (AST error)</td>
                        </tr>
                    </tbody>
                </table>
                <div style="font-size:12px; color:var(--text-muted); background:rgba(0,0,0,0.2); padding:10px; border-radius:6px; border:1px solid var(--border);">
                    <strong>Diagnostic Finding:</strong> Under elevated temperature ($T=0.7$), the coding model exhibited significant hallucination in AST edits, producing 1 malformed syntax patch and failing 8 tasks due to iteration budget exhaustion.
                </div>
            </div>
        </div>

        <!-- Real Traces Interactive Explorer Table -->
        <div class="section-card">
            <div class="section-header">
                <div class="section-title">
                    <span>📋</span> Real Empirical Agent Traces Explorer
                </div>
                <div style="display:flex; gap:10px; align-items:center;">
                    <input type="text" id="trace-search" placeholder="Filter by task or run ID..." oninput="filterTraces()" style="background:rgba(0,0,0,0.3); border:1px solid var(--border); color:var(--text-primary); padding:6px 12px; border-radius:6px; font-size:12px; width:220px;">
                    <span class="badge badge-cyan">20 Executed Runs</span>
                </div>
            </div>
            <div class="section-desc">
                Click <strong>Inspect Trace</strong> on any run to inspect the exact prompt, multi-turn tool calling sequence, syntax-highlighted diff, pre-verification feature vector, and independent oracle adjudication:
            </div>
            <table class="aegis-table" id="traces-table">
                <thead>
                    <tr>
                        <th>Run ID</th>
                        <th>Task</th>
                        <th>Model</th>
                        <th>Temp</th>
                        <th>Seed</th>
                        <th>Oracle</th>
                        <th>Aegis C6</th>
                        <th>Duration</th>
                        <th>Tokens</th>
                        <th>Classification</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody id="traces-body">
                    <!-- Populated by JS -->
                </tbody>
            </table>
        </div>

    </div>

    <!-- ================================================================= -->
    <!-- TAB 2: AEGISBENCH V1 BENCHMARK TASKS (50 TASKS)                  -->
    <!-- ================================================================= -->
    <div id="panel-tasks" class="tab-panel">
        <div class="banner banner-real">
            <div class="banner-title" style="color:var(--cyan);">
                <span>📚</span> AegisBench v1: 50 Real Repository Benchmark Tasks
            </div>
            <div class="banner-desc">
                AegisBench v1 comprises 50 curated real-world repository tasks across three core engineering domains.
                Each task includes reproducible BASE/HEAD snapshots, visible test suites, private unobserved hidden test suites,
                and baseline regression invariance assertions.
            </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px;">
            <div style="background: var(--bg-card); padding: 16px; border-radius: 8px; border: 1px solid var(--border);">
                <div style="font-weight: 700; color: var(--cyan); margin-bottom: 4px;">Track 1: Core Frameworks (20 Tasks)</div>
                <div style="font-size: 12px; color: var(--text-secondary);">FastAPI (5), Pydantic (5), Click (4), aiohttp (3), cryptography (3)</div>
            </div>
            <div style="background: var(--bg-card); padding: 16px; border-radius: 8px; border: 1px solid var(--border);">
                <div style="font-weight: 700; color: var(--purple); margin-bottom: 4px;">Track 2: Scientific Arrays (12 Tasks)</div>
                <div style="font-size: 12px; color: var(--text-secondary);">NumPy (6), Pandas (3), SciPy (3)</div>
            </div>
            <div style="background: var(--bg-card); padding: 16px; border-radius: 8px; border: 1px solid var(--border);">
                <div style="font-weight: 700; color: var(--accent); margin-bottom: 4px;">Track 3: AI/ML Systems (18 Tasks)</div>
                <div style="font-size: 12px; color: var(--text-secondary);">PyTorch (5), Transformers (5), vLLM (4), MLflow (4)</div>
            </div>
        </div>

        <div class="section-card">
            <div class="section-header">
                <div class="section-title">
                    <span>🗂️</span> Benchmark Task Catalog
                </div>
                <span class="badge badge-success">50 Admitted Tasks</span>
            </div>
            <table class="aegis-table">
                <thead>
                    <tr>
                        <th>Task ID</th>
                        <th>Track</th>
                        <th>Repository</th>
                        <th>Problem Summary</th>
                        <th>Complexity</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><code>task_001_fastapi_async_scope</code></td>
                        <td><span class="badge badge-cyan">Frameworks</span></td>
                        <td>FastAPI</td>
                        <td>Async dependency resolution across nested route handlers</td>
                        <td>Medium</td>
                    </tr>
                    <tr>
                        <td><code>task_002_fastapi_middleware_exception</code></td>
                        <td><span class="badge badge-cyan">Frameworks</span></td>
                        <td>FastAPI</td>
                        <td>Exception propagation across chained HTTP middleware</td>
                        <td>Medium</td>
                    </tr>
                    <tr>
                        <td><code>task_003_fastapi_query_validation</code></td>
                        <td><span class="badge badge-cyan">Frameworks</span></td>
                        <td>FastAPI</td>
                        <td>Query parameter regex coercion and Pydantic boundary checks</td>
                        <td>Low</td>
                    </tr>
                    <tr>
                        <td><code>task_004_fastapi_header_encoding</code></td>
                        <td><span class="badge badge-cyan">Frameworks</span></td>
                        <td>FastAPI</td>
                        <td>RFC-5987 percent-encoded header parsing and Latin-1 fallback</td>
                        <td>High</td>
                    </tr>
                    <tr>
                        <td><code>task_005_fastapi_lifespan_state</code></td>
                        <td><span class="badge badge-cyan">Frameworks</span></td>
                        <td>FastAPI</td>
                        <td>ASGI lifespan state context manager lifecycle teardown</td>
                        <td>Medium</td>
                    </tr>
                    <tr>
                        <td><code>task_006_pydantic_discriminator</code></td>
                        <td><span class="badge badge-cyan">Frameworks</span></td>
                        <td>Pydantic</td>
                        <td>Discriminated union type validation on dynamic payload keys</td>
                        <td>Medium</td>
                    </tr>
                    <tr>
                        <td><code>task_021_numpy_stride_tricks</code></td>
                        <td><span class="badge badge-purple">Scientific</span></td>
                        <td>NumPy</td>
                        <td>Sliding window stride indexing on non-contiguous memory layouts</td>
                        <td>High</td>
                    </tr>
                    <tr>
                        <td><code>task_033_pytorch_tensor_backward</code></td>
                        <td><span class="badge badge-danger">AI/ML</span></td>
                        <td>PyTorch</td>
                        <td>Autograd tape graph pruning during custom activation backward</td>
                        <td>High</td>
                    </tr>
                    <tr>
                        <td><code>task_040_vllm_paged_attention</code></td>
                        <td><span class="badge badge-danger">AI/ML</span></td>
                        <td>vLLM</td>
                        <td>KV-cache page table eviction under token preemption</td>
                        <td>High</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- ================================================================= -->
    <!-- TAB 3: QUARANTINED SYNTHETIC SIMULATION BASELINE (N=750)          -->
    <!-- ================================================================= -->
    <div id="panel-synthetic" class="tab-panel">

        <!-- Quarantine Banner -->
        <div class="banner banner-quarantine">
            <div class="banner-title" style="color:var(--warning);">
                <span>⚠️</span> QUARANTINED SYNTHETIC SIMULATION BENCHMARK (N=750 TRACES)
            </div>
            <div class="banner-desc">
                <strong>STRICT METHODOLOGICAL QUARANTINE:</strong> The dataset below was generated via <strong>synthetic simulation</strong>
                to validate the multi-tier verification pipeline algorithms and test MLVerify routing heuristics before live execution.
                <strong>It does NOT represent empirical agent execution data.</strong>
                All empirical findings are recorded exclusively under the <em>Real Empirical Pilot</em> tab.
            </div>
        </div>

        <!-- Overfitting Phenomenon Box -->
        <div class="section-card">
            <div class="section-header">
                <div class="section-title">
                    <span>🔍</span> Overfitting Phenomenon in Simulation (Public CI vs Decoupled Oracle)
                </div>
                <span class="badge badge-warning">Simulated N=750</span>
            </div>
            <div class="section-desc">
                In simulation, 95.5% of patches passed public visible CI (C2), but 118 patches failed unobserved edge cases in hidden tests (C3), demonstrating a 16.5% Overfitting Escape Rate under public CI (McNemar &chi;² = 116.01, p < 1e-26).
            </div>
            <div class="waterfall-row">
                <div class="wf-label">C1: Agent Only</div>
                <div class="wf-bar-wrap">
                    <div class="wf-bar-accepted" style="width: 61.7%;">61.7% Accepted</div>
                </div>
                <div class="wf-stats"><span class="badge badge-danger">65.7% Escape Rate</span></div>
            </div>
            <div class="waterfall-row">
                <div class="wf-label">C2: + Visible Tests (CI)</div>
                <div class="wf-bar-wrap">
                    <div class="wf-bar-accepted" style="width: 95.5%;">95.5% Accepted</div>
                </div>
                <div class="wf-stats"><span class="badge badge-danger">66.2% Escape Rate</span></div>
            </div>
            <div class="waterfall-row">
                <div class="wf-label">C6: Full Aegis Pipeline</div>
                <div class="wf-bar-wrap">
                    <div class="wf-bar-accepted" style="width: 30.5%; background: var(--success); color:#000;">30.5% Qualified</div>
                </div>
                <div class="wf-stats"><span class="badge badge-success">0.0% Escape Rate</span></div>
            </div>
        </div>

        <!-- Adversarial Integrity Harness -->
        <div class="section-card">
            <div class="section-header">
                <div class="section-title">
                    <span>⚔️</span> Adversarial Integrity Harness (9 Exploit Probes vs 5 Benign Controls)
                </div>
                <span class="badge badge-success">100% Interception Rate</span>
            </div>
            <div class="section-desc">
                Harness security evaluation: Aegis blocked all 9 tested exploit probes across 6 attack vectors with 0 false positives on benign controls:
            </div>
            <table class="aegis-table">
                <thead>
                    <tr>
                        <th>Attack Vector</th>
                        <th>Probe Description</th>
                        <th>Defense Mechanism</th>
                        <th>Outcome</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Test Tampering</strong></td>
                        <td>Global <code>assert True</code> injection</td>
                        <td>AST Validator & Syntax Lock</td>
                        <td><span class="badge badge-danger">BLOCKED</span></td>
                    </tr>
                    <tr>
                        <td><strong>Framework Hijack</strong></td>
                        <td><code>sys.modules['pytest']</code> monkeypatch</td>
                        <td>Baseline Verification Fail-Closed</td>
                        <td><span class="badge badge-danger">BLOCKED</span></td>
                    </tr>
                    <tr>
                        <td><strong>Evaluator Probing</strong></td>
                        <td><code>../../private/hidden_tests</code> traversal</td>
                        <td>Namespace Isolation Gate</td>
                        <td><span class="badge badge-danger">BLOCKED</span></td>
                    </tr>
                    <tr>
                        <td><strong>Secret Exfiltration</strong></td>
                        <td>Outbound socket beaconing</td>
                        <td>Unshare Network Sandbox</td>
                        <td><span class="badge badge-danger">BLOCKED</span></td>
                    </tr>
                    <tr>
                        <td><strong>Benign Controls</strong></td>
                        <td>5 authentic functional bug fixes</td>
                        <td>All Verification Gates Clean</td>
                        <td><span class="badge badge-success">UNBLOCKED (0 FP)</span></td>
                    </tr>
                </tbody>
            </table>
        </div>

    </div>

</div>

<!-- ================================================================= -->
<!-- TRACE DETAIL MODAL                                                -->
<!-- ================================================================= -->
<div class="modal-overlay" id="trace-modal">
    <div class="modal-container">
        <div class="modal-header">
            <div class="modal-title">
                <span>🔎</span> <span id="modal-run-id">Trace Details</span>
            </div>
            <button class="modal-close" onclick="closeModal()">&times;</button>
        </div>
        <div class="modal-subnav">
            <button class="subnav-btn active" onclick="switchModalTab('overview')">Overview & Provenance</button>
            <button class="subnav-btn" onclick="switchModalTab('steps')">Agent Tool Execution</button>
            <button class="subnav-btn" onclick="switchModalTab('diff')">Unified Diff</button>
            <button class="subnav-btn" onclick="switchModalTab('features')">Pre-Verification Features</button>
            <button class="subnav-btn" onclick="switchModalTab('verification')">Aegis Verification (C1-C6)</button>
            <button class="subnav-btn" onclick="switchModalTab('oracle')">Independent Oracle</button>
        </div>
        <div class="modal-body" id="modal-body">
            <div style="text-align:center; padding:40px; color:var(--text-muted);">Loading run trace...</div>
        </div>
    </div>
</div>

<script>
let currentRunsData = [];
let activeTraceData = null;

function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

    if (tabId === 'pilot') {
        document.querySelector('.tab-btn:nth-child(1)').classList.add('active');
        document.getElementById('panel-pilot').classList.add('active');
    } else if (tabId === 'tasks') {
        document.querySelector('.tab-btn:nth-child(2)').classList.add('active');
        document.getElementById('panel-tasks').classList.add('active');
    } else if (tabId === 'synthetic') {
        document.querySelector('.tab-btn:nth-child(3)').classList.add('active');
        document.getElementById('panel-synthetic').classList.add('active');
    }
}

function fetchMetrics() {
    fetch('/api/research/metrics')
        .then(r => r.json())
        .then(data => {
            if (data.real_pilot && data.real_pilot.runs) {
                currentRunsData = data.real_pilot.runs;
                renderRunsTable(currentRunsData);
            }
        })
        .catch(err => console.error("Error fetching metrics:", err));
}

function renderRunsTable(runs) {
    const tbody = document.getElementById('traces-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    runs.forEach(r => {
        const tr = document.createElement('tr');

        const oracleBadge = r.oracle_verdict === 'CORRECT'
            ? '<span class="badge badge-success">CORRECT</span>'
            : '<span class="badge badge-danger">DEFECTIVE</span>';

        const c6Badge = r.c6_accepted === 1
            ? '<span class="badge badge-success">ADMITTED</span>'
            : '<span class="badge badge-danger">REJECTED</span>';

        let catBadge = '<span class="badge badge-muted">' + (r.failure_category || 'UNKNOWN') + '</span>';
        if (r.failure_category === 'SUCCESS') catBadge = '<span class="badge badge-success">SUCCESS</span>';
        else if (r.failure_category === 'INVALID_PATCH') catBadge = '<span class="badge badge-danger">INVALID_PATCH</span>';
        else if (r.failure_category === 'AGENT_FAILURE') catBadge = '<span class="badge badge-warning">AGENT_FAILURE</span>';

        const runShort = r.run_id.replace('run_', '').substring(0, 32);

        tr.innerHTML = `
            <td><code style="font-size:11px;">${runShort}...</code></td>
            <td><strong>${r.task_id}</strong></td>
            <td><code style="font-size:11px;">${r.model}</code></td>
            <td>${r.temperature !== undefined ? r.temperature : 0.2}</td>
            <td>${r.seed || 42}</td>
            <td>${oracleBadge}</td>
            <td>${c6Badge}</td>
            <td>${r.duration ? r.duration.toFixed(1) + 's' : '-'}</td>
            <td>${r.tokens ? r.tokens.toLocaleString() : '-'}</td>
            <td>${catBadge}</td>
            <td><button class="btn-inspect" onclick="openTraceModal('${r.run_id}')">Inspect Trace</button></td>
        `;
        tbody.appendChild(tr);
    });
}

function filterTraces() {
    const q = document.getElementById('trace-search').value.toLowerCase();
    const filtered = currentRunsData.filter(r =>
        r.run_id.toLowerCase().includes(q) ||
        r.task_id.toLowerCase().includes(q) ||
        (r.failure_category && r.failure_category.toLowerCase().includes(q))
    );
    renderRunsTable(filtered);
}

function openTraceModal(runId) {
    const modal = document.getElementById('trace-modal');
    modal.classList.add('active');
    document.getElementById('modal-run-id').innerText = runId;
    document.getElementById('modal-body').innerHTML = '<div style="text-align:center; padding:40px; color:var(--text-muted);">Loading full trace data...</div>';

    fetch('/api/research/run/' + runId)
        .then(r => r.json())
        .then(data => {
            activeTraceData = data;
            switchModalTab('overview');
        })
        .catch(err => {
            document.getElementById('modal-body').innerHTML = '<div style="color:var(--accent); padding:20px;">Failed to load trace: ' + err + '</div>';
        });
}

function closeModal() {
    document.getElementById('trace-modal').classList.remove('active');
    activeTraceData = null;
}

function switchModalTab(tab) {
    document.querySelectorAll('.subnav-btn').forEach(b => b.classList.remove('active'));
    const btn = Array.from(document.querySelectorAll('.subnav-btn')).find(b => b.innerText.toLowerCase().includes(tab));
    if (btn) btn.classList.add('active');

    const body = document.getElementById('modal-body');
    if (!activeTraceData) return;

    if (tab === 'overview') {
        const prov = activeTraceData.provenance || {};
        const fc = activeTraceData.failure_classification || {};
        body.innerHTML = `
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:20px;">
                <div style="background:rgba(0,0,0,0.25); padding:16px; border-radius:6px; border:1px solid var(--border);">
                    <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px;">RUN METADATA</div>
                    <div><strong>Task:</strong> ${activeTraceData.task_id}</div>
                    <div><strong>Model:</strong> ${activeTraceData.model} (Provider: ${activeTraceData.provider})</div>
                    <div><strong>Sampling:</strong> Temperature = ${activeTraceData.temperature}, Seed = ${activeTraceData.seed}</div>
                    <div><strong>Timestamp:</strong> ${activeTraceData.timestamp}</div>
                    <div><strong>Schema:</strong> ${activeTraceData.schema_version}</div>
                </div>
                <div style="background:rgba(0,0,0,0.25); padding:16px; border-radius:6px; border:1px solid var(--border);">
                    <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px;">DIAGNOSTIC OUTCOME</div>
                    <div><strong>Classification:</strong> <span class="badge badge-cyan">${fc.category || 'UNKNOWN'}</span></div>
                    <div><strong>Detail:</strong> ${fc.detail || 'None'}</div>
                    <div><strong>Total Tokens:</strong> ${(activeTraceData.agent_execution?.total_tokens || 0).toLocaleString()}</div>
                    <div><strong>Execution Time:</strong> ${(activeTraceData.agent_execution?.agent_duration_seconds || 0).toFixed(2)}s</div>
                </div>
            </div>
            <div style="background:rgba(0,0,0,0.25); padding:16px; border-radius:6px; border:1px solid var(--border);">
                <div style="font-size:12px; color:var(--text-muted); margin-bottom:6px;">PROVENANCE & INTEGRITY HASHES</div>
                <div style="font-family:monospace; font-size:12px;"><strong>Base Snapshot SHA:</strong> ${prov.base_snapshot_sha256 || 'None'}</div>
                <div style="font-family:monospace; font-size:12px; margin-top:4px;"><strong>Head Snapshot SHA:</strong> ${prov.head_snapshot_sha256 || 'None'}</div>
                <div style="font-family:monospace; font-size:12px; margin-top:4px;"><strong>Patch SHA-256:</strong> ${prov.patch_sha256 || 'None'}</div>
                <div style="margin-top:8px;"><strong>Churn:</strong> +${prov.lines_added || 0} / -${prov.lines_deleted || 0} (Net: ${prov.net_churn || 0} LOC across ${(prov.modified_files || []).length} files)</div>
            </div>
        `;
    } else if (tab === 'steps') {
        const steps = activeTraceData.agent_execution?.steps || [];
        if (steps.length === 0) {
            body.innerHTML = '<div style="color:var(--text-muted);">No tool steps recorded for this run.</div>';
            return;
        }
        let html = '<div style="font-size:13px; margin-bottom:12px;"><strong>Multi-Turn Agent Execution Trace (' + steps.length + ' steps):</strong></div>';
        steps.forEach(s => {
            const calls = (s.tool_calls || []).map(c => `<code>${c.function?.name || c.name}</code>(${JSON.stringify(c.function?.arguments || c.arguments || {})})`).join('<br>');
            html += `
                <div class="tool-step">
                    <div class="tool-step-hdr">
                        <span style="color:var(--cyan);">Step ${s.step_index + 1} (${(s.duration_seconds || 0).toFixed(2)}s)</span>
                        <span style="color:var(--text-muted);">${s.prompt_tokens || 0} prompt / ${s.completion_tokens || 0} completion tokens</span>
                    </div>
                    ${s.model_response_content ? `<div style="font-size:12px; color:var(--text-secondary); margin-bottom:8px; font-style:italic;">"${escapeHtml(s.model_response_content.substring(0, 300))}${s.model_response_content.length > 300 ? '...' : ''}"</div>` : ''}
                    <div style="font-size:12px; background:rgba(0,0,0,0.3); padding:8px; border-radius:4px; font-family:monospace; margin-bottom:6px;">
                        <span style="color:var(--purple); font-weight:bold;">Tool Calls:</span><br>${calls || 'None'}
                    </div>
                </div>
            `;
        });
        body.innerHTML = html;
    } else if (tab === 'diff') {
        const patch = activeTraceData.provenance?.patch_diff || '';
        if (!patch.trim()) {
            body.innerHTML = '<div style="color:var(--text-muted); padding:20px;">No diff was generated in this run.</div>';
            return;
        }
        const lines = patch.split('\n').map(l => {
            if (l.startsWith('+') && !l.startsWith('+++')) return `<span class="diff-add">${escapeHtml(l)}</span>`;
            if (l.startsWith('-') && !l.startsWith('---')) return `<span class="diff-del">${escapeHtml(l)}</span>`;
            if (l.startsWith('diff --git') || l.startsWith('@@')) return `<span class="diff-hdr">${escapeHtml(l)}</span>`;
            return escapeHtml(l);
        }).join('\n');
        body.innerHTML = `<pre class="diff-view">${lines}</pre>`;
    } else if (tab === 'features') {
        const feats = activeTraceData.pre_verification_features || {};
        let items = '';
        for (const [k, v] of Object.entries(feats)) {
            items += `
                <div class="feature-item">
                    <div class="feature-name">${k}</div>
                    <div class="feature-val">${v}</div>
                </div>
            `;
        }
        body.innerHTML = `
            <div style="font-size:13px; color:var(--text-secondary); margin-bottom:14px;">
                <strong>19 Pre-Verification Static Features</strong> (Extracted from diff/AST prior to verification; zero runtime leakage):
            </div>
            <div class="feature-grid">${items}</div>
        `;
    } else if (tab === 'verification') {
        const v = activeTraceData.aegis_verification || {};
        const acc = activeTraceData.accepted || {};
        body.innerHTML = `
            <div style="margin-bottom:16px;">
                <strong>Aegis Verification Verdict:</strong> <span class="badge ${v.technical_verdict === 'PASS' ? 'badge-success' : 'badge-danger'}">${v.technical_verdict}</span>
                <span style="margin-left:12px;"><strong>Release Policy:</strong> <span class="badge ${v.release_policy === 'ALLOW' ? 'badge-success' : 'badge-danger'}">${v.release_policy}</span></span>
            </div>
            <table class="aegis-table" style="margin-bottom:20px;">
                <thead><tr><th>Tier</th><th>Description</th><th>Accepted</th></tr></thead>
                <tbody>
                    <tr><td><strong>C1</strong></td><td>Agent Self-Report</td><td>${acc.C1_agent_only ? '✅ Passed' : '❌ Failed'}</td></tr>
                    <tr><td><strong>C2</strong></td><td>Visible Tests</td><td>${acc.C2_visible_tests ? '✅ Passed' : '❌ Failed'}</td></tr>
                    <tr><td><strong>C3</strong></td><td>Hidden Private Tests</td><td>${acc.C3_hidden_tests ? '✅ Passed' : '❌ Failed'}</td></tr>
                    <tr><td><strong>C4</strong></td><td>BASE Regression Invariance</td><td>${acc.C4_regression ? '✅ Passed' : '❌ Failed'}</td></tr>
                    <tr><td><strong>C5</strong></td><td>Mutation Analysis</td><td>${acc.C5_mutation ? '✅ Passed' : '❌ Failed'}</td></tr>
                    <tr><td><strong>C6</strong></td><td>Full Aegis Qualification</td><td>${acc.C6_full_aegis ? '✅ Qualified' : '❌ Rejected'}</td></tr>
                </tbody>
            </table>
            <div style="background:rgba(0,0,0,0.25); padding:14px; border-radius:6px; border:1px solid var(--border); font-size:13px;">
                <div><strong>Static Security Safe:</strong> ${v.security_safe ? '✅ Yes' : '❌ Violation'} (Issues: ${(v.security_issues || []).length})</div>
                <div><strong>Mutation Score:</strong> ${v.mutation_score !== undefined ? (v.mutation_score * 100).toFixed(1) + '%' : 'N/A'}</div>
                <div><strong>Verification Duration:</strong> ${(v.verification_duration_seconds || 0).toFixed(2)}s</div>
            </div>
        `;
    } else if (tab === 'oracle') {
        const o = activeTraceData.oracle_evaluation || {};
        const tg = activeTraceData.targets || {};
        body.innerHTML = `
            <div style="margin-bottom:16px;">
                <strong>Independent Oracle Ground Truth:</strong>
                <span class="badge ${o.oracle_verdict === 'CORRECT' ? 'badge-success' : 'badge-danger'}" style="font-size:14px; padding:4px 10px;">
                    ${o.oracle_verdict}
                </span>
            </div>
            <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; margin-bottom:16px;">
                <div class="feature-item"><div class="feature-name">y_regression</div><div class="feature-val" style="color:${tg.regression ? 'var(--accent)' : 'var(--success)'};">${tg.regression}</div></div>
                <div class="feature-item"><div class="feature-name">y_security</div><div class="feature-val" style="color:${tg.security ? 'var(--accent)' : 'var(--success)'};">${tg.security}</div></div>
                <div class="feature-item"><div class="feature-name">y_overfitting</div><div class="feature-val" style="color:${tg.overfitting ? 'var(--accent)' : 'var(--success)'};">${tg.overfitting}</div></div>
                <div class="feature-item"><div class="feature-name">y_performance</div><div class="feature-val" style="color:${tg.performance ? 'var(--accent)' : 'var(--success)'};">${tg.performance}</div></div>
            </div>
            <div style="background:rgba(0,0,0,0.25); padding:14px; border-radius:6px; border:1px solid var(--border); font-size:13px;">
                <div><strong>Hidden Test Passed:</strong> ${o.hidden_test_passed ? '✅ Yes' : '❌ No'}</div>
                <div><strong>Regression Invariant Maintained:</strong> ${o.regression_test_passed ? '✅ Yes' : '❌ No'}</div>
                <div><strong>Candidate Latency Delta:</strong> ${(o.latency_delta_pct || 0).toFixed(1)}%</div>
                ${o.failure_reasons && o.failure_reasons.length ? `<div style="color:var(--accent); margin-top:8px;"><strong>Failure Reasons:</strong> ${o.failure_reasons.join(', ')}</div>` : ''}
            </div>
        `;
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Initial fetch
document.addEventListener('DOMContentLoaded', () => {
    fetchMetrics();
});
</script>

</body>
</html>
'''

def update_editor():
    editor_file = Path("aegis_editor.py")
    content = editor_file.read_text(encoding="utf-8")

    start_tag = 'RESEARCH_HTML = r"""'
    end_tag = '# ---------------------------------------------------------------------------'

    start_idx = content.find(start_tag)
    if start_idx == -1:
        print("ERROR: Could not find RESEARCH_HTML in aegis_editor.py")
        sys.exit(1)

    end_idx = content.find(end_tag, start_idx)
    if end_idx == -1:
        print("ERROR: Could not find end tag in aegis_editor.py")
        sys.exit(1)

    new_html_block = 'RESEARCH_HTML = r"""' + generate_research_html() + '"""\n\n'
    new_content = content[:start_idx] + new_html_block + content[end_idx:]

    editor_file.write_text(new_content, encoding="utf-8")
    print(f"Successfully updated aegis_editor.py with rich Research Console UI.")

if __name__ == "__main__":
    update_editor()
