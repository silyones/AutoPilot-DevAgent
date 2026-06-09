export default function RecentActivity({ recentLog }) {
  return (
    <div className="mt-6 border-t border-pink/20 pt-4">
      <h3 className="text-xs uppercase text-muted tracking-wide mb-2">Recent Activity</h3>
      {recentLog.length === 0 ? (
        <p className="text-muted text-sm">Waiting for pipeline events…</p>
      ) : (
        <ul className="space-y-1.5">
          {recentLog.map((entry, i) => (
            <li key={i} className="text-xs font-mono">
              <span className="text-muted">{entry.ts}</span>
              <span className="text-pink ml-2">{entry.agent}</span>
              <span className="text-muted ml-2">{entry.message}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
