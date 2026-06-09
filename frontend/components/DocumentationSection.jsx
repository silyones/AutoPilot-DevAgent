export default function DocumentationSection({ doc }) {
  if (!doc?.summary) {
    return <p className="text-muted text-sm">No documentation generated.</p>;
  }
  return <p className="text-sm leading-relaxed">{doc.summary}</p>;
}
