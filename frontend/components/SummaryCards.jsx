import { CARD_CLASS } from '../lib/pipeline';

export default function SummaryCards({ report }) {
  const review = report.review || {};
  const findings = review.findings || [];
  const severity = { critical: 0, high: 0, medium: 0, low: 0 };
  findings.forEach((f) => {
    const s = (f.severity || 'low').toLowerCase();
    if (severity[s] !== undefined) severity[s]++;
  });
  const patches = report.patches || [];
  const tests = report.test_results || {};

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
      <div className={CARD_CLASS}>
        <div className="text-muted text-xs uppercase tracking-wide mb-1">Total Issues</div>
        <div className="text-2xl font-bold">{review.total_issues ?? findings.length}</div>
        <div className="text-xs text-muted mt-3 space-x-2">
          <span className="text-danger">C:{severity.critical}</span>
          <span className="text-warn">H:{severity.high}</span>
          <span className="text-pink">M:{severity.medium}</span>
          <span className="text-muted">L:{severity.low}</span>
        </div>
      </div>
      <div className={CARD_CLASS}>
        <div className="text-muted text-xs uppercase tracking-wide mb-1">Patches Generated</div>
        <div className="text-2xl font-bold text-pink">{patches.length}</div>
      </div>
      <div className={CARD_CLASS}>
        <div className="text-muted text-xs uppercase tracking-wide mb-1">Tests</div>
        <div className="text-2xl font-bold">
          <span className="text-success">{tests.passed ?? 0}</span>
          <span className="text-muted text-lg"> / </span>
          <span className="text-danger">{tests.failed ?? 0}</span>
        </div>
        <div className="text-xs text-muted mt-3">passed / failed</div>
      </div>
      <div className={CARD_CLASS}>
        <div className="text-muted text-xs uppercase tracking-wide mb-1">Duration</div>
        <div className="text-2xl font-bold text-pink">{(report.total_duration_seconds || 0).toFixed(2)}s</div>
      </div>
    </div>
  );
}
