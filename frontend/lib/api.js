export function resolveApiBase() {
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

export function buildWsUrl(sessionId) {
  const base = new URL(resolveApiBase());
  const wsProtocol = base.protocol === 'https:' ? 'wss:' : 'ws:';
  const safeId = encodeURIComponent(String(sessionId));
  return `${wsProtocol}//${base.host}/api/ws/${safeId}`;
}

export function validatePrUrl(raw) {
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

