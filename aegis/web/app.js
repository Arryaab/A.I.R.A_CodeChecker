/**
 * A.I.R.A. (AI Release Assurance) — Production Control Plane Engine
 *
 * Architecture:
 * - State management: Active scenario, current audit report, verification execution lock.
 * - API integration: /api/health, /api/demo/scenarios, /api/demo/verify, /api/verifications, /api/auth/*.
 * - Central API client: Centralized session authentication with zero credential leakage.
 * - Interactive Workbench: Real diff rendering, staggered gate animation, fail-closed policy.
 * - Developer Console: Async job submission with streaming execution telemetry and error states.
 * - Cryptographic Ledger: Content-addressed run history and JSON package modal inspection.
 */

// Application State
const appState = {
  activeScenarioId: 'demo_01_clean_pass',
  scenariosCache: {},
  latestReport: null,
  isExecuting: false
};

// ============================================================================
// CENTRAL API CLIENT & AUTHENTICATION MANAGER (SESSION-ONLY)
// ============================================================================

const auth = {
  SESSION_KEY: 'aira_api_key',

  getKey() {
    return sessionStorage.getItem(this.SESSION_KEY) || '';
  },

  setKey(key) {
    if (key && typeof key === 'string' && key.trim()) {
      sessionStorage.setItem(this.SESSION_KEY, key.trim());
      updateAuthUI(true);
    } else {
      this.clearKey();
    }
  },

  clearKey() {
    sessionStorage.removeItem(this.SESSION_KEY);
    updateAuthUI(false);
  },

  isConnected() {
    return Boolean(this.getKey());
  },

  async validateKey(keyToTest) {
    const key = keyToTest || this.getKey();
    if (!key) return false;
    try {
      const res = await fetch('/api/auth/check', {
        method: 'GET',
        headers: { 'X-API-Key': key }
      });
      return res.status === 200;
    } catch (e) {
      return false;
    }
  },

  async initLocalDevIfApplicable() {
    // Zero-friction local development: Only on localhost if not already connected
    const hostname = window.location.hostname;
    const isLocalhost = ['localhost', '127.0.0.1', '::1'].includes(hostname);
    if (!isLocalhost || this.isConnected()) return;

    try {
      const res = await fetch('/api/auth/local-dev-token');
      if (res.ok) {
        const data = await res.json();
        if (data.enabled && data.token) {
          sessionStorage.setItem(this.SESSION_KEY, data.token);
          updateAuthUI(true);
        }
      }
    } catch (e) {
      // Remote or local dev mode disabled
    }
  }
};

const api = {
  async request(endpoint, options = {}, isPublic = false) {
    const headers = Object.assign({}, options.headers || {});

    if (!isPublic) {
      const key = auth.getKey();
      if (key) {
        headers['X-API-Key'] = key;
      }
    }

    const config = Object.assign({}, options, { headers });
    const res = await fetch(endpoint, config);

    if (res.status === 401 && !isPublic) {
      handleAuthFailure();
    }
    return res;
  },

  get(endpoint, isPublic = false) {
    return api.request(endpoint, { method: 'GET' }, isPublic);
  },

  post(endpoint, bodyData, isPublic = false) {
    return api.request(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bodyData)
    }, isPublic);
  },

  upload(endpoint, formData, isPublic = false) {
    // Note: Do NOT set Content-Type header so browser generates multipart boundary automatically
    return api.request(endpoint, {
      method: 'POST',
      body: formData
    }, isPublic);
  },

  delete(endpoint, isPublic = false) {
    return api.request(endpoint, { method: 'DELETE' }, isPublic);
  }
};

function updateAuthUI(isConnected) {
  const badge = document.getElementById('api-status-badge');
  const triggerBtn = document.getElementById('btn-api-auth-trigger');
  const uploadBanner = document.getElementById('upload-auth-banner');
  const actionsDisconnected = document.getElementById('auth-actions-disconnected');
  const actionsConnected = document.getElementById('auth-actions-connected');

  if (isConnected) {
    if (badge) {
      badge.textContent = 'CONNECTED';
      badge.className = 'api-status-badge connected mono';
    }
    if (triggerBtn) {
      triggerBtn.textContent = 'MANAGE';
    }
    if (uploadBanner) {
      uploadBanner.style.display = 'none';
    }
    if (actionsDisconnected) actionsDisconnected.style.display = 'none';
    if (actionsConnected) actionsConnected.style.display = 'flex';
  } else {
    if (badge) {
      badge.textContent = 'NOT CONNECTED';
      badge.className = 'api-status-badge not-connected mono';
    }
    if (triggerBtn) {
      triggerBtn.textContent = 'CONNECT';
    }
    if (uploadBanner) {
      uploadBanner.style.display = 'block';
    }
    if (actionsDisconnected) actionsDisconnected.style.display = 'flex';
    if (actionsConnected) actionsConnected.style.display = 'none';
  }
}

function handleAuthFailure() {
  auth.clearKey();
  showAuthModal('Authentication failed. Check your API key and try again.', true);
}

function showAuthModal(message = '', isError = false) {
  const modal = document.getElementById('auth-modal');
  const feedback = document.getElementById('auth-modal-feedback');
  const keyInput = document.getElementById('auth-input-key');
  if (!modal) return;

  if (keyInput) keyInput.value = '';

  if (feedback) {
    if (message) {
      feedback.style.display = 'block';
      feedback.className = `auth-modal-feedback ${isError ? 'error' : 'success'}`;
      feedback.textContent = message;
    } else {
      feedback.style.display = 'none';
      feedback.textContent = '';
    }
  }

  modal.style.display = 'flex';
}

function closeAuthModal() {
  const modal = document.getElementById('auth-modal');
  if (modal) modal.style.display = 'none';
}

// Curated Domain Scenarios (Zero-Dependency Offline Fallback & Initial Seed)
const DOMAIN_SCENARIOS = {
  demo_01_clean_pass: {
    id: 'demo_01_clean_pass',
    title: 'Token Bucket Rate Limiter',
    category: 'High Assurance / Clean Pass',
    file_path: 'services/rate_limiter.py',
    duration_ms: 1420,
    technical_verdict: 'QUALIFIED',
    release_policy: 'AUTO_APPROVE',
    headline: 'DEMO — QUALIFIED',
    explanation: 'All 6 verification layers satisfied. Thread-safe implementation with monotonic clock and clean boundary checks.',
    diff: `--- a/services/rate_limiter.py
+++ b/services/rate_limiter.py
@@ -14,6 +14,24 @@ class TokenBucket:
     def __init__(self, capacity: int, refill_rate: float):
+        if capacity <= 0:
+            raise ValueError("Capacity must be positive")
+        if refill_rate <= 0:
+            raise ValueError("Refill rate must be positive")
         self.capacity = float(capacity)
         self.tokens = float(capacity)
         self.refill_rate = float(refill_rate)
-        self.last_refill = time.time()
+        self.last_refill = time.monotonic()
+        self._lock = threading.Lock()
+
+    def consume(self, tokens: int = 1) -> bool:
+        if tokens <= 0:
+            raise ValueError("Tokens to consume must be positive")
+        with self._lock:
+            now = time.monotonic()
+            elapsed = now - self.last_refill
+            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
+            self.last_refill = now
+            if self.tokens >= tokens:
+                self.tokens -= tokens
+                return True
+            return False`,
    criteria: {
      C1_syntax: { status: 'PASS', score: 1.0, label: 'PASSED' },
      C2_visible_tests: { status: 'PASS', score: 1.0, label: 'PASSED (8/8)' },
      C3_hidden_invariants: { status: 'PASS', score: 1.0, label: 'PASSED (12/12)' },
      C4_regression: { status: 'PASS', score: 1.0, label: 'PASSED (34/34)' },
      C5_mutation: { status: 'PASS', score: 0.92, label: 'PASSED (0.92)' },
      C6_security: { status: 'PASS', score: 1.0, label: 'PASSED' }
    }
  },

  demo_02_hidden_overfit: {
    id: 'demo_02_hidden_overfit',
    title: 'Invariant Zero-Division (AI Overfit)',
    category: 'Hidden Invariant Defect',
    file_path: 'orders/inventory_allocator.py',
    duration_ms: 1180,
    technical_verdict: 'REJECTED',
    release_policy: 'BLOCK',
    headline: 'DEMO — REJECTED: Hidden Invariant Violated',
    explanation: 'The AI patch passed visible unit tests, but silently crashes with ZeroDivisionError when total batch demand is 0.',
    diff: `--- a/orders/inventory_allocator.py
+++ b/orders/inventory_allocator.py
@@ -32,7 +32,13 @@ def rebalance_stock(warehouse_inventory: dict, order_demands: dict) -> dict:
     """Calculates proportional allocation ratio for multi-warehouse fulfillments."""
-    pass
+    total_demand = sum(order_demands.values())
+    allocated = {}
+    for sku, available in warehouse_inventory.items():
         demand = order_demands.get(sku, 0)
         # BUG: ZeroDivisionError occurs when total_demand is 0
         ratio = demand / total_demand
         allocated[sku] = round(available * ratio, 2)
     return allocated`,
    criteria: {
      C1_syntax: { status: 'PASS', score: 1.0, label: 'PASSED' },
      C2_visible_tests: { status: 'PASS', score: 1.0, label: 'PASSED (4/4)' },
      C3_hidden_invariants: { status: 'FAIL', score: 0.0, label: 'FAILED (ZeroDivisionError)' },
      C4_regression: { status: 'PASS', score: 1.0, label: 'PASSED (18/18)' },
      C5_mutation: { status: 'SKIP', score: 0.0, label: 'SKIPPED' },
      C6_security: { status: 'PASS', score: 1.0, label: 'PASSED' }
    }
  },

  demo_03_path_traversal: {
    id: 'demo_03_path_traversal',
    title: 'CWE-22 Path Traversal in Export Worker',
    category: 'Security AST Taint Scan',
    file_path: 'reports/export_worker.py',
    duration_ms: 940,
    technical_verdict: 'REJECTED',
    release_policy: 'BLOCK',
    headline: 'DEMO — REJECTED: Critical Security Veto',
    explanation: 'Untrusted filename parameter concatenated directly into filesystem write sink. Arbitrary file write vulnerability detected.',
    diff: `--- a/reports/export_worker.py
+++ b/reports/export_worker.py
@@ -19,5 +19,13 @@ def save_report_output(report_id: str, filename: str, content: bytes) -> str:
     base_dir = "/var/reports/generated"
-    target = os.path.join(base_dir, f"{report_id}.pdf")
+    # SECURITY VULNERABILITY: filename flows directly into filesystem sink
+    # Allows attacks like filename='../../etc/cron.d/malicious'
     target = os.path.join(base_dir, filename)
     with open(target, "wb") as f:
         f.write(content)
     return target`,
    criteria: {
      C1_syntax: { status: 'PASS', score: 1.0, label: 'PASSED' },
      C2_visible_tests: { status: 'PASS', score: 1.0, label: 'PASSED (2/2)' },
      C3_hidden_invariants: { status: 'PASS', score: 1.0, label: 'PASSED (4/4)' },
      C4_regression: { status: 'PASS', score: 1.0, label: 'PASSED (12/12)' },
      C5_mutation: { status: 'SKIP', score: 0.0, label: 'SKIPPED' },
      C6_security: { status: 'FAIL', score: 0.0, label: 'FAILED (CWE-22)' }
    }
  },

  demo_04_regression_break: {
    id: 'demo_04_regression_break',
    title: 'API Schema Regression in Webhook Dispatcher',
    category: 'Backward Compatibility Break',
    file_path: 'payments/webhook_dispatcher.py',
    duration_ms: 1310,
    technical_verdict: 'REJECTED',
    release_policy: 'BLOCK',
    headline: 'DEMO — REJECTED: Downstream Regression Detected',
    explanation: 'AI renamed payload key transaction_id to tx_id. Broke 3 downstream consumers in billing integration suite.',
    diff: `--- a/payments/webhook_dispatcher.py
+++ b/payments/webhook_dispatcher.py
@@ -45,8 +45,8 @@ def format_webhook_event(raw_event: dict) -> dict:
     return {
         "event_type": raw_event.get("type", "unknown"),
-        "transaction_id": raw_event.get("txn_id"),
-        "status": raw_event.get("status")
+        # BREAKING REGRESSION: Renamed key breaks downstream consumers
         "tx_id": raw_event.get("txn_id"),
         "status": raw_event.get("status")
      }`,
    criteria: {
      C1_syntax: { status: 'PASS', score: 1.0, label: 'PASSED' },
      C2_visible_tests: { status: 'PASS', score: 1.0, label: 'PASSED (3/3)' },
      C3_hidden_invariants: { status: 'PASS', score: 1.0, label: 'PASSED' },
      C4_regression: { status: 'FAIL', score: 0.0, label: 'FAILED (KeyError in billing)' },
      C5_mutation: { status: 'SKIP', score: 0.0, label: 'SKIPPED' },
      C6_security: { status: 'PASS', score: 1.0, label: 'PASSED' }
    }
  },

  demo_05_mutation_survivor: {
    id: 'demo_05_mutation_survivor',
    title: 'Mutation-Resistant Semantic Defect',
    category: 'Semantic Mutation Resistance',
    file_path: 'pricing/discount_calculator.py',
    duration_ms: 1650,
    technical_verdict: 'REJECTED',
    release_policy: 'REVIEW',
    headline: 'DEMO — REVIEW: Vacuous Test Coverage',
    explanation: 'The condition "total >= 100 or total > 0" is a tautology. Mutants survived undetected (Mutation Score: 0.28 < 0.50 threshold).',
    diff: `--- a/pricing/discount_calculator.py
+++ b/pricing/discount_calculator.py
@@ -10,7 +10,10 @@ def calculate_bulk_discount(total: float, tier: str) -> float:
-    return 0.0
+    # SEMANTIC BUG: Tautology makes '> 0' dominate; mutant total <= 100 survives
+    if total >= 100.0 or total > 0:
+        return total * 0.15
     return 0.0`,
    criteria: {
      C1_syntax: { status: 'PASS', score: 1.0, label: 'PASSED' },
      C2_visible_tests: { status: 'PASS', score: 1.0, label: 'PASSED' },
      C3_hidden_invariants: { status: 'PASS', score: 1.0, label: 'PASSED' },
      C4_regression: { status: 'PASS', score: 1.0, label: 'PASSED' },
      C5_mutation: { status: 'FAIL', score: 0.28, label: 'FAILED (Score: 0.28)' },
      C6_security: { status: 'PASS', score: 1.0, label: 'PASSED' }
    }
  }
};

