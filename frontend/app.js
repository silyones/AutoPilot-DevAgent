import React, { useState, useRef, useEffect, useCallback } from 'react';
import { createRoot } from 'react-dom/client';
import htm from 'htm';

const html = htm.bind(React.createElement);

/** Validate and resolve API base URL from the current page origin. */
function resolveApiBase() {
  try {
    const { origin, protocol, hostname } = window.location;
    if (protocol !== 'http:' && protocol !== 'https:') {
      throw new Error('Unsupported protocol');
    }
    if (!hostname) {
      throw new Error('Missing hostname');
    }
    return origin.replace(/\/$/, '');
  } catch (err) {
    console.warn('API base fallback:', err);
    return 'http://localhost:8000';
  }
}

function buildWsUrl(sessionId) {
  const base = new URL(resolveApiBase());
  const wsProtocol = base.protocol === 'https:' ? 'wss:' : 'ws:';
  const safeId = encodeURIComponent(String(sessionId));
  return `${wsProtocol}//${base.host}/api/ws/${safeId}`;
}

function validatePrUrl(raw) {
  const trimmed = String(raw || '').trim();
  if (!trimmed) return { ok: false, error: 'Please enter a GitHub PR URL.' };
  let parsed;
  try {
    parsed = new URL(trimmed);
  } catch {
    return { ok: false, error: 'Invalid URL format.' };
  }
  if (parsed.hostname !== 'github.com') {
    return { ok: false, error: 'URL must be a github.com pull request link.' };
  }
  if (!/^\/[^/]+\/[^/]+\/pull\/\d+\/?$/.test(parsed.pathname)) {
    return { ok: false, error: 'URL must be: https://github.com/owner/repo/pull/123' };
  }
  return { ok: true, url: parsed.href.replace(/\/$/, '') };
}

const API = resolveApiBase();

const PIPELINE_NODES = [
  { id: 'fetcher', label: 'GitHub Fetcher', agents: ['GitHub Fetcher'] },
  { id: 'reviewer', label: 'Reviewer Agent', agents: ['Reviewer Agent'] },
  { id: 'fixer', label: 'Fixer Agent', agents: ['Fixer Agent'] },
  { id: 'tester', label: 'Tester Agent', agents: ['Tester Agent'] },
  { id: 'documenter', label: 'Documenter Agent', agents: ['Documenter Agent'] },
  { id: 'final', label: 'Final Report', agents: [] },
];

const AGENT_TO_NODE = {};
PIPELINE_NODES.forEach((n) => {
  n.agents.forEach((a) => { AGENT_TO_NODE[a] = n.id; });
});

const NODE_ORDER = PIPELINE_NODES.map((n) => n.id);

const STATUS_STYLES = {
  WAITING: 'border-dashed border-muted/30 bg-bg/60 text-muted rounded-3xl',
  RUNNING: 'border-pink bg-pink/20 text-pink node-running rounded-3xl',
  DONE: 'border-success bg-success/15 text-success rounded-3xl',
  FAILED: 'border-danger bg-danger/20 text-danger rounded-3xl',
};

const SEVERITY_COLORS = {
  critical: 'text-[#FFD4DC] bg-danger/40',
  high: 'text-warn bg-warn/25',
  medium: 'text-pink bg-pink/20',
  low: 'text-muted bg-forest/50',
};

const CARD_CLASS = 'bg-surface2/80 border border-pink/25 rounded-3xl p-4';
const PANEL_CLASS = 'bg-surface/90 border border-pink/30 rounded-[2rem] p-6 shadow-lg backdrop-blur-sm';

function mapAgentToNode(agent) {
  if (!agent) return null;
  if (AGENT_TO_NODE[agent]) return AGENT_TO_NODE[agent];
  for (const [name, id] of Object.entries(AGENT_TO_NODE)) {
    if (agent.includes(name.split(' ')[0])) return id;
  }
  return null;
}

function initialNodeStates() {
  const s = {};
  PIPELINE_NODES.forEach((n) => { s[n.id] = 'WAITING'; });
  return s;
}

