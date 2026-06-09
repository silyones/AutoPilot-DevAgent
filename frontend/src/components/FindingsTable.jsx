import { SEVERITY_COLORS } from '../constants/pipeline';

export default function FindingsTable({ findings }) {
  if (!findings || findings.length === 0) {
    return <p className="text-muted text-sm">No findings reported.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-pink/20 text-muted text-left">
            <th className="py-2 pr-3">Severity</th>
            <th className="py-2 pr-3">File</th>
            <th className="py-2 pr-3">Line</th>
            <th className="py-2 pr-3">Category</th>
            <th className="py-2">Description</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((f, i) => {
            const sev = (f.severity || 'low').toLowerCase();
            const sevCls = SEVERITY_COLORS[sev] || SEVERITY_COLORS.low;
            return (
              <tr key={i} className="border-b border-pink/15">
                <td className="py-2 pr-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-semibold uppercase ${sevCls}`}>
                    {f.severity}
                  </span>
                </td>
                <td className="py-2 pr-3 font-mono text-xs text-pink">{f.file}</td>
                <td className="py-2 pr-3 text-muted">{f.line}</td>
                <td className="py-2 pr-3 text-muted">{f.category}</td>
                <td className="py-2">{f.description}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