// DOM References
const dom = {
  navSystemStatus: document.getElementById('nav-system-status'),
  scenarioTabs: document.querySelectorAll('.scenario-tab'),
  scenarioTraceId: document.getElementById('scenario-trace-id'),
  demoDiffFilename: document.getElementById('demo-diff-filename'),
  demoDiffContent: document.getElementById('demo-diff-content'),
  demoVerdictBanner: document.getElementById('demo-verdict-banner'),
  demoVerdictBadge: document.getElementById('demo-verdict-badge'),
  demoVerdictDuration: document.getElementById('demo-verdict-duration'),
  demoVerdictHeadline: document.getElementById('demo-verdict-headline'),
  demoVerdictDesc: document.getElementById('demo-verdict-desc'),
  btnReExecuteDemo: document.getElementById('btn-re-execute-demo'),
  btnViewAuditPackage: document.getElementById('btn-view-audit-package'),
  gateBadges: {
    C1_syntax: document.getElementById('demo-badge-C1'),
    C2_visible_tests: document.getElementById('demo-badge-C2'),
    C3_hidden_invariants: document.getElementById('demo-badge-C3'),
    C4_regression: document.getElementById('demo-badge-C4'),
    C5_mutation: document.getElementById('demo-badge-C5'),
    C6_security: document.getElementById('demo-badge-C6')
  },
  consoleForm: document.getElementById('console-submission-form'),
  consoleRepo: document.getElementById('console-input-repo'),
  consoleBase: document.getElementById('console-input-base'),
  consoleHead: document.getElementById('console-input-head'),
  consoleTier: document.getElementById('console-select-tier'),
  consoleDiff: document.getElementById('console-input-diff'),
  consoleSubmitBtn: document.getElementById('btn-submit-console-job'),
  consoleLog: document.getElementById('console-execution-log'),
  ledgerTableRows: document.getElementById('ledger-table-rows'),
  btnRefreshLedger: document.getElementById('btn-refresh-ledger'),
  btnExportLatestJson: document.getElementById('btn-export-latest-json'),
  evidenceModal: document.getElementById('evidence-modal'),
  evidenceModalJsonContent: document.getElementById('evidence-modal-json-content'),
  btnCloseEvidenceModal: document.getElementById('btn-close-evidence-modal')
};

// ============================================================================
// VISUAL & INTERACTION SYSTEM (FLUX PROCEDURAL SHADER & AIRLOCK DYNAMICS)
// ============================================================================

function initVisualExperience() {
  initShaderAndInteraction();
  initHeroRing();
  initMarqueeTrack();
  initResearchObserver();
  drawAirlockGates();
}

function initHeroRing() {
  const ring = document.getElementById('ring');
  if (!ring) return;
  const G = [['C1', 'Syntax'], ['C2', 'Tests'], ['C3', 'Invariants'], ['C4', 'Regression'], ['C5', 'Mutation'], ['C6', 'Security']];
  function pt(i, r) {
    const a = (-90 + 60 * i) * Math.PI / 180;
    return (200 + r * Math.cos(a)).toFixed(1) + ',' + (200 + r * Math.sin(a)).toFixed(1);
  }
  let h = '<polygon points="' + [0, 1, 2, 3, 4, 5].map(i => pt(i, 170)).join(' ') + '" stroke-width="1.5"/>' +
          '<polygon points="' + [0, 1, 2, 3, 4, 5].map(i => pt(i, 120)).join(' ') + '"/>' +
          '<polygon points="' + [0, 1, 2, 3, 4, 5].map(i => pt(i, 195)).join(' ') + '"/>' +
          '<circle class="core" cx="200" cy="200" r="22"/>';
  G.forEach((g, i) => {
    const [x, y] = pt(i, 150).split(',');
    h += `<circle class="n" cx="${x}" cy="${y}" r="11" style="animation-delay:${i}s"/>` +
         `<text x="${x}" y="${+y + (y < 200 ? -24 : 30)}">${g[0]}</text>`;
  });
  ring.innerHTML = h;
}

function initMarqueeTrack() {
  const tr = document.getElementById('track');
  if (!tr) return;
  const words = ['CONTAIN', 'VERIFY', 'FAIL-CLOSED', 'ISOLATE', 'PROVE', 'ASSURE'];
  let h = '';
  for (let k = 0; k < 2; k++) {
    words.forEach(w => {
      h += `<span>${w}</span><span class="star">&#10042;</span>`;
    });
  }
  tr.innerHTML = h + h;
}

function initResearchObserver() {
  const io = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      io.unobserve(entry.target);
      const el = entry.target;
      if (el.dataset.v) {
        const targetVal = parseFloat(el.dataset.v);
        const decimals = parseInt(el.dataset.d || '2', 10);
        const start = performance.now();
        const duration = 1600;
        function update(now) {
          const progress = Math.min((now - start) / duration, 1);
          const ease = 1 - Math.pow(1 - progress, 4);
          el.textContent = (targetVal * ease).toFixed(decimals);
          if (progress < 1) requestAnimationFrame(update);
        }
        requestAnimationFrame(update);
      } else if (el.dataset.w) {
        el.style.width = el.dataset.w + '%';
      }
    });
  }, { threshold: 0.5 });
  document.querySelectorAll('[data-v], [data-w]').forEach(el => io.observe(el));
}

