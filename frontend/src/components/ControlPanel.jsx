import { PANEL_CLASS, statusBadgeClass, formatStatus } from '../constants/pipeline';

export default function ControlPanel({
  prUrl,
  setPrUrl,
  running,
  startReview,
  error,
  status,
  duration,
}) {
  return (
    <div className={PANEL_CLASS}>
      <h1 className="text-2xl font-bold bg-gradient-to-r from-pink to-[#FFD4DC] bg-clip-text text-transparent mb-1">
        AutoPilot Dev
      </h1>
      <p className="text-muted text-sm mb-6">Autonomous GitHub PR Review &amp; Bug Fix</p>

      <label className="text-xs uppercase text-muted tracking-wide">GitHub Pull Request</label>
      <input
        type="url"
        value={prUrl}
        onChange={(e) => setPrUrl(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && !running && startReview()}
        placeholder="https://github.com/owner/repo/pull/123"
        disabled={running}
        className="w-full mt-2 mb-4 bg-white border border-pink/30 rounded-full px-5 py-2.5 text-sm text-black placeholder:text-gray-500 focus:outline-none focus:border-pink focus:ring-2 focus:ring-pink/30 disabled:opacity-50"
      />

      <button
        type="button"
        onClick={startReview}
        disabled={running}
        className="w-full bg-pink hover:bg-accenthover disabled:opacity-40 text-bg font-bold py-3 rounded-full text-sm transition shadow-md no-print"
      >
        {running ? ' Running…' : 'Analyse'}
      </button>

      {error && (
        <div className="mt-3 text-[#FFD4DC] text-sm bg-danger/20 border border-danger/40 rounded-2xl px-4 py-2">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3 mt-5">
        <span className="text-muted text-sm">Status</span>
        <span className={`px-4 py-1 rounded-full text-xs font-bold uppercase border ${statusBadgeClass(status)}`}>
          {formatStatus(status)}
        </span>
        {duration && <span className="text-muted text-sm ml-auto font-mono">{duration}</span>}
      </div>
    </div>
  );
}
