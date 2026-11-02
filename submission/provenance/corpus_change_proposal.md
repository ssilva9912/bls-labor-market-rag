# Five-document corpus proposal — approval required

No corpus document, index, old result, or source/reference file has been deleted
or replaced. No replacement source body has been downloaded into the project.
This is a review proposal, not a completed five-document evaluation.

## Current-source inspection and reuse decision

All ten local PDFs were opened with pypdf, their page counts/hashes checked, and
rights notices searched. The first pages of the three certified legal PDFs were
rendered and visually inspected; all their pages carry legal certification footers.
The detailed inspection record is `tmp/corpus_rights_review/current_sources_inspected.json`.
Absence of a copyright notice was never treated as permission.

|Current file|Finding|Proposed decision|
|---|---|---|
|01_esd_annual_lmer_2025.pdf|PDF p3 permits internal/personal non-commercial use and requires authorization for other uses.|Remove.|
|02_esd_q2_2026_briefing.pdf|No document-specific reuse grant found; ESD policy includes third-party content.|Remove; not cleared.|
|03_esd_facts_figures_2025.pdf|No document-specific reuse grant found; ESD policy includes third-party content.|Remove; public availability alone is insufficient.|
|04_erfc_feb2026_forecast.pdf|No document-specific reuse grant found; official site fetch returned403 during review.|Remove; terms unverified, not a claim that reuse is forbidden.|
|05_dor_qbr_q2_2025.pdf|DOR copyright notice recommends contacting its webmaster for permission.|Remove; not cleared.|
|06_wa_small_business_guide.pdf|Official guide page displays ORIA copyright/all-rights-reserved notice; no affirmative reuse terms verified.|Remove; not cleared.|
|07_wac_458_20_101.pdf|Government-edicts doctrine supports reuse of legal text, but Legislature disclaimer asserts copyright in code publications.|Do not count the complete PDF as having uncontested verified publisher reuse terms; replace.|
|08_rcw_19_255_breach.pdf|Same legal-text/publication distinction.|Replace.|
|09_rcw_19_373_mhmda.pdf|Same legal-text/publication distinction.|Replace.|
|10_watech_dsa_guidance.pdf|WaTech recommends seeking permission for site content; no specific open grant verified.|Remove; not cleared.|

This is a conservative document-selection decision, not a conclusion that the
text of statutes/rules is privately copyrightable. The U.S. Copyright Office
discusses government edicts in Compendium313.6(C)(2), physical PDF page37, while
the Legislature's own publication disclaimer asserts a claim. Rather than invent
a license or resolve that publication issue by assumption, select sources with
an explicit publisher reuse statement. Under that criterion, zero current full
PDFs are selected; all five documents below are replacements.

Sources checked:

- [U.S. Copyright Office, government-edicts discussion](https://www.copyright.gov/comp3/chap300/ch300-copyrightable-authorship.pdf), section313.6(C)(2), pp37-38.
- [Washington Legislature disclaimer](https://leg.wa.gov/disclaimer/), code-publication copyright claim and contact for sale.
- [ESD policy](https://esd.wa.gov/about-us/who-we-are-and-what-we-do/policies/privacy-statement), third-party content and reuse contact; direct fetch was403 this turn, prior official-policy review is preserved.
- [DOR copyright notice](https://dor.wa.gov/contact/your-privacy/website-privacy-notice).
- [ORIA guide page](https://www.business.wa.gov/site/alias__business/927/small-business-guide.aspx), footer.
- [WaTech copyright notice](https://watech.wa.gov/privacy-policy).

## Exactly five selected replacement documents

|ID|Document and verified official HTML source|Reference period / release date|Proposed local filename|
|---|---|---|---|
|D1|[Regional and State Unemployment — 2024 Annual Averages](https://www.bls.gov/news.release/archives/srgune_03052025.htm)|Calendar2024 / March5,2025|docs/01_bls_state_unemployment_annual_2024.txt|
|D2|[State Employment and Unemployment — December2024](https://www.bls.gov/news.release/archives/laus_01282025.htm)|December2024 / January28,2025|docs/02_bls_state_employment_unemployment_dec2024.txt|
|D3|[Occupational Employment and Wages — May2024](https://www.bls.gov/news.release/archives/ocwage_04022025.htm)|May2024 / April2,2025|docs/03_bls_occupational_employment_wages_may2024.txt|
|D4|[Business Employment Dynamics — Fourth Quarter2024](https://www.bls.gov/news.release/archives/cewbd_07302025.htm)|Q4 calendar2024 / July30,2025|docs/04_bls_business_employment_dynamics_q42024.txt|
|D5|[Employment Projections — 2024–2034](https://www.bls.gov/news.release/archives/ecopro_08282025.htm)|U.S.2024–2034 projection / August28,2025|docs/05_bls_employment_projections_2024_2034.txt|

**Documented terms for each of D1-D5:** [BLS Copyright Information](https://www.bls.gov/opub/copyright-information.htm)
explicitly states its publications are public domain except previously
copyrighted photographs/illustrations. It permits use of public-domain material
without specific permission and requests that BLS be cited. Its emblem is a
separately protected trademark. This is the publisher's actual statement, not
an invented Creative Commons license or an assumption about state government.

**Format is part of this approval proposal:** use five faithful UTF-8 text
snapshots of the official releases, retaining release text, technical notes and
tables, with source URL, release/capture dates and SHA-256. Exclude website
navigation, logos/emblems, photos and illustrations. Preserve table headers and
row/column alignment and verify them visually against the official source.
Source references will use filename, table/section and stable line ranges,
not invented original PDF page numbers. BLS HTML sources were successfully
inspected. HEAD-only probes of possible archived PDF endpoints returned403;
no PDF availability or PDF-specific reuse clearance is claimed. No replacement
PDF/source body has been saved to the workspace.

These are five distinct releases, not arbitrary splits of one report. The corpus
focus becomes BLS labor-market evidence, including Washington-specific state
tables and clearly labelled national occupational/projection evidence. The
national projection report must never be represented as Washington projections.
License/provenance records live outside the indexed five-document directory.

## Files proposed for deletion after approval

`corpus_change_manifest.json` lists **193 exact existing file paths**, sizes and
reasons. No wildcard deletion is authorized by this proposal generator.

|Group|Existing files|Reason|
|---|---:|---|
|docs/*.pdf|10|The ten named current-source PDFs above; none selected.|
|submission/|56|Obsolete duplicate ten-document package, including source PDFs, index, development excerpts and old scores.|
|final_artifacts/|11|Old answers, retrieved excerpts, comparisons, reference tables, scores and analysis; regenerate entirely.|
|index/|8|Old vectors, SQLite files, metadata and extracted chunks; rebuild from scratch.|
|results/|19|Old Gemini/Ollama runs and checkpoints with removed-source excerpts; no old scores carried forward.|
|archive/|41|Obsolete snapshots, excerpt/reference fixtures and old-generation utilities; credential/private-config paths exempt.|
|tmp/|32|Old source downloads, page images, analysis render and inspection/build utilities enumerated in the manifest.|
|Root obsolete files and legacy scoring test|16|Exact paths below.|

The16 root/test deletions are:

```
reference_review.json
reference_table.csv
reference_table.md
authoritative_source_review.md
unemployment_evidence_review.md
development_case_review.md
ollama_migration_review.md
prepare_final.py
record_judgments.py
create_analysis.py
score_results.py
compare_development.py
development_diagnostics.py
rubric_development.py
package_submission.py
tests/test_scoring.py
```

Separately, the manifest identifies files to **replace**, including the current
question/reference files, freeze manifest, rubric, source inventory, README,
publication review/notices and publication inventory. Original question texts,
IDs, explicit corrections and hashes will first be preserved as non-excerpt
provenance records, with a mapping to the new question set. Old answers,
retrieved passages and scores will not be retained as new-corpus artifacts.

Five discovered credential/private-config paths are expressly protected in the
manifest; no values were read or printed. External credentials, `.venv`, local
embedding/Ollama caches and unrelated user files remain untouched. Before any
approved deletion, resolve each exact target within this workspace and recheck
inventory state. New or changed files are not silently added to the deletion set.

## Work authorized only after approval

1. Capture the five approved releases and reuse-term evidence; verify body/table
   fidelity and source attribution. If a selected release cannot be obtained,
   stop that replacement rather than silently substituting another source.
2. Preserve original-question provenance; remove only approved unwanted sources
   and obsolete artifacts, then build a fresh Chroma collection using the existing
   local MiniLM embedding model. Enforce exactly five source documents.
3. Create eight explicitly versioned questions: seven answerable and one corpus
   abstention. Proposed coverage is Washington's2024 annual unemployment;
   Washington's December2024 monthly rate and distinction from annual;
   Washington's December2024 payroll employment/change; May2024 national
   occupational employment and wage facts; Q4-2024 national gross job gains/losses;
   2024–2034 national employment projections; and an unsupported Seattle city
   service-business B&O rate. Final wording/reference values follow source capture
   and verification, not assumed numbers. Every selected document must support
   at least one answerable question.
4. Verify references against the new snapshots, freeze sources/questions/settings,
   and run one new paired Ollama llama3.1:8b evaluation with identical options,
   timeouts and retry policy for both arms. No Gemini requests or model downloads.
5. Assign new manual correctness, retrieval relevance, sufficiency and citation
   judgments independently. Report errors, abstentions and denominators, and
   disclose which questions were developed/tuned. Rebuild CSV/JSONL, comparisons,
   reference table and authored one-page analysis; reuse no old scores.
6. Consolidate active code, tests, docs, corpus, provenance and artifacts; remove
   duplicate submission snapshots rather than maintain conflicting copies. Adapt
   retrieval to the five text snapshots and stable source locators. Update CI for
   offline tests, source hashes/terms, exact corpus count and fresh artifact
   validation, keeping live inference opt-in. Validate publication scans again.

No commit, staging, upload or push is included. Approval is requested because
you explicitly required reviewing selected sources and deletions first.