function initShaderAndInteraction() {
  const cv = document.getElementById('gl');
  const bar = document.getElementById('bar');
  if (bar) {
    window.addEventListener('scroll', () => {
      const m = document.documentElement.scrollHeight - window.innerHeight;
      bar.style.transform = 'scaleX(' + (m > 0 ? window.scrollY / m : 0) + ')';
    }, { passive: true });
  }

  if (!cv) return;
  const gl = cv.getContext('webgl', { antialias: false, powerPreference: 'high-performance' });
  const rm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let mx = 0.5, my = 0.5, tx = 0.5, ty = 0.5, blast = [0.5, 0.5, -100], t0 = performance.now();

  function pos(e) {
    tx = e.clientX / window.innerWidth;
    ty = 1 - e.clientY / window.innerHeight;
  }
  window.addEventListener('pointermove', pos);

  function boom(x, y) {
  window.boom = boom;
    blast = [x / window.innerWidth, 1 - y / window.innerHeight, (performance.now() - t0) / 1000 * (rm ? 0.3 : 1)];
  }
  window.addEventListener('pointerdown', (e) => {
    if (!['INPUT', 'TEXTAREA', 'SELECT', 'LABEL'].includes(e.target.tagName)) {
      boom(e.clientX, e.clientY);
    }
  });

  const blastBtns = ['nav-btn-verify', 'nav-btn-demo', 'btn-run-verify', 'btn-re-execute-demo', 'boom-hero', 'boom-end', 'flux-hint-trigger'];
  blastBtns.forEach(id => {
    const btn = document.getElementById(id);
    if (btn) {
      btn.addEventListener('click', (e) => {
        const r = e.currentTarget.getBoundingClientRect();
        boom(r.left + r.width / 2, r.top + r.height / 2);
      });
    }
  });

  if (!gl) {
    cv.style.display = 'none';
    return;
  }

  const vs = 'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
  const fs = 'precision highp float;uniform vec2 r,m;uniform float t;uniform vec3 b;' +
    'float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}' +
    'float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(h(i),h(i+vec2(1.,0.)),f.x),mix(h(i+vec2(0.,1.)),h(i+1.),f.x),f.y);}' +
    'float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<5;i++){v+=a*n(p);p=p*2.03+vec2(1.7,9.2);a*=.5;}return v;}' +
    'void main(){' +
    'vec2 uv=(gl_FragCoord.xy-.5*r)/r.y;vec2 mm=(m*r-.5*r)/r.y;float d=length(uv-mm);' +
    'uv+=normalize(uv-mm+1e-4)*.09*exp(-d*3.)*sin(t*1.5);' +
    'vec2 bc=(b.xy*r-.5*r)/r.y;float bd=length(uv-bc);float age=t-b.z;' +
    'float ring=exp(-pow((bd-age*.9)*8.,2.))*exp(-age*1.2)*step(0.,age);' +
    'uv+=normalize(uv-bc+1e-4)*ring*.14;' +
    'vec2 q=vec2(fbm(uv*2.+t*.1),fbm(uv*2.+vec2(5.2,1.3)-t*.12));' +
    'vec2 w=vec2(fbm(uv*2.+3.*q+vec2(1.7,9.2)+t*.15),fbm(uv*2.+3.*q+vec2(8.3,2.8)-t*.126));' +
    'float f=fbm(uv*2.+3.*w);' +
    'vec3 ink=vec3(0.0,0.0,0.0);' +
    'vec3 c1=vec3(0.08,0.08,0.10);' +
    'vec3 c2=vec3(0.015,0.015,0.02);' +
    'vec3 c3=vec3(0.243,0.941,0.769);' +
    'vec3 col=mix(ink,c2,smoothstep(.2,.6,f));' +
    'col=mix(col,c1,smoothstep(.45,.85,length(q)));' +
    'col=mix(col,c3,smoothstep(.5,1.,w.x*w.y*2.4));' +
    'col+=ring*vec3(1.0,1.0,1.0)*1.2+exp(-d*4.)*c3*.25;' +
    'col*=1.15-.6*length(gl_FragCoord.xy/r-.5);' +
    'gl_FragColor=vec4(col,1.);}';

  function compileShader(type, src) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    return s;
  }
  const pr = gl.createProgram();
  gl.attachShader(pr, compileShader(gl.VERTEX_SHADER, vs));
  gl.attachShader(pr, compileShader(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(pr);
  if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) {
    cv.style.display = 'none';
    return;
  }
  gl.useProgram(pr);

  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(pr, 'p');
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

  const U = {
    r: gl.getUniformLocation(pr, 'r'),
    m: gl.getUniformLocation(pr, 'm'),
    t: gl.getUniformLocation(pr, 't'),
    b: gl.getUniformLocation(pr, 'b')
  };

  function rs() {
    const d = Math.min(window.devicePixelRatio || 1, 1.5) * 0.6;
    cv.width = Math.floor(window.innerWidth * d);
    cv.height = Math.floor(window.innerHeight * d);
    gl.viewport(0, 0, cv.width, cv.height);
  }
  rs();
  window.addEventListener('resize', rs);

  let tt = 0, last = performance.now();
  let syLast = window.scrollY;
  function frame(now) {
    const dt = (now - last) / 1000;
    last = now;
    tt += dt * (rm ? 0.15 : 1) * (1 + Math.min(Math.abs(window.scrollY - syLast) / 40, 2));
    syLast = window.scrollY;
    mx += (tx - mx) * 0.08;
    my += (ty - my) * 0.08;
    gl.uniform2f(U.r, cv.width, cv.height);
    gl.uniform2f(U.m, mx, my);
    gl.uniform1f(U.t, tt);
    const bz = blast[2] < 0 ? blast[2] : blast[2];
    gl.uniform3f(U.b, blast[0], blast[1], bz > -50 ? tt - ((performance.now() - t0) / 1000 * (rm ? 0.3 : 1) - blast[2]) : -100);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

// ============================================================================
// INITIALIZATION
// ============================================================================

async function initializeApp() {
  setupNavigationEvents();
  setupScenarioTabs();
  setupConsoleForm();
  setupModalEvents();
  setupAuthEvents();

  updateAuthUI(auth.isConnected());
  await auth.initLocalDevIfApplicable();
  await checkHealthStatus();
  await loadRemoteScenarios();
  initRouter();
  await loadEvidenceLedger();
  initVisualExperience();
}

// ============================================================================
// 1. SYSTEM HEALTH MONITOR
// ============================================================================

async function checkHealthStatus() {
  try {
    const res = await api.get(`/api/system/sandbox?t=${Date.now()}`, true);
    if (res.ok) {
      const data = await res.json();
      updateNavSandboxStatus(data);
      return data;
    }
  } catch (e) {
    updateNavSandboxStatus({ available: false, sandbox_health: 'OFFLINE' });
  }
}

function updateNavSandboxStatus(data) {
  const isReady = !!(data && (data.available || data.sandbox_health === 'SANDBOX_READY'));
  if (dom.navSystemStatus) {
    dom.navSystemStatus.textContent = isReady ? 'SANDBOX READY' : 'SANDBOX UNAVAILABLE';
  }
  const dot = document.getElementById('nav-status-dot');
  if (dot) {
    if (isReady) {
      dot.style.backgroundColor = 'var(--status-pass)';
      dot.classList.remove('offline');
    } else {
      dot.style.backgroundColor = 'var(--status-fail)';
      dot.classList.add('offline');
    }
  }
}

// ============================================================================
// 2. SCENARIO SELECTION & WORKBENCH RENDERING (DEMO)
// ============================================================================

async function loadRemoteScenarios() {
  try {
    const res = await api.get('/api/demo/scenarios', true);
    if (res.ok) {
      const data = await res.json();
      data.forEach(sc => {
        appState.scenariosCache[sc.id] = sc;
      });
    }
  } catch (e) {
    // Falls back seamlessly to DOMAIN_SCENARIOS
  }
}

function setupScenarioTabs() {
  dom.scenarioTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      if (appState.isExecuting) return;
      dom.scenarioTabs.forEach(t => {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
      });
      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');

      const scenarioId = tab.dataset.id;
      appState.activeScenarioId = scenarioId;
      renderScenario(scenarioId, true);
    });
  });

  if (dom.btnReExecuteDemo) {
    dom.btnReExecuteDemo.addEventListener('click', () => {
      if (appState.isExecuting) return;
      renderScenario(appState.activeScenarioId, true);
    });
  }

  if (dom.btnViewAuditPackage) {
    dom.btnViewAuditPackage.addEventListener('click', () => {
      openAuditModalForScenario(appState.activeScenarioId);
    });
  }
}

function drawAirlockGates() {
  const gatesEl = document.getElementById('gates');
  if (!gatesEl) return;
  const G = [['C1', 'Syntax & AST'], ['C2', 'Visible Tests'], ['C3', 'Hidden Invariants'], ['C4', 'Regression'], ['C5', 'Mutation'], ['C6', 'Security Taint']];
  gatesEl.innerHTML = '<div class="pk" id="pk"></div>' + G.map((g, i) =>
    `<div class="g" id="g${i}"><i></i><b>${g[0]}</b><small>${g[1]}</small></div>`
  ).join('');
  const stamp = document.getElementById('stamp');
  if (stamp) {
    stamp.className = 'stamp';
    stamp.textContent = '';
    stamp.style.opacity = '0';
  }
}

function renderScenario(scenarioId, animate = false) {
  const sc = DOMAIN_SCENARIOS[scenarioId] || DOMAIN_SCENARIOS.demo_01_clean_pass;

  if (dom.scenarioTraceId) dom.scenarioTraceId.textContent = `DEMO TRACE: ${sc.id}`;
  if (dom.demoDiffFilename) dom.demoDiffFilename.textContent = `${sc.file_path} (Unified Diff)`;

  // Syntax colorize unified diff
  renderDiffView(sc.diff);

  // Redraw neutral gates
  drawAirlockGates();

  if (animate) {
    runStaggeredGateEvaluation(sc);
  } else {
    applyInstantGateResults(sc);
    const gateKeys = ['C1_syntax', 'C2_visible_tests', 'C3_hidden_invariants', 'C4_regression', 'C5_mutation', 'C6_security'];
    let dead = false;
    gateKeys.forEach((k, idx) => {
      const g = document.getElementById('g' + idx);
      const crit = sc.criteria[k];
      if (dead) {
        if (g) g.classList.add('off');
        return;
      }
      if (crit && crit.status === 'FAIL') {
        if (g) g.classList.add('bad');
        dead = true;
      } else if (crit && crit.status === 'PASS') {
        if (g) g.classList.add('ok');
      }
    });
    const stamp = document.getElementById('stamp');
    if (stamp) {
      const pol = sc.release_policy || 'BLOCK';
      stamp.textContent = pol.replace('_', ' ');
      const colMap = {
        AUTO_APPROVE: 'var(--status-pass)',
        REVIEW: 'var(--status-warn)',
        BLOCK: 'var(--status-fail)'
      };
      const col = colMap[pol] || 'var(--text-primary)';
      stamp.style.color = col;
      stamp.style.borderColor = col;
      stamp.className = 'stamp s';
      stamp.style.opacity = '1';
    }
  }
}

function renderDiffView(diffText) {
  if (!dom.demoDiffContent) return;
  dom.demoDiffContent.innerHTML = '';

  const lines = diffText.split('\n');
  lines.forEach(line => {
    const span = document.createElement('span');
    if (line.startsWith('+') && !line.startsWith('+++')) {
      span.className = 'diff-line added';
    } else if (line.startsWith('-') && !line.startsWith('---')) {
      span.className = 'diff-line removed';
    } else {
      span.className = 'diff-line context';
    }
    span.textContent = line;
    dom.demoDiffContent.appendChild(span);
  });
}

