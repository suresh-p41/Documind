# DocuMind – Test Data Documentation

This document provides an overview of the test data available for DocuMind, including the purpose of each folder, expected test results, and instructions for generating additional test documents.

The test dataset is designed to evaluate DocuMind's ability to:
- Identify document types and extract relevant information.
- Extract text from both digital and scanned PDFs.
- Detect missing, inconsistent, or suspicious information.
- Identify documents that require human verification.
- Handle IRS notices and other legal documents.
- Detect poor-quality scans and extraction failures.

## 1. Folder Structure

The `testdata` directory contains the following folders and files:

| Folder / File | Description | Testing Purpose |
|---|---|---|
| `cuad_digital/` | Contains 12 real US commercial contracts (3–6 pages each) in digital PDF format. | Test document classification and extraction accuracy. |
| `cuad_scanned/` | Contains scanned versions of 6 contracts from the digital dataset, along with 1 deliberately poor-quality scan. These PDFs contain images rather than selectable text. | Test OCR accuracy and poor-scan detection. |
| `synthetic/` | Contains 6 artificially created US legal documents with predefined issues and inconsistencies. | Test automatic verification rules and human review decisions. |
| `irs_notices/` | Contains 10 official IRS sample notices and 3 scanned copies. | Test extraction of IRS notice details, tax amounts, and payment deadlines. |
| `raw/` | Contains the complete CUAD dataset with 510 contracts (approximately 170 MB). Not stored in git; see section 5 to download it. | Source additional contracts for testing. |
| `tools/make_scanned.py` | A Python utility that converts digital PDFs into scanned PDFs. | Generate additional scanned documents for OCR testing. |

### Expected Results for CUAD Contracts

The file `cuad_expected.json` contains reference information for the 12 CUAD contracts.

These reference values have been labelled by legal experts and can be used to compare DocuMind's extracted results against the expected answers.

The reference data includes:
- Document name
- Contracting parties
- Agreement date
- Effective date
- Expiration date
- Governing law

Each record is linked to its corresponding PDF filename.

**Important:** Scanned versions of these contracts have the same expected answers as their original digital PDFs.

## 2. Synthetic Documents – Expected Test Results

The synthetic dataset contains documents specifically created to test DocuMind's validation and human verification logic.

Each document contains a predefined scenario.

| Document | Scenario | Expected Result |
|---|---|---|
| `1_clean_lease.pdf` | A lease agreement with no known issues. | No human review required. |
| `2_problem_lease.pdf` | Contains an incorrectly formatted EIN, conflicting rent amounts, and embedded text saying "ignore previous instructions". | Flag for human review. |
| `3_clean_order.pdf` | A federal court order (summary judgment) with no known issues. | No human review required. |
| `4_deed_no_notary.pdf` | A deed missing its notary acknowledgment. | Flag for human review. |
| `5_ambiguous.pdf` | Mentions three companies without clearly identifying the primary entity and contains an unexplained number. | Flag for human review. |
| `6_blank_page.pdf` | Contains a blank page with no extractable text. | Extraction failure: "No text could be extracted from the PDF". |

### Additional OCR Quality Test

The following document is intentionally created with poor scan quality:

`cuad_scanned/05_distributor_agreement_BAD_scan.pdf`

**Expected behaviour:**
- DocuMind should identify that the scan quality is poor and flag it for review.
- Alternatively, if processing continues, the extracted JSON should show noticeably lower accuracy than the normal scanned version.

This test helps verify whether DocuMind can recognize unreliable OCR results rather than treating every extraction as accurate.

## 3. Generating Additional Scanned Documents

The utility `make_scanned.py` can convert any digital PDF into a scanned PDF.

This is useful when additional OCR test cases are required.

**Step 1: Navigate to the testdata directory**

```bash
cd testdata
```

**Step 2: Convert a digital PDF into a scanned PDF**

