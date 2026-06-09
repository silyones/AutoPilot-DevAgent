export const PIPELINE_NODES = [
  { id: 'fetcher', label: 'GitHub Fetcher', agents: ['GitHub Fetcher'] },
  { id: 'reviewer', label: 'Reviewer Agent', agents: ['Reviewer Agent'] },
  { id: 'fixer', label: 'Fixer Agent', agents: ['Fixer Agent'] },
  { id: 'tester', label: 'Tester Agent', agents: ['Tester Agent'] },
  { id: 'documenter', label: 'Documenter Agent', agents: ['Documenter Agent'] },
  { id: 'final', label: 'Final Report', agents: [] },
];

export const AGENT_TO_NODE = {};
PIPELINE_NODES.forEach((n) => {
  n.agents.forEach((a) => {
    AGENT_TO_NODE[a] = n.id;
  });
});

export const NODE_ORDER = PIPELINE_NODES.map((n) => n.id);

export const STATUS_STYLES = {
  WAITING: 'border-muted/40 bg-surface2/40 text-muted rounded-3xl',
  RUNNING: 'border-pink bg-pink/20 text-pink node-running rounded-3xl',
  DONE: 'border-success bg-success/15 text-success rounded-3xl',
  FAILED: 'border-danger bg-danger/20 text-danger rounded-3xl',
};

export const SEVERITY_COLORS = {
  critical: 'text-[#FFD4DC] bg-danger/40',
  high: 'text-warn bg-warn/25',
  medium: 'text-pink bg-pink/20',
  low: 'text-muted bg-forest/50',
};

export const CARD_CLASS =
  'bg-surface2/80 border border-pink/25 rounded-3xl px-6 py-5 min-h-[7.5rem]';
export const PANEL_CLASS =
  'bg-surface/90 border border-pink/30 rounded-3xl px-8 py-7 shadow-lg backdrop-blur-sm';

export function mapAgentToNode(agent) {
  if (!agent) return null;
  if (AGENT_TO_NODE[agent]) return AGENT_TO_NODE[agent];
  for (const [name, id] of Object.entries(AGENT_TO_NODE)) {
    if (agent.includes(name.split(' ')[0])) return id;
  }
  return null;
}

export function initialNodeStates() {
  const s = {};
  PIPELINE_NODES.forEach((n) => {
    s[n.id] = 'WAITING';
  });
  return s;
}

export function statusBadgeClass(status) {
  const m = {
    'IN PROGRESS': 'bg-pink/25 text-pink border-pink/60',
    PASSED: 'bg-success/20 text-success border-success/50',
    FIXED: 'bg-pink/30 text-[#FFF5F7] border-pink/70',
    NEEDS_HUMAN_REVIEW: 'bg-danger/25 text-[#FFD4DC] border-danger/50',
    ERROR: 'bg-danger/25 text-[#FFD4DC] border-danger/50',
  };
  return m[status] || 'bg-forest/60 text-muted border-pink/30';
}

export function formatStatus(s) {
  if (s === 'NEEDS_HUMAN_REVIEW') return 'NEEDS HUMAN REVIEW';
  return s || 'IDLE';
}
