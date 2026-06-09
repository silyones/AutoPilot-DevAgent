import { Fragment } from 'react';

export default function AgentTimeline({ trace }) {
  if (!trace || trace.length === 0) return null;

  return (
    <div className="overflow-x-auto pb-2">
      <div className="flex items-start gap-0 min-w-max">
        {trace.map((step, i) => (
          <Fragment key={i}>
            <div className="flex flex-col items-center w-36 shrink-0">
              <div className="w-3 h-3 rounded-full bg-pink mb-2" />
              <div className="text-xs font-semibold text-center">{step.agent}</div>
              <div className="text-xs text-muted text-center mt-1">{step.action}</div>
              <div className="text-xs text-muted/60 text-center mt-1 font-mono">
                {step.timestamp ? new Date(step.timestamp).toLocaleTimeString() : ''}
              </div>
            </div>
            {i < trace.length - 1 && (
              <div className="flex items-center self-start mt-[5px] px-2">
                <span className="text-pink text-xl font-bold leading-none drop-shadow-[0_0_4px_rgba(248,161,177,0.8)]">
                  →
                </span>
              </div>
            )}
          </Fragment>
        ))}
      </div>
    </div>
  );
}
