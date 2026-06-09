import { CARD_CLASS, SEVERITY_COLORS } from '../lib/pipeline';

export default function FindingsTable({ findings }) {
  if (!findings || findings.length === 0) {
    return <p className="text-muted text-sm">No findings reported.</p>;
  }

  return (
    <div className={`${CARD_CLASS} overflow-x-auto !min-h-0`}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-pink/20 text-muted text-left">
            <th className="py-3 pr-5">Severity</th>
            <th className="py-3 pr-5">File</th>
            <th className="py-3 pr-5">Line</th>
            <th className="py-3 pr-5">Category</th>
            <th className="py-3">Description</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((f, i) => {
            const sev = (f.severity || 'low').toLowerCase();
            const sevCls = SEVERITY_COLORS[sev] || SEVERITY_COLORS.low;
            return (
              <tr key={i} className="border-b border-pink/15">
                <td className="py-3 pr-5 align-top">
                  <span className={`px-2.5 py-1 rounded-full text-xs font-semibold uppercase ${sevCls}`}>
                    {f.severity}
                  </span>
                </td>
                <td className="py-3 pr-5 font-mono text-xs text-pink align-top">{f.file}</td>
                <td className="py-3 pr-5 text-muted align-top">{f.line}</td>
                <td className="py-3 pr-5 text-muted align-top">{f.category}</td>
                <td className="py-3 leading-relaxed align-top">{f.description}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
