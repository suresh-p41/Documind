// Reasons a file was sent to verification, grouped under readable labels.

const CATEGORY = {
  manual: "Manual",
  low_classification_confidence: "Document type",
  entity_ambiguity: "Entity",
  missing_required_fields: "Missing fields",
  identifier_uncertainty: "Identifier",
  ocr_quality: "OCR quality",
  conflicting_information: "Conflict",
  suspicious_content: "Suspicious",
  verification_skipped: "Not verified",
};

export default function ReviewReasons({ reasons }) {
  if (!reasons?.length) return null;
  return (
    <ul className="reasons">
      {reasons.map((r, i) => (
        <li key={i}>
          <span className={`reason-source reason-${r.source}`}>{CATEGORY[r.code] || r.code}</span>
          <span>{r.message}</span>
        </li>
      ))}
    </ul>
  );
}