```bash
../backend/.venv/bin/python tools/make_scanned.py cuad_digital/09_supply_agreement.pdf cuad_scanned/09_supply_agreement_scanned.pdf
```

**Step 3: Generate a poor-quality scanned PDF**

```bash
../backend/.venv/bin/python tools/make_scanned.py IN.pdf OUT.pdf --quality bad
```

Replace `IN.pdf` with the source PDF and `OUT.pdf` with the desired output path.

The `--quality bad` option deliberately reduces scan quality to simulate real-world document scanning problems.

## 4. IRS Notices Dataset

The `irs_notices/` folder contains official sample notices published by the US Internal Revenue Service (IRS).

Source: `eitc.irs.gov/pub/notices/`

These are public-domain US government documents.

The sample notices use placeholder information such as:
- TAXPAYER NAME
- ADDRESS

DocuMind should extract these values as they appear in the documents rather than treating them as missing information.

### Available IRS Notice Types

| Notice | Description | Information to Extract |
|---|---|---|
| CP14 | Balance Due Notice | Outstanding tax amount and payment deadline. |
| CP161 | Business Tax Balance Due | Unpaid business tax balance. |
| CP501, CP503 | Unpaid Tax Reminders | Outstanding balance and payment instructions. |
| CP504 | Notice of Intent to Levy | Amount due and potential collection action. |
| CP71C | Annual Balance-Due Reminder | Outstanding tax balance. |
| CP77, CP90, CP297 | Final Notices | Intent to seize assets and right to request a hearing. |
| CP2566 | Return Not Received | Missing tax return and substitute return information. |

**Not included: CP 575 (EIN Assignment Letter)**

The IRS does not publish a sample PDF of this notice, so it is not included in the current dataset.

## 5. Dataset Sources and Licensing

### CUAD – Contract Understanding Atticus Dataset

The commercial contracts used in this test dataset come from CUAD (Contract Understanding Atticus Dataset), version 1, published by The Atticus Project.

- **License:** Creative Commons Attribution 4.0 (CC BY 4.0).
- **Original source:** Contracts filed with the US Securities and Exchange Commission (SEC) through EDGAR.
- **Dataset website:** https://www.atticusprojectai.org/cuad
- **Download and dataset records:** https://zenodo.org/records/4595826

To recreate the `raw/` folder (not stored in git because of its size):

```bash
cd testdata
mkdir -p raw && cd raw
curl -L -o CUAD_v1.zip "https://zenodo.org/records/4595826/files/CUAD_v1.zip?download=1"
unzip -q CUAD_v1.zip && rm CUAD_v1.zip
```

### Research Paper

Hendrycks, Burns, Chen, and Ball:

*CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review*

Research paper: https://arxiv.org/abs/2103.06268

---

## 6. Overall Testing Coverage

The dataset covers the following major areas of DocuMind functionality:

| Testing Area | Dataset | What We Want to Validate |
|---|---|---|
| Document classification | CUAD, IRS notices, Synthetic | Correctly identify the type of document. |
| Entity identification | CUAD, Synthetic | Identify the company or entity associated with the document. |
| Information extraction | CUAD, IRS notices | Extract relevant dates, parties, amounts, and other key information. |
| OCR processing | Scanned CUAD, IRS scans | Extract text accurately from scanned documents. |
| OCR quality assessment | Bad scanned PDF | Recognize when extracted information may be unreliable. |
| Automatic verification | Synthetic documents | Detect malformed identifiers, conflicting values, and missing information. |
| Security and prompt injection | Problem lease | Prevent embedded document instructions from influencing the extraction process. |
| Human verification | Synthetic, scanned documents | Correctly identify documents that require manual review. |
| Extraction failure handling | Blank PDF | Handle documents from which no text can be extracted. |

**Objective:** Use this dataset to evaluate DocuMind across normal documents, scanned documents, documents with intentional problems, and real-world IRS notices. The goal is to ensure that DocuMind not only extracts information but also recognizes when the extracted information is incomplete, inconsistent, or unreliable.