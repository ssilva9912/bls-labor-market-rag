# Evaluating Retrieval-Augmented Generation on BLS Labor Market Reports

## Objective and utility

This study evaluates whether retrieved evidence improves local language-model answers about employment, unemployment, wages, job flows, and projections. BLS Labor Market RAG supports release-specific statistical lookup with traceable PDF evidence, a useful aid for labor-market research and policy analysis that still requires human review.

## Corpus and system

The corpus contains eight unmodified official U.S. Bureau of Labor Statistics PDFs, totaling 172 pages. Source URLs, release dates, download timestamps, hashes, attribution, and reuse terms are recorded in the inventory. PDF text was split into 1,000-character chunks with 180-character overlap, producing 1,178 chunks. Normalized local all-MiniLM-L6-v2 embeddings are stored in Chroma. Dense retrieval and page-level BM25 are combined through reciprocal rank fusion, with 16 candidates per route and four returned PDF pages. Release filtering and table-row preservation help retain relevant evidence.

## Controlled comparison

Nine development questions comprise eight answerable cases, one per document, and one unsupported Seattle city tax-rate question. Each received one RAG and one no-retrieval response from the identical Ollama llama3.1:8b Q4_K_M model and frozen digest. Both arms used temperature 0, seed 42, an 8,192-token context, a 1,024-token output limit, and one attempt. Frozen inputs, raw responses, references with filenames and physical pages, and hash-bound manual judgments are retained.

## Results and scales

Across the eight answerable cases, macro Precision@4 was 40.625% (13 directly relevant pages in 32 slots). Macro reference-evidence Recall@4 was 100% (8 of 8 canonical pages); this is not exhaustive corpus recall. Manual page labels distinguish direct support, context, and irrelevance. Correctness uses 0 for wrong or unsupported, 1 for partial without a core contradiction, and 2 for fully correct. RAG earned 12/18 points with 6/9 fully correct, versus 2/18 and 1/9 without retrieval. On answerable cases alone, scores were 10/16 versus 0/16. Points are not accuracy percentages. Citation support was 4/7 factual RAG responses; pure abstentions were excluded.

## Successes and failures

Both arms appropriately abstained on the unsupported tax rate. RAG nevertheless abstained on an available annual-rate table, reversed a preliminary-estimate qualification, and contradicted correct wage figures. Another answer cited the wrong page for component figures. All 18 calls completed with zero runtime failures. RAG made three abstentions, including one partial abstention; the baseline made eight. Mean generation-worker wall times were 5.602 and 5.255 seconds, respectively; RAG also averaged 2.165 seconds for retrieval. Worker timings include startup and are not end-to-end RAG latency.

## Limitations and improvements

Source selection, reference construction, and retrieval tuning used these same questions, including a table-coverage adjustment; no held-out performance is claimed. The small sample, incomplete relevance labels, single runs, and non-independent manual ratings limit generalization. Retrieval success did not guarantee interpretation or citation fidelity. Future work should use untouched questions, independent ratings, repeated timing measurements, and checks for table units, estimate qualifications, contradictions, and claim-level citations. Detailed comparisons and supporting evidence remain in the accompanying artifacts.
