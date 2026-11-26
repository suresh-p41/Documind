"""
Automatic rules that decide whether a processed document needs
human verification.

Each rule looks at the extracted JSON (and the OCR quality report) and
returns zero or more reasons. Any reason => review_status = needs_review.

Rules combine two kinds of evidence:
  * the model's own review_signals (it says when it is unsure), and
  * plain checks in code (formats, missing fields, OCR scores), which
    don't depend on the model noticing the problem.
"""

import re

from app.services.pdf_service import PdfExtraction

# ---------- Business rules: required fields per document type ----------
# Edit this table to change what counts as "missing". Each check is
# (description shown to the reviewer, function(result) -> bool present).


def _parties(n):
    return (f"at least {n} part{'y' if n == 1 else 'ies'}", lambda r: len(r["parties"]) >= n)


_SIGNATURES = ("a signature block", lambda r: len(r["signatures"]) > 0)
_SIGNED_OR_EFFECTIVE_DATE = (
    "an effective or execution date",
    lambda r: bool(r["dates"]["effective_date"] or r["dates"]["execution_date"]),
)
_AMOUNT = ("a monetary amount", lambda r: len(r["monetary_amounts"]) > 0)
_PROPERTY = ("the property address or legal description",
             lambda r: bool(r["real_property"] and (r["real_property"]["address"] or r["real_property"]["legal_description"])))
_NOTARIZED = ("a notary acknowledgment", lambda r: r["notarization"]["notarized"])
_CASE_NUMBER = ("a case number", lambda r: bool(r["court"] and r["court"]["case_number"]))
_COURT_NAME = ("the court name", lambda r: bool(r["court"] and r["court"]["court_name"]))

AGREEMENT = [_parties(2), _SIGNED_OR_EFFECTIVE_DATE, _SIGNATURES]
COURT_DOCUMENT = [_COURT_NAME, _CASE_NUMBER]

REQUIRED_FIELDS = {
    "contract": AGREEMENT,
    "nda": AGREEMENT,
    "employment_agreement": AGREEMENT,
    "settlement_agreement": AGREEMENT + [_AMOUNT],
    "lease": AGREEMENT + [_AMOUNT, _PROPERTY],
    "deed": [_parties(2), _PROPERTY, _SIGNATURES, _NOTARIZED],
    "mortgage_or_deed_of_trust": [_parties(2), _AMOUNT, _PROPERTY, _SIGNATURES],
    "promissory_note": [_parties(2), _AMOUNT, _SIGNATURES],
    "will": [_parties(1), _SIGNATURES],
    "trust": [_parties(1), _SIGNATURES],
    "power_of_attorney": [_parties(2), _SIGNATURES],
    "affidavit": [_parties(1), _SIGNATURES, _NOTARIZED],
    "complaint": COURT_DOCUMENT + [_parties(2)],
    "motion": COURT_DOCUMENT,
    "summons": COURT_DOCUMENT,
    "subpoena": COURT_DOCUMENT,
    "court_order": COURT_DOCUMENT,
    "judgment": COURT_DOCUMENT,
}

GENERIC_ROLES = {"", "party", "parties", "company", "organization", "entity"}

EIN_FORMAT = re.compile(r"^\d{2}-?\d{7}$")

# Phrases that try to instruct an AI. Checked against the OCR text in code,
# so it works even if the model obeys the instruction instead of reporting it.
INJECTION_PATTERNS = re.compile(
    r"ignore (all |any )?(previous|prior|above) instructions"
    r"|disregard (the |all )?(previous|prior|above)"
    r"|you are (now )?(an? )?(ai|assistant|language model|chatgpt)"
    r"|system prompt"
    r"|output the full (ssn|social security)"
    r"|do not (flag|report) this",
    re.IGNORECASE,
)


def _reason(code: str, message: str) -> dict:
    return {"code": code, "message": message, "source": "rule"}