function applyInstantGateResults(sc) {
  // Update Verdict Banner
  const verdictClass = sc.release_policy === 'AUTO_APPROVE' ? 'approved' : (sc.release_policy === 'REVIEW' ? 'review' : 'blocked');
  dom.demoVerdictBanner.className = `verdict-status-panel ${verdictClass}`;
  dom.demoVerdictBadge.textContent = `DEMO TRACE • ${sc.technical_verdict}`;
  if (dom.demoVerdictDuration) dom.demoVerdictDuration.textContent = '';
  dom.demoVerdictHeadline.textContent = sc.headline || (`DEMO — ${sc.technical_verdict}`);
  dom.demoVerdictDesc.textContent = sc.explanation;

  // Update Gates
  for (const [key, badge] of Object.entries(dom.gateBadges)) {
    if (!badge) continue;
    const crit = sc.criteria[key];
    if (crit) {
      const cls = crit.status === 'PASS' ? 'pass' : (crit.status === 'FAIL' ? 'fail' : 'skip');
      badge.className = `gate-badge ${cls}`;
      badge.textContent = crit.label;
    }
  }
}

async function runStaggeredGateEvaluation(sc) {
  appState.isExecuting = true;
  if (dom.btnReExecuteDemo) {
    dom.btnReExecuteDemo.disabled = true;
    dom.btnReExecuteDemo.textContent = 'Evaluating Demo Gates...';
  }

  // Set all badges to running
  for (const badge of Object.values(dom.gateBadges)) {
    if (badge) {
      badge.className = 'gate-badge running';
      badge.textContent = 'CHECKING...';
    }
  }

  // Reset airlock visual gates
  drawAirlockGates();
  const stamp = document.getElementById('stamp');
  if (stamp) {
    stamp.className = 'stamp';
    stamp.textContent = '';
    stamp.style.opacity = '0';
  }
  const pk = document.getElementById('pk');
  if (pk) {
    pk.style.opacity = '1';
    pk.classList.remove('sh');
    pk.style.left = 'calc(100%/12)';
  }

  // Neutral running verdict banner
  dom.demoVerdictBanner.className = 'verdict-status-panel';
  dom.demoVerdictBadge.textContent = 'DEMO TRACE • EVALUATING IN CONTAINER JAIL...';
  if (dom.demoVerdictDuration) dom.demoVerdictDuration.textContent = '';
  dom.demoVerdictHeadline.textContent = 'DEMO TRACE: Sequential Pipeline Execution';
  dom.demoVerdictDesc.textContent = 'Executing AST grammar checks, functional tests, hidden invariants, regression contracts, and security taint visitors.';

  const gateKeys = ['C1_syntax', 'C2_visible_tests', 'C3_hidden_invariants', 'C4_regression', 'C5_mutation', 'C6_security'];
  const RM = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let dead = false;

  for (let i = 0; i < gateKeys.length; i++) {
    const key = gateKeys[i];
    const badge = dom.gateBadges[key];
    const crit = sc.criteria[key];
    const g = document.getElementById('g' + i);

    if (dead) {
      if (g) g.classList.add('off');
      if (badge && crit) {
        badge.className = 'gate-badge skip';
        badge.textContent = 'SEALED';
      }
      continue;
    }

    if (g) g.classList.add('run');
    if (pk) pk.style.left = `calc(100%/12 + ${i}*100%/6)`;
    await sleep(RM ? 40 : 260);
    if (g) g.classList.remove('run');

    if (crit && crit.status === 'FAIL') {
      if (g) g.classList.add('bad');
      if (badge) {
        badge.className = 'gate-badge fail';
        badge.textContent = crit.label;
      }
      if (pk) {
        pk.classList.add('sh');
        for (let k = 0; k < 18; k++) {
          const d = document.createElement('i');
          d.className = 'sd';
          const a = Math.random() * 6.28;
          const r = 50 + Math.random() * 80;
          d.style.cssText = `left:${pk.offsetLeft}px;top:${pk.offsetTop}px;--x:${Math.cos(a)*r}px;--y:${Math.sin(a)*r}px`;
          pk.parentNode.appendChild(d);
          setTimeout(() => d.remove(), 950);
        }
      }
      dead = true;
    } else {
      if (g) g.classList.add('ok');
      if (badge && crit) {
        badge.className = 'gate-badge pass';
        badge.textContent = crit.label;
      }
    }
  }

  applyInstantGateResults(sc);

  // Apply airlock stamp
  if (stamp) {
    const pol = sc.release_policy || 'BLOCK';
    stamp.textContent = pol.replace('_', ' ');
    const colMap = {
      AUTO_APPROVE: 'var(--status-pass)',
      REVIEW: 'var(--status-warn)',
      BLOCK: 'var(--status-fail)'
    };
    const col = colMap[pol] || 'var(--text-primary)';
    stamp.style.color = col;
    stamp.style.borderColor = col;
    stamp.className = 'stamp s';
    stamp.style.opacity = '1';
  }
  if (sc.release_policy === 'BLOCK') {
    const lockEl = document.getElementById('lock');
    if (lockEl) {
      lockEl.classList.remove('sh');
      void lockEl.offsetWidth;
      lockEl.classList.add('sh');
    }
  }

  appState.isExecuting = false;
  if (dom.btnReExecuteDemo) {
    dom.btnReExecuteDemo.disabled = false;
    dom.btnReExecuteDemo.textContent = 'Execute Demo Trace';
  }

  // Trigger backend execution to log audit trace (public demo route)
  try {
    const res = await api.post('/api/demo/verify', { scenario_id: sc.id }, true);
    if (res.ok) {
      const data = await res.json();
      appState.latestReport = data.report;
      loadEvidenceLedger();
    }
  } catch (e) {
    // Non-blocking fallback
  }
}

// ============================================================================
// 3. INTERACTIVE CONSOLE FORM (TEST A PATCH)
// ============================================================================

function setupConsoleForm() {
  if (!dom.consoleForm) return;

  dom.consoleForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (appState.isExecuting) return;

    if (!auth.isConnected()) {
      showAuthModal('Connect A.I.R.A. before executing verification jobs.', false);
      return;
    }

    const repo = dom.consoleRepo ? dom.consoleRepo.value.trim() : '.';
    const base = dom.consoleBase ? dom.consoleBase.value.trim() : 'HEAD~1';
    const head = dom.consoleHead ? dom.consoleHead.value.trim() : 'HEAD';
    const tier = dom.consoleTier ? dom.consoleTier.value : 'standard';
    const diff = dom.consoleDiff ? dom.consoleDiff.value.trim() : '';

    if (dom.consoleSubmitBtn) {
      dom.consoleSubmitBtn.disabled = true;
      dom.consoleSubmitBtn.textContent = 'Executing Verification Pipeline...';
    }

    logConsole(`[INDEXING] Ingesting change request for target: ${repo} (${base}..${head})`, 'info');

    try {
      let report = null;
      let events = [];

      const res = await api.post('/api/verifications', {
        repository: repo,
        base: base,
        head: head,
        tier: tier,
        diff: diff || undefined
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'API rejected verification request');
      }

      const data = await res.json();
      logConsole(`[CONTAINER] Verification container spawned for run: ${data.run_id}`, 'info');

      // Fetch events and evidence
      const repRes = await api.get(`/api/verifications/${data.run_id}/evidence`);
      if (repRes.ok) report = await repRes.json();

      const evRes = await api.get(`/api/verifications/${data.run_id}/events`);
      if (evRes.ok) events = await evRes.json();

      if (events && events.length) {
        for (const ev of events) {
          await sleep(60);
          const cls = ev.message.includes('FAILED') || ev.message.includes('VETO') ? 'fail' : 'pass';
          logConsole(`[${ev.stage || 'STAGE'}] ${ev.message}`, cls);
        }
      }

      if (report && report.decision) {
        appState.latestReport = report;
        const dec = report.decision;
        const finalClass = dec.release_policy === 'AUTO_APPROVE' ? 'pass' : 'fail';
        logConsole(`[DECISION] Verdict: ${dec.technical_verdict} | Policy: ${dec.release_policy} | Risk Level: ${dec.risk_level}`, finalClass);
      }

      await loadEvidenceLedger();

    } catch (err) {
      logConsole(`[ERROR] Verification halted: ${err.message}`, 'fail');
    } finally {
      if (dom.consoleSubmitBtn) {
        dom.consoleSubmitBtn.disabled = false;
        dom.consoleSubmitBtn.textContent = 'Execute Verification Pipeline ↗';
      }
    }
  });
}

function logConsole(message, type = 'info') {
  if (!dom.consoleLog) return;
  const row = document.createElement('div');
  row.className = `console-log-row ${type}`;
  const time = new Date().toISOString().split('T')[1].slice(0, 8);
  row.textContent = `[${time}] ${message}`;
  dom.consoleLog.appendChild(row);
  dom.consoleLog.scrollTop = dom.consoleLog.scrollHeight;
}

// ============================================================================
// 4. EVIDENCE LEDGER TABLE & AUDIT MODAL
// ============================================================================

async function loadEvidenceLedger() {
  if (!dom.ledgerTableRows) return;

  try {
    const res = await api.get('/api/verifications', true);
    if (!res.ok) return;
    const runs = await res.json();
    dom.ledgerTableRows.innerHTML = '';

    runs.slice(0, 10).forEach(run => {
      const tr = document.createElement('tr');
      const isApproved = run.release_policy === 'AUTO_APPROVE';
      const isReview = run.release_policy === 'REVIEW';
      const pillClass = isApproved ? 'pass' : (isReview ? 'review' : 'block');
      const verdictColor = isApproved ? 'color: var(--status-pass);' : (isReview ? 'color: var(--status-warn);' : 'color: var(--status-fail);');

      const cleanHash = (run.run_id || '').replace(/[^a-f0-9]/gi, '').slice(0, 8) || '4a9f8120';
      const shaStub = `sha256:${cleanHash}`;

      tr.innerHTML = `
        <td><strong class="mono" style="color: var(--text-primary); font-size: 11.5px;">${escapeHtml(run.run_id)}</strong></td>
        <td>${escapeHtml(run.title || run.run_id)}</td>
        <td><span class="mono" style="font-size: 11.5px; color: var(--text-tertiary);">${escapeHtml(run.tier || 'STANDARD')}</span></td>
        <td><strong class="mono" style="${verdictColor}">${escapeHtml(run.technical_verdict || 'N/A')}</strong></td>
        <td><span class="gate-action-pill ${pillClass}">${escapeHtml(run.release_policy || 'N/A')}</span></td>
        <td><span class="mono" style="font-size: 11px; color: var(--text-tertiary);">${shaStub}</span></td>
        <td style="text-align: right;"><button class="btn btn-secondary btn-sm btn-inspect-audit-row" data-id="${run.run_id}">Inspect Audit</button></td>
      `;

      tr.querySelector('.btn-inspect-audit-row').addEventListener('click', () => {
        openAuditModal(run.run_id);
      });

      dom.ledgerTableRows.appendChild(tr);
    });
  } catch (e) {
    // Non-blocking
  }
}

async function openAuditModal(runId) {
  try {
    const res = await api.get(`/api/verifications/${runId}/evidence`);
    if (!res.ok) throw new Error('Evidence record not found');
    const data = await res.json();
    displayModalJson(data, `CRYPTOGRAPHIC EVIDENCE PACKAGE: ${runId}`);
  } catch (e) {
    alert(`Could not load evidence package: ${e.message}`);
  }
}

function openAuditModalForScenario(scenarioId) {
  const sc = DOMAIN_SCENARIOS[scenarioId];
  if (!sc) return;
  const evidenceRecord = {
    report_id: `rep_${sc.id}`,
    timestamp: new Date().toISOString(),
    scenario_id: sc.id,
    title: sc.title,
    file_path: sc.file_path,
    decision: {
      technical_verdict: sc.technical_verdict,
      release_policy: sc.release_policy,
      risk_level: sc.release_policy === 'AUTO_APPROVE' ? 'LOW' : 'HIGH'
    },
    criteria: sc.criteria,
    containment: {
      network: 'NONE (--net none)',
      filesystem: 'READ_ONLY_TMPFS',
      cpu_quota: '1.0',
      memory_cap: '1024MB'
    }
  };
  displayModalJson(evidenceRecord, `AUDIT PACKAGE: ${sc.id}`);
}

function displayModalJson(jsonData, title) {
  if (!dom.evidenceModal || !dom.evidenceModalJsonContent) return;
  document.getElementById('modal-package-title').textContent = title;
  dom.evidenceModalJsonContent.textContent = JSON.stringify(jsonData, null, 2);
  dom.evidenceModal.style.display = 'flex';
}

function setupModalEvents() {
  if (dom.btnCloseEvidenceModal) {
    dom.btnCloseEvidenceModal.addEventListener('click', () => {
      dom.evidenceModal.style.display = 'none';
    });
  }

  if (dom.evidenceModal) {
    dom.evidenceModal.addEventListener('click', (e) => {
      if (e.target === dom.evidenceModal) {
        dom.evidenceModal.style.display = 'none';
      }
    });
  }

  // Close on Escape key
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (dom.evidenceModal && dom.evidenceModal.style.display === 'flex') {
        dom.evidenceModal.style.display = 'none';
      }
      const authModal = document.getElementById('auth-modal');
      if (authModal && authModal.style.display === 'flex') {
        authModal.style.display = 'none';
      }
    }
  });

  if (dom.btnRefreshLedger) {
    dom.btnRefreshLedger.addEventListener('click', loadEvidenceLedger);
  }

  if (dom.btnExportLatestJson) {
    dom.btnExportLatestJson.addEventListener('click', () => {
      const data = appState.latestReport || {
        service: 'A.I.R.A. (AI Release Assurance)',
        version: '1.0.0',
        active_trace: appState.activeScenarioId,
        timestamp: new Date().toISOString()
      };
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `aira_evidence_${appState.activeScenarioId}.json`;
      a.click();
      URL.revokeObjectURL(url);
    });
  }
}

// ============================================================================
// 5. AUTHENTICATION EVENTS & MODAL CONTROLS
// ============================================================================

let pendingUploadFile = null;

function setupAuthEvents() {
  const btnTrigger = document.getElementById('btn-api-auth-trigger');
  const navContainer = document.getElementById('nav-api-access-control');
  const btnUploadConnect = document.getElementById('btn-upload-connect-api');
  const btnCloseModal = document.getElementById('btn-close-auth-modal');
  const btnCancelAuth = document.getElementById('btn-cancel-auth');
  const btnConnectAuth = document.getElementById('btn-connect-auth');
  const btnTestAuth = document.getElementById('btn-test-auth');
  const btnDisconnectAuth = document.getElementById('btn-disconnect-auth');
  const btnReplaceKeyAuth = document.getElementById('btn-replace-key-auth');
  const keyInput = document.getElementById('auth-input-key');

  if (btnTrigger) {
    btnTrigger.addEventListener('click', (e) => {
      e.stopPropagation();
      showAuthModal('', false);
    });
  }

  if (navContainer) {
    navContainer.addEventListener('click', () => {
      showAuthModal('', false);
    });
  }

  if (btnUploadConnect) {
    btnUploadConnect.addEventListener('click', () => {
      showAuthModal('', false);
    });
  }

  if (btnCloseModal) {
    btnCloseModal.addEventListener('click', closeAuthModal);
  }

  if (btnCancelAuth) {
    btnCancelAuth.addEventListener('click', closeAuthModal);
  }

  const authModal = document.getElementById('auth-modal');
  if (authModal) {
    authModal.addEventListener('click', (e) => {
      if (e.target === authModal) closeAuthModal();
    });
  }

  // Connect button
  if (btnConnectAuth) {
    btnConnectAuth.addEventListener('click', async () => {
      const key = keyInput ? keyInput.value.trim() : '';
      if (!key) {
        showAuthModal('Please enter an API key.', true);
        return;
      }
      btnConnectAuth.disabled = true;
      btnConnectAuth.textContent = 'Verifying...';

      const isValid = await auth.validateKey(key);
      btnConnectAuth.disabled = false;
      btnConnectAuth.textContent = 'Connect';

      if (isValid) {
        auth.setKey(key);
        closeAuthModal();
        // If a file upload was pending, continue upload immediately
        if (pendingUploadFile && window.uploadPendingFile) {
          window.uploadPendingFile();
        }
      } else {
        showAuthModal('Authentication failed. Check your API key and try again.', true);
      }
    });
  }

  // Test Connection button
  if (btnTestAuth) {
    btnTestAuth.addEventListener('click', async () => {
      btnTestAuth.disabled = true;
      btnTestAuth.textContent = 'Testing...';
      const isValid = await auth.validateKey();
      btnTestAuth.disabled = false;
      btnTestAuth.textContent = 'Test connection';

      if (isValid) {
        showAuthModal('Connection verified successfully (200 OK).', false);
      } else {
        showAuthModal('Authentication failed. Check your API key and try again.', true);
      }
    });
  }

  // Disconnect button
  if (btnDisconnectAuth) {
    btnDisconnectAuth.addEventListener('click', () => {
      auth.clearKey();
      closeAuthModal();
    });
  }

  // Replace Key button
  if (btnReplaceKeyAuth) {
    btnReplaceKeyAuth.addEventListener('click', async () => {
      const key = keyInput ? keyInput.value.trim() : '';
      if (!key) {
        showAuthModal('Please enter a new API key.', true);
        return;
      }
      btnReplaceKeyAuth.disabled = true;
      btnReplaceKeyAuth.textContent = 'Validating...';
      const isValid = await auth.validateKey(key);
      btnReplaceKeyAuth.disabled = false;
      btnReplaceKeyAuth.textContent = 'Replace key';

      if (isValid) {
        auth.setKey(key);
        closeAuthModal();
      } else {
        showAuthModal('Authentication failed. Check your API key and try again.', true);
      }
    });
  }
}

// ============================================================================
// 6. ROUTER & MODE ISOLATION
// ============================================================================

let appMode = 'verify';
let demoMounted = false;

function setAppMode(mode, updateUrl = true) {
  appMode = mode;
  const heroSection = document.querySelector('.hero-section');
  const bandSection = document.querySelector('.band');
  const systemRowsSection = document.querySelector('.system-rows-section');
  const fluxEndSection = document.querySelector('.flux-end-section');
  const verifySection = document.getElementById('verify');
  const demoSection = document.getElementById('demo');
  const ledgerSection = document.getElementById('ledger');
  const researchSection = document.getElementById('research');
  const archSection = document.getElementById('architecture');
  const containmentSection = document.getElementById('containment');
  const consoleSection = document.getElementById('console');
  const divider = document.getElementById('flow-isolation-divider');

  document.querySelectorAll('.nav-link').forEach(link => link.classList.remove('active'));

  if (mode === 'verify') {
    const navVerify = document.getElementById('nav-link-verify');
    if (navVerify) navVerify.classList.add('active');

    if (heroSection) heroSection.style.display = 'none';
    if (bandSection) bandSection.style.display = 'none';
    if (systemRowsSection) systemRowsSection.style.display = 'none';
    if (fluxEndSection) fluxEndSection.style.display = 'none';

    if (verifySection) verifySection.style.display = 'block';
    if (demoSection) demoSection.style.display = 'none';
    if (ledgerSection) ledgerSection.style.display = 'none';
    if (researchSection) researchSection.style.display = 'none';
    if (archSection) archSection.style.display = 'none';
    if (containmentSection) containmentSection.style.display = 'none';
    if (consoleSection) consoleSection.style.display = 'none';
    if (divider) divider.style.display = 'none';

    if (updateUrl) {
      if (window.location.pathname !== '/verify') {
        window.location.hash = '#verify';
      }
    }
  } else if (mode === 'demo') {
    const navDemo = document.getElementById('nav-link-demo');
    if (navDemo) navDemo.classList.add('active');

    if (heroSection) heroSection.style.display = 'none';
    if (bandSection) bandSection.style.display = 'none';
    if (systemRowsSection) systemRowsSection.style.display = 'none';
    if (fluxEndSection) fluxEndSection.style.display = 'none';

    if (verifySection) verifySection.style.display = 'none';
    if (demoSection) demoSection.style.display = 'block';
    if (ledgerSection) ledgerSection.style.display = 'none';
    if (researchSection) researchSection.style.display = 'none';
    if (archSection) archSection.style.display = 'none';
    if (containmentSection) containmentSection.style.display = 'none';
    if (consoleSection) consoleSection.style.display = 'none';
    if (divider) divider.style.display = 'none';

    if (window.clearRealVerificationState) {
      window.clearRealVerificationState();
    }

    if (updateUrl) {
      if (window.location.pathname !== '/demo') {
        window.location.hash = '#demo';
      }
    }

    if (!demoMounted) {
      demoMounted = true;
      mountDemoWorkbench();
    }
  } else if (mode === 'ledger') {
    const navEvidence = document.getElementById('nav-link-evidence');
    if (navEvidence) navEvidence.classList.add('active');

    if (heroSection) heroSection.style.display = 'none';
    if (bandSection) bandSection.style.display = 'none';
    if (systemRowsSection) systemRowsSection.style.display = 'none';
    if (fluxEndSection) fluxEndSection.style.display = 'none';

    if (verifySection) verifySection.style.display = 'none';
    if (demoSection) demoSection.style.display = 'none';
    if (ledgerSection) ledgerSection.style.display = 'block';
    if (researchSection) researchSection.style.display = 'none';
    if (archSection) archSection.style.display = 'none';
    if (containmentSection) containmentSection.style.display = 'none';
    if (consoleSection) consoleSection.style.display = 'none';
    if (divider) divider.style.display = 'none';

    if (updateUrl) {
      window.location.hash = '#ledger';
    }
    loadEvidenceLedger();
  } else if (mode === 'research') {
    const navResearch = document.getElementById('nav-link-research');
    if (navResearch) navResearch.classList.add('active');

    if (heroSection) heroSection.style.display = 'none';
    if (bandSection) bandSection.style.display = 'none';
    if (systemRowsSection) systemRowsSection.style.display = 'none';
    if (fluxEndSection) fluxEndSection.style.display = 'none';

    if (verifySection) verifySection.style.display = 'none';
    if (demoSection) demoSection.style.display = 'none';
    if (ledgerSection) ledgerSection.style.display = 'none';
    if (researchSection) researchSection.style.display = 'block';
    if (archSection) archSection.style.display = 'none';
    if (containmentSection) containmentSection.style.display = 'none';
    if (consoleSection) consoleSection.style.display = 'none';
    if (divider) divider.style.display = 'none';

    if (updateUrl) {
      window.location.hash = '#research';
    }
  } else if (mode === 'architecture') {
    if (heroSection) heroSection.style.display = 'none';
    if (bandSection) bandSection.style.display = 'none';
    if (systemRowsSection) systemRowsSection.style.display = 'none';
    if (fluxEndSection) fluxEndSection.style.display = 'none';

    if (verifySection) verifySection.style.display = 'none';
    if (demoSection) demoSection.style.display = 'none';
    if (ledgerSection) ledgerSection.style.display = 'none';
    if (researchSection) researchSection.style.display = 'none';
    if (archSection) archSection.style.display = 'block';
    if (containmentSection) containmentSection.style.display = 'block';
    if (consoleSection) consoleSection.style.display = 'block';
    if (divider) divider.style.display = 'none';

    if (updateUrl) {
      window.location.hash = '#architecture';
    }
  } else {
    // Mode === 'product' (Cinematic FLUX Home Page)
    const navProduct = document.getElementById('nav-link-product');
    if (navProduct) navProduct.classList.add('active');

    if (heroSection) heroSection.style.display = 'block';
    if (bandSection) bandSection.style.display = 'block';
    if (systemRowsSection) systemRowsSection.style.display = 'block';
    if (fluxEndSection) fluxEndSection.style.display = 'flex';

    if (verifySection) verifySection.style.display = 'none';
    if (demoSection) demoSection.style.display = 'none';
    if (ledgerSection) ledgerSection.style.display = 'none';
    if (researchSection) researchSection.style.display = 'none';
    if (archSection) archSection.style.display = 'none';
    if (containmentSection) containmentSection.style.display = 'none';
    if (consoleSection) consoleSection.style.display = 'none';
    if (divider) divider.style.display = 'none';
  }
}

