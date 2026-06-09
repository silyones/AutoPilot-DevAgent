import { STATUS_STYLES } from '../lib/pipeline';

export default function PipelineNode({ label, state }) {
  const cls = STATUS_STYLES[state] || STATUS_STYLES.WAITING;
  return (
    <div className={`w-full border-2 px-6 py-4 text-center text-sm font-semibold transition-all duration-300 ${cls}`}>
      {state === 'DONE' && <span className="mr-1">✓</span>}
      {state === 'FAILED' && <span className="mr-1">✗</span>}
      {label}
    </div>
  );
}
