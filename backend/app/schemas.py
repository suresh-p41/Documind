from typing import Literal, Optional

from pydantic import BaseModel, model_validator


DocumentType = Literal[
    # Agreements
    "contract",
    "nda",
    "employment_agreement",
    "settlement_agreement",
    "lease",
    # Real estate and finance
    "deed",
    "mortgage_or_deed_of_trust",
    "promissory_note",
    "lien_or_ucc_filing",
    # Estate planning
    "will",
    "trust",
    "power_of_attorney",
    # Court documents
    "complaint",
    "motion",
    "summons",
    "subpoena",
    "court_order",
    "judgment",
    # Other
    "affidavit",
    "corporate_filing",
    "legal_notice",
    "letter",
    "other",
]


class Party(BaseModel):
    name: str
    # Role as stated in the document: lessor, lessee, plaintiff, grantor...
    role: str
    party_type: Optional[Literal["individual", "organization", "government"]]
    # LLC, corporation, LP, trust, sole proprietorship...
    entity_type: Optional[str]
    # US state where an organization is formed, e.g. "Delaware"
    state_of_formation: Optional[str]
    address: Optional[str]


class CourtInfo(BaseModel):
    court_name: Optional[str]
    court_level: Optional[Literal["federal", "state", "other"]]
    state: Optional[str]
    county: Optional[str]
    case_number: Optional[str]
    judge: Optional[str]


class KeyDates(BaseModel):
    # All dates as YYYY-MM-DD
    document_date: Optional[str]
    effective_date: Optional[str]
    execution_date: Optional[str]
    expiration_date: Optional[str]
    filing_date: Optional[str]
    recording_date: Optional[str]


class MonetaryAmount(BaseModel):
    description: str
    amount: float
    currency: str


class Clause(BaseModel):
    clause_type: Literal[
        "term_and_renewal",
        "termination",
        "payment",
        "indemnification",
        "limitation_of_liability",
        "confidentiality",
        "non_compete",
        "non_solicitation",
        "arbitration",
        "dispute_resolution",
        "assignment",
        "force_majeure",
        "other",
    ]
    summary: str


class Identifier(BaseModel):
    identifier_type: Literal[
        "EIN",
        "case_number",
        "parcel_number",
        "recording_number",
        "ucc_filing_number",
        "state_entity_id",
        "bar_number",
        "other",
    ]
    value: str
    # Agency or office that issued it, e.g. "IRS", "Cook County Recorder"
    issuing_authority: Optional[str]


class RealProperty(BaseModel):
    address: Optional[str]
    county: Optional[str]
    state: Optional[str]
    # Short form only, e.g. "Lot 12, Block 4, Oak Ridge Subdivision"
    legal_description: Optional[str]


class Signature(BaseModel):
    signer_name: Optional[str]
    signer_title: Optional[str]
    on_behalf_of: Optional[str]
    date_signed: Optional[str]


class Notarization(BaseModel):
    notarized: bool
    notary_name: Optional[str]
    notary_state: Optional[str]
    notary_county: Optional[str]
    commission_expires: Optional[str]


class SensitiveItem(BaseModel):
    data_type: Literal[
        "ssn",
        "itin",
        "date_of_birth",
        "bank_account",
        "credit_card",
        "drivers_license",
        "passport",
        "medical_information",
        "minor_name",
        "other",
    ]
    # Masked value: last 4 digits only, year only for dates of birth
    masked_value: str


class Issue(BaseModel):
    # One sentence describing the problem
    description: str
    # Exact text copied from the document that shows the problem.
    # Code checks these quotes really appear in the document and drops
    # the issue if they don't, which filters out invented problems.
    evidence: list[str]


# Produced by a separate verification pass (llm_service.verify_extraction),
# not by the extraction itself. Used by app/review_rules.py.
class ReviewSignals(BaseModel):
    # How sure the model is about document_type
    document_type_confidence: Literal["high", "medium", "low"]
    # Second most likely type when confidence is not high
    alternative_document_type: Optional[DocumentType]
    # Several organizations could be the main party and it's unclear which
    primary_party_unclear: bool
    # The same fact given with different values in different places
    # (evidence: the two different values, quoted)
    conflicting_information: list[Issue]
    # Identifiers whose label is missing or whose characters are unclear
    # (evidence: the identifier as written)
    uncertain_identifiers: list[Issue]
    # Text that is garbled, cut off or unreadable (evidence: the garbled text)
    text_quality_issues: list[Issue]
    # Out-of-place instructions or signs of tampering (evidence: the text)
    suspicious_content: list[Issue]


class DocumentExtraction(BaseModel):
    title: Optional[str]
    document_type: Optional[DocumentType]
    parties: list[Party]
    court: Optional[CourtInfo]
    # US state whose law governs, e.g. "New York"
    governing_law_state: Optional[str]
    dates: KeyDates
    monetary_amounts: list[MonetaryAmount]
    key_clauses: list[Clause]
    identifiers: list[Identifier]
    real_property: Optional[RealProperty]
    signatures: list[Signature]
    notarization: Notarization
    sensitive_data: list[SensitiveItem]
    summary: Optional[str]

    @model_validator(mode="after")
    def clean_up(self):
        # Letters and notices don't create obligations, so they have no clauses
        if self.document_type in ("letter", "legal_notice"):
            self.key_clauses = []

        # A real identifier always contains at least one digit
        self.identifiers = [
            i for i in self.identifiers
            if any(ch.isdigit() for ch in i.value)
        ]
        return self