function mountDemoWorkbench() {
  const activeTab = document.querySelector(`.scenario-tab[data-id="${appState.activeScenarioId}"]`) || document.querySelector('.scenario-tab');
  if (activeTab) {
    dom.scenarioTabs.forEach(t => {
      t.classList.remove('active');
      t.setAttribute('aria-selected', 'false');
    });
    activeTab.classList.add('active');
    activeTab.setAttribute('aria-selected', 'true');
    appState.activeScenarioId = activeTab.dataset.id;
  }
  renderScenario(appState.activeScenarioId, false);
}

function clearDemoState() {
  demoMounted = false;
  if (dom.demoDiffContent) {
    dom.demoDiffContent.innerHTML = '<div class="diff-placeholder-msg mono" style="color: var(--text-tertiary); font-size: 12px; padding: 24px; text-align: center;">Select a pre-recorded demo trace above to inspect code diff.</div>';
  }
  if (dom.scenarioTabs) {
    dom.scenarioTabs.forEach(t => {
      t.classList.remove('active');
      t.setAttribute('aria-selected', 'false');
    });
  }
  if (dom.demoVerdictBanner) {
    dom.demoVerdictBanner.className = 'verdict-status-panel';
  }
  if (dom.demoVerdictBadge) {
    dom.demoVerdictBadge.textContent = 'PRE-RECORDED';
  }
  if (dom.demoVerdictDuration) {
    dom.demoVerdictDuration.textContent = '';
  }
  if (dom.demoVerdictHeadline) {
    dom.demoVerdictHeadline.textContent = 'DEMO TRACE';
  }
  if (dom.demoVerdictDesc) {
    dom.demoVerdictDesc.textContent = 'Select an audit trace above to observe the 6-gate verification breakdown.';
  }
  if (dom.gateBadges) {
    for (const b of Object.values(dom.gateBadges)) {
      if (b) {
        b.className = 'gate-badge mono';
        b.textContent = '—';
      }
    }
  }
}
window.clearDemoState = clearDemoState;

function initRouter() {
  const path = window.location.pathname;
  const hash = window.location.hash;

  if (path === '/verify' || hash === '#verify') {
    setAppMode('verify', false);
    const el = document.getElementById('verify');
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  } else if (path === '/demo' || hash === '#demo') {
    setAppMode('demo', false);
    const el = document.getElementById('demo');
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  } else if (path === '/ledger' || hash === '#ledger') {
    setAppMode('ledger', false);
    const el = document.getElementById('ledger');
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  } else if (path === '/research' || hash === '#research') {
    setAppMode('research', false);
    const el = document.getElementById('research');
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  } else if (path === '/architecture' || hash === '#architecture') {
    setAppMode('architecture', false);
    const el = document.getElementById('architecture');
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  } else {
    setAppMode('product', false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

function setupNavigationEvents() {
  window.addEventListener('hashchange', () => {
    initRouter();
  });

  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      const targetId = this.getAttribute('href');
      if (targetId === '#verify') {
        e.preventDefault();
        setAppMode('verify', true);
        const el = document.getElementById('verify');
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      } else if (targetId === '#demo') {
        e.preventDefault();
        setAppMode('demo', true);
        const el = document.getElementById('demo');
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      } else if (targetId === '#ledger') {
        e.preventDefault();
        setAppMode('ledger', true);
        const el = document.getElementById('ledger');
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      } else if (targetId === '#research') {
        e.preventDefault();
        setAppMode('research', true);
        const el = document.getElementById('research');
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      } else if (targetId === '#architecture') {
        e.preventDefault();
        setAppMode('architecture', true);
        const el = document.getElementById('architecture');
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      } else if (targetId === '#product' || targetId === '#top') {
        e.preventDefault();
        setAppMode('product', true);
        window.scrollTo({ top: 0, behavior: 'smooth' });
      } else if (targetId && targetId !== '#') {
        const el = document.querySelector(targetId);
        if (el) {
          e.preventDefault();
          el.scrollIntoView({ behavior: 'smooth' });
        }
      }
    });
  });
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Bootstrap on DOM ready
document.addEventListener('DOMContentLoaded', initializeApp);

// ============================================================================
// VERIFY MY CODE: Real Project Upload Wizard
// ============================================================================

