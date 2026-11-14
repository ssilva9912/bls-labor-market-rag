# Fresh BLS evaluation protocol

Freeze this rubric before paired generation. The nine questions were used for
source/reference and retrieval development; there is no held-out claim. Eight
questions are answerable, one (B9) is intentionally unsupported by this corpus.
No earlier-corpus scores enter this evaluation. Manual judgments are made against
the saved PDFs, not keyword grading or model self-grading; record a reason each.

K is 4. The relevance unit is a PDF page (not a chunk or document). Each retrieved PDF-page passage gets relevance 2 if it directly supports any
required answer fact, 1 if only contextual/topical, 0 if irrelevant or wrong
period/geography/measure. Strict precision counts grade2 / actual returned
slots (K=4, unfilled slots count as nonrelevant) over the eight answerable cases;
report per-question and macro Precision@4. Actual returned counts are also reported.
Reference-evidence Recall@4 is the fraction of canonical supporting PDF pages in
references.json retrieved in the top4. Those documented evidence pages are a
non-exhaustive reference set; this is not exhaustive corpus recall. Other pages
can support a fact without being in the canonical recall set. Record per-case
gold filenames/pages, intersections, denominators and macro recall over eight.
Grade sufficiency 1 only if the selected excerpts jointly support all required
criteria, else0. Denominator eight. B9 is N/A for these aggregates; inspect its
contexts anyway. Corpus-wide review, not top-k absence, establishes abstention.

Correctness for each completed arm is 2 for all required facts/qualifications,
1 for useful partial facts without a materially contradictory core claim, 0 for
wrong core facts/measure/period, unsupported explanations or abstention on an
answerable case. B9 earns2 for explicit abstention without inventing a tax rate.
Additional unsupported material can reduce correctness. Report points/possible,
fully correct/completed and answerable-only results separately. All nine new
questions count; original retired questions are not retrospectively regraded.

Citation support for a factual RAG answer is 1 only if valid [S#] passages support
every material factual claim without wrong file/page attribution, else0. Pure
abstention is N/A, as is baseline. Correctness and support are independent.

Record abstentions separately. Transport/deadline/worker/empty/truncation errors
are N/A for answer quality, never silent wrong-answer zeros; list category and
completion denominators. Paired comparisons use both-completed cases. Both arms
use the identical frozen llama3.1:8b digest/options, one attempt, no selective
retry and no post-freeze answer rewriting. Keep raw output and call timings.
