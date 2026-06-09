import SummaryCards from './SummaryCards';
import FindingsTable from './FindingsTable';
import PatchesSection from './PatchesSection';
import DocumentationSection from './DocumentationSection';
import AgentTimeline from './AgentTimeline';

export default function ReportPanel({ report }) {
  if (!report) return null;

  return (
    <div id="report-print" className="space-y-10 mt-10">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">DevReport</h2>
        <button
          type="button"
          onClick={() => {
            try {
              window.print();
            } catch (e) {
              console.error(e);
            }
          }}
          className="no-print bg-pink hover:bg-accenthover text-bg font-semibold px-5 py-2.5 rounded-full text-sm transition shadow-md"
        >
          Download Report as PDF
        </button>
      </div>
      <p className="text-sm text-muted font-mono">{report.pr_url}</p>

      <section>
        <h3 className="text-sm font-semibold text-muted uppercase tracking-wide mb-3">Summary</h3>
        <SummaryCards report={report} />
      </section>

      <section>
        <h3 className="text-sm font-semibold text-muted uppercase tracking-wide mb-3">Findings</h3>
        <FindingsTable findings={(report.review || {}).findings} />
      </section>

      <section>
        <h3 className="text-sm font-semibold text-muted uppercase tracking-wide mb-3">Patches Applied</h3>
        <PatchesSection patches={report.patches} />
      </section>

      <section>
        <h3 className="text-sm font-semibold text-muted uppercase tracking-wide mb-3">Documentation</h3>
        <DocumentationSection doc={report.documentation} />
      </section>

      <section>
        <h3 className="text-sm font-semibold text-muted uppercase tracking-wide mb-3">Agent Trace Timeline</h3>
        <AgentTimeline trace={report.agent_trace} />
      </section>
    </div>
  );
}