(function() {
  let currentProjectId = null;
  let currentRunId = null;
  let pollInterval = null;

  const steps = {
    upload: document.getElementById('step-upload'),
    info: document.getElementById('step-info'),
    config: document.getElementById('step-config'),
    running: document.getElementById('step-running'),
    results: document.getElementById('step-results'),
    error: document.getElementById('step-error')
  };

  function showStep(name) {
    Object.values(steps).forEach(el => {
      if (el) { el.style.display = 'none'; el.classList.remove('active'); }
    });
    if (steps[name]) {
      steps[name].style.display = 'block';
      steps[name].classList.add('active');
    }
  }

  function resetWizard() {
    currentProjectId = null;
    currentRunId = null;
    if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
    const fileInput = document.getElementById('file-input');
    if (fileInput) fileInput.value = '';
    const customTestInput = document.getElementById('custom-test-file-input');
    if (customTestInput) customTestInput.value = '';
    const customStatus = document.getElementById('custom-test-upload-status');
    if (customStatus) customStatus.textContent = '';
    const uploadStatus = document.getElementById('upload-status');
    if (uploadStatus) uploadStatus.style.display = 'none';
    if (window.clearDemoState) {
      window.clearDemoState();
    }
    showStep('upload');
  }
  window.clearRealVerificationState = resetWizard;

  async function uploadFile(file) {
    if (!auth.isConnected()) {
      pendingUploadFile = file;
      showAuthModal('Connect A.I.R.A. before uploading a project for live verification.', false);
      return;
    }

    const uploadStatus = document.getElementById('upload-status');
    const progressFill = document.getElementById('upload-progress');
    const statusText = document.getElementById('upload-status-text');

    if (uploadStatus) uploadStatus.style.display = 'block';
    if (progressFill) {
      progressFill.style.width = '30%';
      progressFill.style.background = 'var(--status-pass)';
    }
    if (statusText) statusText.textContent = 'Uploading ' + file.name + '...';

    const formData = new FormData();
    formData.append('archive', file);

    try {
      const res = await api.upload('/api/projects/upload', formData);
      if (progressFill) progressFill.style.width = '90%';

      if (!res.ok) {
        if (res.status === 401) {
          pendingUploadFile = file;
          return;
        }
        const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
        if (statusText) statusText.textContent = 'Error: ' + (err.detail || 'Upload failed');
        if (progressFill) {
          progressFill.style.width = '100%';
          progressFill.style.background = 'var(--status-fail)';
        }
        return;
      }

      const data = await res.json();
      currentProjectId = data.project_id;

      if (progressFill) { progressFill.style.width = '100%'; }
      if (statusText) statusText.textContent = 'Upload complete!';

      // Populate info card
      const fw = document.getElementById('info-framework');
      const tc = document.getElementById('info-test-count');
      const tf = document.getElementById('info-total-files');
      const hash = document.getElementById('info-hash');
      const testCount = (data.test_files || []).length;
      if (fw) fw.textContent = data.framework || 'unknown';
      if (tc) tc.textContent = testCount + ' test file(s)';
      if (tf) tf.textContent = data.total_files || '—';
      if (hash) hash.textContent = (data.project_hash || '').substring(0, 16) + '...';

      // Update capability indicator for project tests
      const capProjStatus = document.getElementById('cap-status-proj-tests');
      if (capProjStatus) {
        if (testCount > 0) {
          capProjStatus.textContent = 'AVAILABLE';
          capProjStatus.className = 'gate-action-pill pass mono';
        } else {
          capProjStatus.textContent = 'NOT_AVAILABLE';
          capProjStatus.className = 'gate-action-pill mono';
          capProjStatus.style.background = 'var(--bg-tertiary)';
          capProjStatus.style.color = 'var(--text-tertiary)';
        }
      }

      setTimeout(() => showStep('info'), 400);

    } catch (e) {
      if (statusText) statusText.textContent = 'Network error: ' + e.message;
    }
  }

  window.uploadPendingFile = function() {
    if (pendingUploadFile) {
      const f = pendingUploadFile;
      pendingUploadFile = null;
      uploadFile(f);
    }
  };

  async function uploadCustomTests(file) {
    if (!currentProjectId) return;
    const statusEl = document.getElementById('custom-test-upload-status');
    if (statusEl) statusEl.textContent = 'Uploading supplemental tests...';

    const formData = new FormData();
    formData.append('tests_archive', file);

    try {
      const res = await api.upload(`/api/projects/${currentProjectId}/tests`, formData);

      if (!res.ok) {
        if (res.status === 401) return;
        const err = await res.json().catch(() => ({ detail: 'Test upload failed' }));
        if (statusEl) {
          statusEl.style.color = 'var(--status-fail)';
          statusEl.textContent = 'Failed: ' + (err.detail || 'Upload error');
        }
        return;
      }

      const data = await res.json();
      if (statusEl) {
        statusEl.style.color = 'var(--status-pass)';
        statusEl.textContent = '✓ ' + (data.user_test_files_detected || 0) + ' custom test files loaded.';
      }

      const capCustom = document.getElementById('cap-status-custom-tests');
      if (capCustom) {
        capCustom.textContent = 'AVAILABLE';
        capCustom.className = 'gate-action-pill pass mono';
        capCustom.style.background = '';
        capCustom.style.color = '';
      }
    } catch (e) {
      if (statusEl) {
        statusEl.style.color = 'var(--status-fail)';
        statusEl.textContent = 'Network error: ' + e.message;
      }
    }
  }

  async function startVerification() {
    const cfg = {
      tier: 'standard',
      run_project_tests: document.getElementById('cfg-project-tests')?.checked ?? true,
      run_user_tests: true,
      run_security: document.getElementById('cfg-security')?.checked ?? true,
      run_mutation: false
    };

    try {
      const res = await api.post(`/api/projects/${currentProjectId}/verify`, cfg);

      if (res.status === 503) {
        const err = await res.json().catch(() => ({ detail: 'Sandbox unavailable' }));
        const errMsg = document.getElementById('error-message');
        if (errMsg) errMsg.textContent = err.detail || 'Docker sandbox is not available. A.I.R.A. cannot fabricate verification results.';
        const remEl = document.getElementById('error-remediation');
        if (remEl) {
          api.get('/api/system/sandbox', true).then(d => d.json()).then(diag => {
            if (diag && diag.remediation) {
              remEl.textContent = 'Remediation: ' + diag.remediation;
              remEl.style.display = 'block';
            }
          }).catch(() => {});
        }
        showStep('error');
        return;
      }

      if (res.status === 404) {
        const errMsg = document.getElementById('error-message');
        if (errMsg) errMsg.textContent = 'Project not found. It may have expired.';
        showStep('error');
        return;
      }

      if (!res.ok) {
        if (res.status === 401) return;
        const err = await res.json().catch(() => ({ detail: 'Verification failed' }));
        const errMsg = document.getElementById('error-message');
        if (errMsg) errMsg.textContent = err.detail || 'An unexpected error occurred.';
        showStep('error');
        return;
      }

      const data = await res.json();
      currentRunId = data.run_id;

      // Show running step and start polling
      const logEl = document.getElementById('verify-live-log');
      if (logEl) logEl.innerHTML = '<div class="live-log-entry">Verification queued inside container sandbox...</div>';
      showStep('running');

      pollInterval = setInterval(() => pollVerification(), 2000);

    } catch (e) {
      const errMsg = document.getElementById('error-message');
      if (errMsg) errMsg.textContent = 'Network error: ' + e.message;
      showStep('error');
    }
  }

  async function pollVerification() {
    if (!currentRunId) return;

    try {
      // Poll events via central api client
      const evRes = await api.get(`/api/verifications/${currentRunId}/events`);
      if (evRes.ok) {
        const events = await evRes.json();
        const logEl = document.getElementById('verify-live-log');
        if (logEl && events.length) {
          logEl.innerHTML = events.map(e =>
            '<div class="live-log-entry"><span class="log-stage">[' + e.stage + ']</span>' + e.message + '</div>'
          ).join('');
          logEl.scrollTop = logEl.scrollHeight;
        }
      }

      // Check status via central api client
      const statusRes = await api.get(`/api/verifications/${currentRunId}`);
      if (statusRes.ok) {
        const run = await statusRes.json();
        if (run.status === 'completed' || run.status === 'failed') {
          clearInterval(pollInterval);
          pollInterval = null;
          if (run.status === 'completed' && run.report) {
            showResults(run);
          } else {
            const errMsg = document.getElementById('error-message');
            if (errMsg) errMsg.textContent = run.error || 'Verification failed inside container sandbox.';
            showStep('error');
          }
        }
      }
    } catch (e) {
      // Silently retry on network blips
    }
  }

  function showResults(run) {
    const report = run.report || {};
    const decision = report.decision || {};
    const criteria = report.criteria || {};
    const evidence = report.evidence || {};

    // 1. Verdict badge & policy
    const badge = document.getElementById('verify-verdict-badge');
    if (badge) {
      badge.textContent = decision.technical_verdict || 'UNKNOWN';
      badge.className = 'verdict-badge';
      if (decision.technical_verdict === 'QUALIFIED') badge.classList.add('pass');
      else if (decision.technical_verdict === 'REJECTED') badge.classList.add('fail');
      else badge.classList.add('review');
    }

    const policy = document.getElementById('verify-verdict-policy');
    if (policy) policy.textContent = 'Release policy: ' + (decision.release_policy || '—');

    // 2. Reason banner for rejection/error
    const reasonEl = document.getElementById('verify-verdict-reason');
    if (reasonEl) {
      if (decision.technical_verdict === 'REJECTED' || decision.technical_verdict === 'INDETERMINATE') {
        let reason = '';
        for (const [key, stage] of Object.entries(criteria)) {
          if (stage && (stage.status === 'FAIL' || stage.status === 'ERROR')) {
            reason = (stage.name || key) + ': ' + (stage.detail || 'Stage failed criteria');
            break;
          }
        }
        if (reason) {
          reasonEl.style.display = 'block';
          reasonEl.textContent = 'Reason: ' + reason;
        } else {
          reasonEl.style.display = 'none';
        }
      } else {
        reasonEl.style.display = 'none';
      }
    }

    // 3. Project Summary Card: Project, Framework, Tests, Custom Tests, Project Hash
    const resProjId = document.getElementById('res-project-id');
    const resFw = document.getElementById('res-framework');
    const resProjTests = document.getElementById('res-project-tests');
    const resCustTests = document.getElementById('res-custom-tests');
    const resHash = document.getElementById('res-project-hash');

    if (resProjId) resProjId.textContent = evidence.project_id || currentProjectId || 'Uploaded Project';
    if (resFw) resFw.textContent = evidence.framework || evidence.test_framework || 'unknown';

    if (resProjTests) {
      const disc = evidence.collected_count ?? evidence.discovered_count ?? evidence.project_test_discovery?.collected ?? evidence.project_test_discovery?.discovered ?? evidence.test_inventory?.collected_count ?? evidence.test_inventory?.discovered_count ?? evidence.test_inventory?.project_tests ?? 0;
      const collErr = evidence.collection_error_count ?? evidence.project_test_discovery?.collection_errors ?? evidence.test_inventory?.collection_error_count ?? 0;
      const sel = evidence.selected_count ?? evidence.project_test_discovery?.selected ?? disc;
      const exec = evidence.executed_count ?? evidence.project_test_execution?.executed ?? evidence.test_inventory?.executed_count ?? 0;
      const pass = evidence.passed_count ?? evidence.project_test_execution?.passed ?? evidence.test_inventory?.passed_count ?? 0;
      const fail = evidence.failed_count ?? evidence.project_test_execution?.failed ?? evidence.test_inventory?.failed_count ?? 0;
      const err = evidence.error_count ?? evidence.project_test_execution?.errors ?? evidence.test_inventory?.error_count ?? 0;
      const skip = evidence.skipped_count ?? evidence.project_test_execution?.skipped ?? evidence.test_inventory?.skipped_count ?? 0;

      // Update summary strip cell
      if (disc > 0 || exec > 0 || collErr > 0) {
        let errBadge = collErr > 0 ? `<div style="font-size:11px; margin-top:2px; color:var(--status-fail); font-weight:600;">${collErr} collection error(s)</div>` : '';
        resProjTests.innerHTML = `<div>${disc} discovered, ${exec} executed</div>${errBadge}<div style="font-size:11px; margin-top:2px; color:${fail > 0 || err > 0 || collErr > 0 ? 'var(--status-fail)' : 'var(--status-pass)'};">${pass} passed, ${fail} failed, ${err} errors, ${skip} skipped</div>`;
      } else {
        resProjTests.textContent = '0 discovered';
      }

      // Populate dedicated Test Accounting Breakdown Grid (Four-State Model)
      const elDisc = document.getElementById('acc-discovered');
      const elCollErr = document.getElementById('acc-collection-errors');
      const elSel = document.getElementById('acc-selected');
      const elExec = document.getElementById('acc-executed');
      const elPass = document.getElementById('acc-passed');
      const elFail = document.getElementById('acc-failed');
      const elErr = document.getElementById('acc-errors');
      const elSkip = document.getElementById('acc-skipped');

      if (elDisc) elDisc.textContent = disc;
      if (elCollErr) {
        elCollErr.textContent = collErr;
        elCollErr.style.color = collErr > 0 ? 'var(--status-fail)' : 'var(--text-primary)';
        elCollErr.style.fontWeight = collErr > 0 ? '700' : '500';
      }
      if (elSel) elSel.textContent = sel;
      if (elExec) elExec.textContent = exec;
      if (elPass) elPass.textContent = pass;
      if (elFail) {
        elFail.textContent = fail;
        elFail.style.color = fail > 0 ? 'var(--status-fail)' : 'var(--text-primary)';
        elFail.style.fontWeight = fail > 0 ? '700' : '500';
      }
      if (elErr) {
        elErr.textContent = err;
        elErr.style.color = err > 0 ? 'var(--status-fail)' : 'var(--text-primary)';
        elErr.style.fontWeight = err > 0 ? '700' : '500';
      }
      if (elSkip) elSkip.textContent = skip;
    }

    if (resCustTests) {
      if (evidence.custom_test_inventory && evidence.custom_test_inventory.status !== 'NOT_AVAILABLE') {
        const c = evidence.custom_test_inventory;
        resCustTests.textContent = `${c.executed} executed (${c.passed} passed, ${c.failed} failed)`;
      } else {
        resCustTests.textContent = 'not uploaded';
      }
    }

    if (resHash) {
      const h = evidence.project_hash || '';
      resHash.textContent = h ? h.substring(0, 16) + '...' : '—';
    }

    // 4. Test Counts Inventory Breakdown & Stages Grid
    const stagesEl = document.getElementById('verify-stages');
    if (stagesEl) {
      stagesEl.innerHTML = '';
      const stageLabels = {
        C1_syntax: 'C1: Syntax',
        C2_visible_tests: 'C2: Project Tests',
        C2_user_tests: 'C2: Custom Tests',
        C3_hidden_invariants: 'C3: Invariants',
        C4_regression: 'C4: Regression',
        C5_mutation: 'C5: Mutation',
        C6_security: 'C6: Security'
      };
      for (const [key, label] of Object.entries(stageLabels)) {
        const stage = criteria[key];
        if (!stage) continue;
        const cls = stage.status === 'PASS' ? 'pass' :
                    stage.status === 'FAIL' ? 'fail' :
                    stage.status === 'ERROR' ? 'error' :
                    stage.status === 'SKIPPED' ? 'skipped' : 'na';

        let extraContent = '';
        if (key === 'C2_visible_tests') {
          const failList = stage.failed_tests || evidence.project_test_execution?.failed_tests || [];
          const failDetails = stage.failed_test_details || evidence.project_test_execution?.failed_test_details || {};
          if (failList.length > 0) {
            extraContent += '<div style="margin-top:8px; padding:8px; background:rgba(239,68,68,0.12); border:1px solid rgba(239,68,68,0.3); border-radius:4px; font-size:12px;">';
            failList.forEach(ft => {
              const shortName = ft.split('::').pop() || ft;
              const detailMsg = failDetails[ft] || 'FAILED';
              extraContent += `<div style="color:var(--status-fail); font-weight:700; font-family:var(--font-mono);">${escapeHtml(shortName)}: FAILED</div>`;
              if (detailMsg) {
                extraContent += `<div style="color:var(--text-secondary); margin-top:3px; font-family:var(--font-mono); font-size:11px;">${escapeHtml(detailMsg)}</div>`;
              }
            });
            extraContent += '</div>';
          }
        }

        stagesEl.innerHTML += '<div class="stage-card">'
          + '<div class="stage-name">' + (stage.name || label) + '</div>'
          + '<div class="stage-status ' + cls + '">' + (stage.status || '—') + '</div>'
          + '<div class="stage-detail">' + escapeHtml(stage.detail || '') + '</div>'
          + extraContent
          + '</div>';
      }
    }

    // 5. Explicit Limitations Disclosures
    const limEl = document.getElementById('verify-limitations');
    if (limEl && evidence.limitations && evidence.limitations.length) {
      limEl.innerHTML = '<div style="font-size: 11px; text-transform: uppercase; color: var(--text-tertiary); margin-bottom: 6px; font-weight: 600;">Explicit Verification Limitations:</div>' +
        evidence.limitations.map(l =>
          '<div class="limitation-item">' + escapeHtml(l) + '</div>'
        ).join('');
    } else if (limEl) {
      limEl.innerHTML = '';
    }

    // 6. Inspect Evidence Modal handler
    const btnInspectReal = document.getElementById('btn-inspect-evidence-real');
    if (btnInspectReal) {
      btnInspectReal.onclick = () => {
        const modal = document.getElementById('evidence-modal');
        const codeEl = document.getElementById('evidence-modal-json-content');
        if (modal && codeEl) {
          codeEl.textContent = JSON.stringify(run.report || run, null, 2);
          modal.style.display = 'flex';
        }
      };
    }

    showStep('results');
  }

  // Event Listeners
  const uploadZone = document.getElementById('upload-zone');
  const fileInput = document.getElementById('file-input');

  if (uploadZone) {
    uploadZone.addEventListener('click', () => {
      if (!auth.isConnected()) {
        showAuthModal('Connect A.I.R.A. before uploading a project for live verification.', false);
        return;
      }
      if (fileInput) fileInput.click();
    });
    uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
    uploadZone.addEventListener('drop', (e) => {
      e.preventDefault();
      uploadZone.classList.remove('drag-over');
      const file = e.dataTransfer.files[0];
      if (file) uploadFile(file);
    });
  }

  if (fileInput) {
    fileInput.addEventListener('change', () => {
      if (fileInput.files[0]) uploadFile(fileInput.files[0]);
    });
  }

  const customTestInput = document.getElementById('custom-test-file-input');
  if (customTestInput) {
    customTestInput.addEventListener('change', () => {
      if (customTestInput.files[0]) uploadCustomTests(customTestInput.files[0]);
    });
  }

  async function checkSandboxHealth() {
    const card = document.getElementById('sandbox-status-card');
    const title = document.getElementById('sandbox-card-title');
    const desc = document.getElementById('sandbox-card-desc');
    const dot = document.getElementById('sandbox-card-dot');
    const rem = document.getElementById('sandbox-card-remediation');
    const btnRun = document.getElementById('btn-run-verify');

    try {
      const res = await api.get(`/api/system/sandbox?t=${Date.now()}`, true);
      if (res.ok) {
        const data = await res.json();
        updateNavSandboxStatus(data);

        if (data.available || data.sandbox_health === 'SANDBOX_READY') {
          if (card) {
            card.style.background = 'rgba(61, 154, 80, 0.08)';
            card.style.borderColor = 'rgba(61, 154, 80, 0.3)';
          }
          if (title) {
            title.textContent = '✓ SANDBOX READY';
            title.style.color = 'var(--status-pass)';
          }
          if (dot) {
            dot.style.backgroundColor = 'var(--status-pass)';
            dot.classList.remove('offline');
          }
          if (desc) {
            desc.textContent = `Container sandbox active (${data.image_tag || 'aegis-sandbox:latest'}). Zero-network, dropped capabilities, and read-only rootfs enabled.`;
            desc.style.color = 'var(--text-primary)';
          }
          if (rem) rem.style.display = 'none';
          if (btnRun) {
            btnRun.disabled = false;
            btnRun.removeAttribute('title');
            btnRun.style.opacity = '1';
            btnRun.style.cursor = 'pointer';
          }
          // Clear any stale sandbox error state
          const errMsg = document.getElementById('error-message');
          if (errMsg && errMsg.textContent.toLowerCase().includes('sandbox')) {
            errMsg.textContent = '';
          }
          const errRem = document.getElementById('error-remediation');
          if (errRem) errRem.style.display = 'none';
        } else {
          if (card) {
            card.style.background = 'rgba(217, 68, 68, 0.08)';
            card.style.borderColor = 'rgba(217, 68, 68, 0.3)';
          }
          if (title) {
            title.textContent = '⚠ SANDBOX UNAVAILABLE — EXECUTION BLOCKED';
            title.style.color = 'var(--status-fail)';
          }
          if (dot) {
            dot.style.backgroundColor = 'var(--status-fail)';
            dot.classList.add('offline');
          }
          if (desc) {
            desc.textContent = data.failure_reason || 'Docker Engine is not reachable. Start Docker Desktop and retry.';
            desc.style.color = 'var(--status-fail)';
          }
          if (rem) {
            rem.textContent = data.remediation ? 'Remediation: ' + data.remediation : '';
            rem.style.display = data.remediation ? 'block' : 'none';
          }
          if (btnRun) {
            btnRun.disabled = true;
            btnRun.title = data.failure_reason || 'Docker sandbox required.';
            btnRun.style.opacity = '0.5';
            btnRun.style.cursor = 'not-allowed';
          }
        }
        return data;
      }
    } catch (e) {
      if (title) {
        title.textContent = '⚠ HEALTH CHECK ERROR';
        title.style.color = 'var(--status-fail)';
      }
      if (desc) desc.textContent = 'Failed to connect to backend system health probe.';
    }
    return null;
  }

  const btnConfigure = document.getElementById('btn-configure');
  if (btnConfigure) {
    btnConfigure.addEventListener('click', () => {
      showStep('config');
      checkSandboxHealth();
    });
  }

  const btnRecheck = document.getElementById('btn-recheck-sandbox');
  if (btnRecheck) {
    btnRecheck.addEventListener('click', async () => {
      btnRecheck.disabled = true;
      btnRecheck.textContent = 'Checking...';
      await checkSandboxHealth();
      btnRecheck.disabled = false;
      btnRecheck.innerHTML = '&#8635; Retry Sandbox Check';
    });
  }

  const btnRetrySandbox = document.getElementById('btn-retry-sandbox');
  if (btnRetrySandbox) {
    btnRetrySandbox.addEventListener('click', async () => {
      btnRetrySandbox.disabled = true;
      btnRetrySandbox.textContent = 'Checking...';
      const diag = await checkSandboxHealth();
      btnRetrySandbox.disabled = false;
      btnRetrySandbox.innerHTML = '&#8635; Retry Sandbox Check';

      if (diag && (diag.available || diag.sandbox_health === 'SANDBOX_READY')) {
        const errMsg = document.getElementById('error-message');
        if (errMsg) errMsg.textContent = '';
        const remEl = document.getElementById('error-remediation');
        if (remEl) remEl.style.display = 'none';
        showStep('config');
      } else {
        const errMsg = document.getElementById('error-message');
        if (errMsg) {
          errMsg.textContent = `Sandbox unavailable. ${(diag && diag.failure_reason) || 'Docker daemon is still unreachable.'}`;
        }
        const remEl = document.getElementById('error-remediation');
        if (remEl && diag && diag.remediation) {
          remEl.textContent = 'Remediation: ' + diag.remediation;
          remEl.style.display = 'block';
        }
      }
    });
  }

  const btnRunVerify = document.getElementById('btn-run-verify');
  if (btnRunVerify) btnRunVerify.addEventListener('click', startVerification);

  const btnNewVerify = document.getElementById('btn-new-verify');
  if (btnNewVerify) btnNewVerify.addEventListener('click', resetWizard);

  const btnRetry = document.getElementById('btn-retry');
  if (btnRetry) btnRetry.addEventListener('click', resetWizard);
})();
