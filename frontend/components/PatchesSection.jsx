import { CARD_CLASS } from '../lib/pipeline';

export default function PatchesSection({ patches }) {
  if (!patches || patches.length === 0) {
    return <p className="text-muted text-sm">No patches generated.</p>;
  }

  return (
    <div className="space-y-6">
      {patches.map((p, i) => (
        <div key={i} className={CARD_CLASS}>
          <div className="font-mono text-sm text-pink mb-4">{p.file}</div>
          <div className="grid md:grid-cols-2 gap-5 mb-4">
            <div>
              <div className="text-xs text-muted mb-2 uppercase">Original</div>
              <pre className="bg-danger/15 border border-danger/30 rounded-2xl px-4 py-4 text-xs overflow-x-auto whitespace-pre-wrap leading-relaxed">
                {p.original}
              </pre>
            </div>
            <div>
              <div className="text-xs text-muted mb-2 uppercase">Fixed</div>
              <pre className="bg-success/10 border border-success/30 rounded-2xl px-4 py-4 text-xs overflow-x-auto whitespace-pre-wrap leading-relaxed">
                {p.fixed}
              </pre>
            </div>
          </div>
          {p.explanation && <p className="text-sm text-muted leading-relaxed">{p.explanation}</p>}
        </div>
      ))}
    </div>
  );
}