function statusBadgeClass(status) {
  const m = {
    'IN PROGRESS': 'bg-pink/25 text-pink border-pink/60',
    PASSED: 'bg-success/20 text-success border-success/50',
    FIXED: 'bg-pink/30 text-[#FFF5F7] border-pink/70',
    NEEDS_HUMAN_REVIEW: 'bg-danger/25 text-[#FFD4DC] border-danger/50',
    ERROR: 'bg-danger/25 text-[#FFD4DC] border-danger/50',
  };
  return m[status] || 'bg-forest/60 text-muted border-pink/30';
}

function formatStatus(s) {
  if (s === 'NEEDS_HUMAN_REVIEW') return 'NEEDS HUMAN REVIEW';
  return s || 'IDLE';
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, message: '' };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: error?.message || 'Unknown error' };
  }

  componentDidCatch(error, info) {
    console.error('UI render error:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return html`
        <div class="max-w-lg mx-auto mt-16 p-6 rounded-2xl border border-danger/40 bg-danger/10 text-[#FFD4DC]">
          <h2 class="font-bold mb-2">UI Error</h2>
          <p class="text-sm">${this.state.message}</p>
        </div>
      `;
    }
    return this.props.children;
  }
}

function PipelineNode({ label, state }) {
  const cls = STATUS_STYLES[state] || STATUS_STYLES.WAITING;
  return html`
    <div class="border-2 px-5 py-3.5 text-center text-sm font-semibold transition-all duration-300 ${cls}">
      ${state === 'DONE' ? html`<span class="mr-1">✓</span>` : null}
      ${state === 'FAILED' ? html`<span class="mr-1">✗</span>` : null}
      ${label}
    </div>
  `;
}

function PipelineDiagram({ nodeStates, retryActive }) {
  return html`
    <div class="flex flex-col items-center w-full max-w-xs mx-auto">
      ${PIPELINE_NODES.map((node, i) => html`
        <${React.Fragment} key=${node.id}>
          <${PipelineNode} label=${node.label} state=${nodeStates[node.id]} />
          ${node.id === 'fixer' && i < PIPELINE_NODES.length - 1 ? html`
            <div class="relative w-full flex justify-center my-1">
              <div class="arrow-down"></div>
              ${retryActive ? html`
                <div class="absolute right-0 top-1/2 -translate-y-1/2 text-xs text-warn border border-warn/50 rounded-full px-3 py-1 whitespace-nowrap bg-warn/10">
                  ↺ retry loop
                </div>
              ` : null}
            </div>
          ` : null}
          ${node.id === 'tester' ? html`
            <div class="relative w-full">
              <div class="arrow-down"></div>
              ${retryActive ? html`
                <svg class="absolute -right-16 top-0 h-16 w-16 text-warn/60" viewBox="0 0 64 64" fill="none">
                  <path d="M8 32 C8 8, 56 8, 56 32" stroke="currentColor" stroke-width="2" stroke-dasharray="4 3" marker-end="url(#arrow)" />
                  <defs><marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="currentColor" /></marker></defs>
                </svg>
              ` : null}
            </div>
          ` : null}
          ${node.id !== 'fixer' && node.id !== 'tester' && i < PIPELINE_NODES.length - 1 ? html`<div class="arrow-down"></div>` : null}
        </${React.Fragment}>
      `)}
    </div>
  `;
}

function SummaryCards({ report }) {
  const review = report.review || {};
  const findings = review.findings || [];
  const severity = { critical: 0, high: 0, medium: 0, low: 0 };
  findings.forEach((f) => {
    const s = (f.severity || 'low').toLowerCase();
    if (severity[s] !== undefined) severity[s]++;
  });
  const patches = report.patches || [];
  const tests = report.test_results || {};

  return html`
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="${CARD_CLASS}">
        <div class="text-muted text-xs uppercase tracking-wide mb-1">Total Issues</div>
        <div class="text-2xl font-bold">${review.total_issues ?? findings.length}</div>
        <div class="text-xs text-muted mt-2 space-x-2">
          <span class="text-danger">C:${severity.critical}</span>
          <span class="text-warn">H:${severity.high}</span>
          <span class="text-pink">M:${severity.medium}</span>
          <span class="text-muted">L:${severity.low}</span>
        </div>
      </div>
      <div class="${CARD_CLASS}">
        <div class="text-muted text-xs uppercase tracking-wide mb-1">Patches Generated</div>
        <div class="text-2xl font-bold text-pink">${patches.length}</div>
      </div>
      <div class="${CARD_CLASS}">
        <div class="text-muted text-xs uppercase tracking-wide mb-1">Tests</div>
        <div class="text-2xl font-bold">
          <span class="text-success">${tests.passed ?? 0}</span>
          <span class="text-muted text-lg"> / </span>
          <span class="text-danger">${tests.failed ?? 0}</span>
        </div>
        <div class="text-xs text-muted mt-1">passed / failed</div>
      </div>
      <div class="${CARD_CLASS}">
        <div class="text-muted text-xs uppercase tracking-wide mb-1">Duration</div>
        <div class="text-2xl font-bold text-pink">${(report.total_duration_seconds || 0).toFixed(2)}s</div>
      </div>
    </div>
  `;
}

function FindingsTable({ findings }) {
  if (!findings || findings.length === 0) {
    return html`<p class="text-muted text-sm">No findings reported.</p>`;
  }
  return html`
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-pink/20 text-muted text-left">
            <th class="py-2 pr-3">Severity</th>
            <th class="py-2 pr-3">File</th>
            <th class="py-2 pr-3">Line</th>
            <th class="py-2 pr-3">Category</th>
            <th class="py-2">Description</th>
          </tr>
        </thead>
        <tbody>
          ${findings.map((f, i) => {
            const sev = (f.severity || 'low').toLowerCase();
            const sevCls = SEVERITY_COLORS[sev] || SEVERITY_COLORS.low;
            return html`
              <tr key=${i} class="border-b border-pink/15">
                <td class="py-2 pr-3"><span class="px-2 py-0.5 rounded-full text-xs font-semibold uppercase ${sevCls}">${f.severity}</span></td>
                <td class="py-2 pr-3 font-mono text-xs text-pink">${f.file}</td>
                <td class="py-2 pr-3 text-muted">${f.line}</td>
                <td class="py-2 pr-3 text-muted">${f.category}</td>
                <td class="py-2">${f.description}</td>
              </tr>
            `;
          })}
        </tbody>
      </table>
    </div>
  `;
}

function PatchesSection({ patches }) {
  if (!patches || patches.length === 0) {
    return html`<p class="text-muted text-sm">No patches generated.</p>`;
  }
  return html`
    <div class="space-y-6">
      ${patches.map((p, i) => html`
        <div key=${i} class="${CARD_CLASS}">
          <div class="font-mono text-sm text-pink mb-3">${p.file}</div>
          <div class="grid md:grid-cols-2 gap-3 mb-3">
            <div>
              <div class="text-xs text-muted mb-1 uppercase">Original</div>
              <pre class="bg-danger/15 border border-danger/30 rounded-2xl p-3 text-xs overflow-x-auto whitespace-pre-wrap">${p.original}</pre>
            </div>
            <div>
              <div class="text-xs text-muted mb-1 uppercase">Fixed</div>
              <pre class="bg-success/10 border border-success/30 rounded-2xl p-3 text-xs overflow-x-auto whitespace-pre-wrap">${p.fixed}</pre>
            </div>
          </div>
          ${p.explanation ? html`<p class="text-sm text-muted">${p.explanation}</p>` : null}
        </div>
      `)}
    </div>
  `;
}

function DocumentationSection({ doc }) {
  if (!doc?.summary) return html`<p class="text-muted text-sm">No documentation generated.</p>`;
  return html`
    <div>
      <p class="text-sm leading-relaxed">${doc.summary}</p>
    </div>
  `;
}

function AgentTimeline({ trace }) {
  if (!trace || trace.length === 0) return null;
  return html`
    <div class="overflow-x-auto pb-2">
      <div class="flex items-start gap-0 min-w-max">
        ${trace.map((step, i) => html`
          <${React.Fragment} key=${i}>
            <div class="flex flex-col items-center w-36 shrink-0">
              <div class="w-3 h-3 rounded-full bg-pink mb-2"></div>
              <div class="text-xs font-semibold text-center">${step.agent}</div>
              <div class="text-xs text-muted text-center mt-1">${step.action}</div>
              <div class="text-xs text-muted/60 text-center mt-1 font-mono">
                ${step.timestamp ? new Date(step.timestamp).toLocaleTimeString() : ''}
              </div>
            </div>
            ${i < trace.length - 1 ? html`
              <div class="flex items-center self-start mt-[5px] px-2">
                <span class="text-pink text-xl font-bold leading-none drop-shadow-[0_0_4px_rgba(248,161,177,0.8)]">→</span>
              </div>
            ` : null}
          </${React.Fragment}>
        `)}
      </div>
    </div>
  `;
}

function ReportPanel({ report }) {
  if (!report) return null;
  return html`
    <div id="report-print" class="space-y-8 mt-8">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-bold">DevReport</h2>
        <button
          onClick=${() => { try { window.print(); } catch (e) { console.error(e); } }}
          class="no-print bg-pink hover:bg-accenthover text-bg font-semibold px-5 py-2.5 rounded-full text-sm transition shadow-md"
        >
          Download Report as PDF
        </button>
      </div>
      <p class="text-sm text-muted font-mono">${report.pr_url}</p>
      <section>
        <h3 class="text-sm font-semibold text-muted uppercase tracking-wide mb-3">Summary</h3>
        <${SummaryCards} report=${report} />
      </section>
      <section>
        <h3 class="text-sm font-semibold text-muted uppercase tracking-wide mb-3">Findings</h3>
        <${FindingsTable} findings=${(report.review || {}).findings} />
      </section>
      <section>
        <h3 class="text-sm font-semibold text-muted uppercase tracking-wide mb-3">Patches Applied</h3>
        <${PatchesSection} patches=${report.patches} />
      </section>
      <section>
        <h3 class="text-sm font-semibold text-muted uppercase tracking-wide mb-3">Documentation</h3>
        <${DocumentationSection} doc=${report.documentation} />
      </section>
      <section>
        <h3 class="text-sm font-semibold text-muted uppercase tracking-wide mb-3">Agent Trace Timeline</h3>
        <${AgentTimeline} trace=${report.agent_trace} />
      </section>
    </div>
  `;
}

function App() {
  const [prUrl, setPrUrl] = useState('');
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState('IDLE');
  const [duration, setDuration] = useState('');
  const [error, setError] = useState('');
  const [nodeStates, setNodeStates] = useState(initialNodeStates);
  const [recentLog, setRecentLog] = useState([]);
  const [report, setReport] = useState(null);
  const [retryActive, setRetryActive] = useState(false);

  const wsRef = useRef(null);
  const timerRef = useRef(null);
  const startTsRef = useRef(null);
  const currentNodeRef = useRef(null);

  const addLog = useCallback((agent, message) => {
    setRecentLog((prev) => {
      const entry = { agent: agent || 'System', message, ts: new Date().toLocaleTimeString() };
      return [...prev.slice(-4), entry];
    });
  }, []);

  const setNode = useCallback((nodeId, state) => {
    if (!nodeId) return;
    setNodeStates((prev) => ({ ...prev, [nodeId]: state }));
  }, []);

  const markPreviousDone = useCallback((activeNodeId) => {
    const idx = NODE_ORDER.indexOf(activeNodeId);
    if (idx <= 0) return;
    setNodeStates((prev) => {
      const next = { ...prev };
      for (let i = 0; i < idx; i++) {
        const id = NODE_ORDER[i];
        if (next[id] === 'RUNNING' || next[id] === 'DONE') next[id] = 'DONE';
      }
      return next;
    });
  }, []);

  const handleAgentProgress = useCallback((agent, message, action) => {
    const nodeId = mapAgentToNode(agent);
    if (!nodeId) return;

    if (action && action.includes('fix_bugs_attempt') && (action.includes('2') || action.includes('3'))) {
      setRetryActive(true);
      setNode('fixer', 'RUNNING');
      setNode('tester', 'WAITING');
    }

    if (action && action.includes('run_tests') && message && message.toLowerCase().includes('fail')) {
      setRetryActive(true);
      setNode('tester', 'FAILED');
      setTimeout(() => setNode('fixer', 'RUNNING'), 400);
    }

    markPreviousDone(nodeId);
    setNode(nodeId, 'RUNNING');
    currentNodeRef.current = nodeId;
    addLog(agent, message);
  }, [setNode, markPreviousDone, addLog]);

  const reset = useCallback(() => {
    setNodeStates(initialNodeStates());
    setRecentLog([]);
    setReport(null);
    setError('');
    setRetryActive(false);
    setDuration('');
    currentNodeRef.current = null;
    try {
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    } catch (e) { console.warn('WebSocket close failed:', e); }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  }, []);

  const startTimer = () => {
    startTsRef.current = Date.now();
    timerRef.current = setInterval(() => {
      setDuration(((Date.now() - startTsRef.current) / 1000).toFixed(1) + 's');
    }, 100);
  };

  const stopTimer = () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };

  const startReview = async () => {
    const validation = validatePrUrl(prUrl);
    if (!validation.ok) {
      setError(validation.error);
      return;
    }

    reset();
    setRunning(true);
    setStatus('IN PROGRESS');
    startTimer();

    let sessionId;
    try {
      const resp = await fetch(`${API}/api/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pr_url: validation.url }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      if (!data.success) throw new Error(data.error || 'Server error');
      sessionId = data.session_id;
    } catch (e) {
      setError('Failed to start: ' + (e?.message || 'Unknown error'));
      setStatus('ERROR');
      setRunning(false);
      stopTimer();
      return;
    }

    addLog('AutoPilot', 'Pipeline started — session ' + sessionId.slice(0, 8) + '…');
    setNode('fetcher', 'RUNNING');
    currentNodeRef.current = 'fetcher';

    let ws;
    try {
      ws = new WebSocket(buildWsUrl(sessionId));
    } catch (e) {
      setError('WebSocket failed: ' + (e?.message || 'Unknown error'));
      setStatus('ERROR');
      setRunning(false);
      stopTimer();
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => addLog('WebSocket', 'Connected — waiting for updates…');

    ws.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch (e) {
        console.warn('Invalid WebSocket message:', e);
        return;
      }

      if (msg.type === 'start') {
        setNode('fetcher', 'RUNNING');
        addLog('System', msg.message || 'Pipeline running…');
      } else if (msg.type === 'progress') {
        handleAgentProgress(msg.agent, msg.message || msg.action, msg.action);
      } else if (msg.type === 'complete') {
        stopTimer();
        const r = msg.report || {};
        setReport(r);
        const st = r.status || 'PASSED';
        setStatus(st);
        setDuration((r.total_duration_seconds || 0).toFixed(2) + 's');
        const finalStates = {};
        PIPELINE_NODES.forEach((n) => { finalStates[n.id] = 'DONE'; });
        setNodeStates(finalStates);
        setRetryActive(false);
        addLog('AutoPilot', 'Pipeline complete — ' + st);
        setRunning(false);
        try { ws.close(); } catch (e) { console.warn(e); }
      } else if (msg.type === 'error') {
        stopTimer();
        setStatus('ERROR');
        setError(msg.message || 'Pipeline error');
        if (currentNodeRef.current) setNode(currentNodeRef.current, 'FAILED');
        addLog('Error', msg.message);
        setRunning(false);
        try { ws.close(); } catch (e) { console.warn(e); }
      }
    };

    ws.onerror = () => addLog('WebSocket', 'Connection error');
  };

  useEffect(() => () => {
    try { if (wsRef.current) wsRef.current.close(); } catch (e) { console.warn(e); }
    if (timerRef.current) clearInterval(timerRef.current);
  }, []);

  return html`
    <div class="max-w-7xl mx-auto px-4 py-8">
      <div class="flex flex-col lg:flex-row gap-6">
        <div class="lg:w-[40%] shrink-0">
          <div class="${PANEL_CLASS}">
            <h1 class="text-2xl font-bold bg-gradient-to-r from-pink to-[#FFD4DC] bg-clip-text text-transparent mb-1">
              AutoPilot Dev
            </h1>
            <p class="text-muted text-sm mb-6">Autonomous GitHub PR Review &amp; Bug Fix</p>
            <label class="text-xs uppercase text-muted tracking-wide">GitHub Pull Request</label>
            <input
              type="url"
              value=${prUrl}
              onChange=${(e) => setPrUrl(e.target.value)}
              onKeyDown=${(e) => e.key === 'Enter' && !running && startReview()}
              placeholder="https://github.com/owner/repo/pull/123"
              disabled=${running}
              class="w-full mt-2 mb-4 bg-white border border-pink/30 rounded-full px-5 py-2.5 text-sm text-black placeholder:text-gray-500 focus:outline-none focus:border-pink focus:ring-2 focus:ring-pink/30 disabled:opacity-50"
            />
            <button
              onClick=${startReview}
              disabled=${running}
              class="w-full bg-pink hover:bg-accenthover disabled:opacity-40 text-bg font-bold py-3 rounded-full text-sm transition shadow-md no-print"
            >
              ${running ? ' Running…' : 'Analyse'}
            </button>
            ${error ? html`
              <div class="mt-3 text-[#FFD4DC] text-sm bg-danger/20 border border-danger/40 rounded-2xl px-4 py-2">
                ${error}
              </div>
            ` : null}
            <div class="flex items-center gap-3 mt-5">
              <span class="text-muted text-sm">Status</span>
              <span class="px-4 py-1 rounded-full text-xs font-bold uppercase border ${statusBadgeClass(status)}">
                ${formatStatus(status)}
              </span>
              ${duration ? html`<span class="text-muted text-sm ml-auto font-mono">${duration}</span>` : null}
            </div>
          </div>
        </div>
        <div class="lg:w-[60%]">
          <div class="${PANEL_CLASS} h-full">
            <h2 class="text-xs uppercase text-pink tracking-wide mb-4">Live Pipeline</h2>
            <${PipelineDiagram} nodeStates=${nodeStates} retryActive=${retryActive} />
            <div class="mt-6 border-t border-pink/20 pt-4">
              <h3 class="text-xs uppercase text-muted tracking-wide mb-2">Recent Activity</h3>
              ${recentLog.length === 0 ? html`
                <p class="text-muted text-sm">Waiting for pipeline events…</p>
              ` : html`
                <ul class="space-y-1.5">
                  ${recentLog.map((entry, i) => html`
                    <li key=${i} class="text-xs font-mono">
                      <span class="text-muted">${entry.ts}</span>
                      <span class="text-pink ml-2">${entry.agent}</span>
                      <span class="text-muted ml-2">${entry.message}</span>
                    </li>
                  `)}
                </ul>
              `}
            </div>
          </div>
        </div>
      </div>
      ${report ? html`<${ReportPanel} report=${report} />` : null}
    </div>
  `;
}

function bootstrap() {
  const rootEl = document.getElementById('root');
  if (!rootEl) {
    console.error('Root element #root not found');
    return;
  }
  try {
    const root = createRoot(rootEl);
    root.render(html`<${ErrorBoundary}><${App} /></${ErrorBoundary}>`);
  } catch (err) {
    console.error('Failed to mount React app:', err);
    rootEl.textContent = 'Failed to load the UI. Please refresh the page.';
  }
}

bootstrap();
