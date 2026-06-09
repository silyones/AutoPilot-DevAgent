import { STATUS_STYLES } from '../constants/pipeline';

export default function PipelineNode({ label, state }) {
  const cls = STATUS_STYLES[state] || STATUS_STYLES.WAITING;
  return (
    <div className={`border-2 px-5 py-3.5 text-center text-sm font-semibold transition-all duration-300 ${cls}`}>
      {state === 'DONE' && <span className="mr-1">✓</span>}
      {state === 'FAILED' && <span className="mr-1">✗</span>}
      {label}
    </div>
  );
}