def _normalize(text: str) -> str:
    # Lower-case, drop markdown symbols, collapse whitespace
    text = re.sub(r"[*_#`|>]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _with_evidence(issue: dict) -> str:
    quotes = " vs ".join(f'"{q.strip()}"' for q in issue["evidence"][:3])
    return f"{issue['description'].rstrip('.')} ({quotes})" if quotes else issue["description"]


def grounded(issues: list[dict], document_text: str, min_quotes: int = 1) -> list[dict]:
    """
    Keep only issues whose evidence quotes all appear in the document.
    Conflicts need min_quotes=2 different quotes (the two values).
    """
    doc = _normalize(document_text)
    kept = []
    for issue in issues:
        quotes = {_normalize(q) for q in issue["evidence"] if _normalize(q)}
        if len(quotes) >= min_quotes and all(q in doc for q in quotes):
            kept.append(issue)
    return kept


# ---------- The 7 rules ----------

def _classification(result, signals) -> list[dict]:
    doc_type = result["document_type"]
    confidence = signals["document_type_confidence"]
    alternative = signals["alternative_document_type"]

    if doc_type in (None, "other"):
        return [_reason("low_classification_confidence",
                        "Document type could not be determined")]
    # Only "low": in testing, "medium" also fired on correctly typed documents
    if confidence == "low":
        alt = f", possibly {alternative.replace('_', ' ')}" if alternative and alternative != doc_type else ""
        return [_reason("low_classification_confidence",
                        f"AI is unsure of the document type: classified as {doc_type.replace('_', ' ')}{alt}")]
    return []


def _entity(result, signals) -> list[dict]:
    if not result["parties"]:
        return [_reason("entity_ambiguity", "No parties were identified")]
    names = ", ".join(p["name"] for p in result["parties"][:4])
    if signals["primary_party_unclear"]:
        return [_reason("entity_ambiguity", f"Primary party is unclear among: {names}")]

    # Checked in code too: 3+ organizations that all have the same generic
    # role (e.g. "party") means the document doesn't say who is primary
    orgs = [p for p in result["parties"] if p["party_type"] == "organization"]
    roles = {(p["role"] or "").strip().lower() for p in orgs}
    if len(orgs) >= 3 and roles <= GENERIC_ROLES:
        return [_reason("entity_ambiguity",
                        f"{len(orgs)} organizations with no distinct roles; primary entity unclear: {names}")]
    return []


def _missing_fields(result, signals) -> list[dict]:
    checks = REQUIRED_FIELDS.get(result["document_type"], [])
    missing = [label for label, present in checks if not present(result)]
    if missing:
        return [_reason("missing_required_fields",
                        f"Missing required information for a {result['document_type'].replace('_', ' ')}: "
                        + ", ".join(missing))]
    return []


def _identifiers(result, signals) -> list[dict]:
    reasons = []
    for ident in result["identifiers"]:
        if ident["identifier_type"] == "EIN" and not EIN_FORMAT.match(ident["value"].strip()):
            reasons.append(_reason("identifier_uncertainty",
                                   f"EIN \"{ident['value']}\" does not match the XX-XXXXXXX format"))
        elif ident["identifier_type"] == "other":
            reasons.append(_reason("identifier_uncertainty",
                                   f"Identifier \"{ident['value']}\" has an unknown type"))
    for issue in signals["uncertain_identifiers"]:
        reasons.append(_reason("identifier_uncertainty", f"AI flagged an identifier: {_with_evidence(issue)}"))
    return reasons


def _ocr_quality(pdf: PdfExtraction, signals) -> list[dict]:
    reasons = []
    if pdf.low_quality_pages:
        pages = ", ".join(map(str, pdf.low_quality_pages))
        reasons.append(_reason("ocr_quality",
                               f"Low OCR confidence on page(s) {pages} (lowest {pdf.min_page_ocr_score:.0%})"))
    if pdf.empty_pages:
        pages = ", ".join(map(str, pdf.empty_pages))
        reasons.append(_reason("ocr_quality", f"No text found on page(s) {pages}"))
    for issue in signals["text_quality_issues"]:
        reasons.append(_reason("ocr_quality", f"AI flagged unreadable or incomplete text: {_with_evidence(issue)}"))
    return reasons


def _conflicts(result, signals) -> list[dict]:
    return [_reason("conflicting_information", _with_evidence(issue))
            for issue in signals["conflicting_information"]]


def _suspicious(pdf: PdfExtraction, signals) -> list[dict]:
    reasons = []
    match = INJECTION_PATTERNS.search(pdf.text)
    if match:
        reasons.append(_reason("suspicious_content",
                               f"Document contains an embedded instruction: \"{match.group(0)}\""))
    for issue in signals["suspicious_content"]:
        reasons.append(_reason("suspicious_content", f"AI flagged: {_with_evidence(issue)}"))
    return reasons


# Used when the verification pass could not run, so every signal is "unknown"
NO_SIGNALS: dict = {
    "document_type_confidence": "high",
    "alternative_document_type": None,
    "primary_party_unclear": False,
    "conflicting_information": [],
    "uncertain_identifiers": [],
    "text_quality_issues": [],
    "suspicious_content": [],
}


def evaluate(result: dict, signals: dict | None, pdf: PdfExtraction) -> list[dict]:
    """
    Return every reason this document needs human verification.

    result:  the extracted JSON (DocumentExtraction as a dict)
    signals: output of the verification pass (ReviewSignals as a dict),
             or None if that pass was skipped
    pdf:     OCR text and quality report
    """
    skipped = []
    if signals is None:
        skipped = [_reason("verification_skipped",
                           "Automatic verification pass was skipped (document too long), so it needs a manual check")]
        signals = NO_SIGNALS
    else:
        # Drop AI-reported issues that can't be backed by quotes from the document
        signals = {
            **signals,
            "conflicting_information": grounded(signals["conflicting_information"], pdf.text, min_quotes=2),
            "uncertain_identifiers": grounded(signals["uncertain_identifiers"], pdf.text),
            "text_quality_issues": grounded(signals["text_quality_issues"], pdf.text),
            "suspicious_content": grounded(signals["suspicious_content"], pdf.text),
        }

    reasons = skipped + (
        _classification(result, signals)
        + _entity(result, signals)
        + _missing_fields(result, signals)
        + _identifiers(result, signals)
        + _ocr_quality(pdf, signals)
        + _conflicts(result, signals)
        + _suspicious(pdf, signals)
    )

    # Drop exact duplicates while keeping order
    seen, unique = set(), []
    for r in reasons:
        key = (r["code"], r["message"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique
