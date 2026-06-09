import { Fragment } from 'react';
import { PIPELINE_NODES } from '../constants/pipeline';
import PipelineNode from './PipelineNode';

export default function PipelineDiagram({ nodeStates, retryActive }) {
  return (
    <div className="flex flex-col items-center w-full max-w-xs mx-auto">
      {PIPELINE_NODES.map((node, i) => (
        <Fragment key={node.id}>
          <PipelineNode label={node.label} state={nodeStates[node.id]} />
          {node.id === 'fixer' && i < PIPELINE_NODES.length - 1 && (
            <div className="relative w-full flex justify-center my-1">
              <div className="arrow-down" />
              {retryActive && (
                <div className="absolute right-0 top-1/2 -translate-y-1/2 text-xs text-warn border border-warn/50 rounded-full px-3 py-1 whitespace-nowrap bg-warn/10">
                  ↺ retry loop
                </div>
              )}
            </div>
          )}
          {node.id === 'tester' && (
            <div className="relative w-full">
              <div className="arrow-down" />
              {retryActive && (
                <svg className="absolute -right-16 top-0 h-16 w-16 text-warn/60" viewBox="0 0 64 64" fill="none">
                  <path
                    d="M8 32 C8 8, 56 8, 56 32"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeDasharray="4 3"
                    markerEnd="url(#arrow)"
                  />
                  <defs>
                    <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                      <path d="M0,0 L6,3 L0,6 Z" fill="currentColor" />
                    </marker>
                  </defs>
                </svg>
              )}
            </div>
          )}
          {node.id !== 'fixer' && node.id !== 'tester' && i < PIPELINE_NODES.length - 1 && (
            <div className="arrow-down" />
          )}
        </Fragment>
      ))}
    </div>
  );
}
