# Fine-Tuning for Grounded Answer Format on BLS Labor Market Reports

## Question and setup

Experiment 01 showed that retrieval already finds the right pages, but the local 8B model mishandles them. This experiment tests whether a small QLoRA fine-tune fixes that answering behaviour. Llama 3.1 8B Instruct was trained on 44 hand-written examples (34 answerable, 2 partial, 8 unanswerable) that reuse the exact inference prompt, with loss on the answer only. The 84 MB adapter is layered on the same Ollama `llama3.1:8b` weights. Four arms answered the nine experiment-01 questions once each: base and fine-tuned, with retrieved pages and closed-book. No evaluation question or reference page appears in the training data.

## What changed with retrieved pages

The fine-tuned model scored 16/18 against 12/18 for the base model, with 8/9 against 6/9 fully correct and 14/16 against 10/16 on answerable questions. Fully supported citations rose from 4 of 7 factual answers to 6 of 8. Format compliance changed most: every fine-tuned answer ended with a `Sources:` line (9/9 against 1/9), although the prompt already asks for one. Both models abstained correctly on the unanswerable question.

## What moved closed-book

Nothing. Both closed-book arms scored 2/18 and 0/16 on answerable questions, earning points only on the question where declining is correct. The fine-tune changed behaviour, not knowledge. It did not reduce fabrication either: both models invented projection totals on B5, and the fine-tuned model also invented metropolitan-area counts on B6.

## Failures fixed and not fixed

Fixed: the wrong abstention on B1, where the fine-tuned model now reads Washington's 4.5 percent from the table; the self-contradictory answer on B3; and the B4 citation, which now cites page 2 for the component figures.

Not fixed: on B2 both models report the correct 4.5 percent but say the estimate was not preliminary, although the column is headed "Dec. 2024p" and the page footnotes p as preliminary. The training examples include preliminary caveats but did not teach the model to read that column marker. On B1 the fine-tuned answer is correct but cites page 2 when the row is on page 9, so the new failure is a confident wrong citation in place of an abstention.

## Is it worth it

Training cost no money and 11 minutes on an 8 GB laptop GPU; answers took 14.1 seconds on average against 12.6. The real cost is writing and checking the examples against the PDFs: [HOURS] hours here. For that, the gain was four points on two questions, two more supported citations and a consistent answer format. Fine-tuning is worth considering when a fixed citation format matters and the base model ignores the instruction. It is not a way to add facts, which retrieval supplies, and it cannot recover a table row that excerpting removed. A stronger prompt with one worked example is cheaper and was not tested here, so this experiment does not show that fine-tuning was necessary.

## Limits

Nine questions, one run and one seed. The questions were used to develop experiment 01, so they are held out from training but not from the system's design. Training contexts were shorter than inference contexts (3 pages of 3,500 characters against 4 of 5,000) to fit the GPU. The index was rebuilt for this run and is not byte-identical to experiment 01's, though every reference page was still retrieved. Judgments were made by one grader with an LLM second grader's suggestions visible; the two sets agreed on 35 of 36 answers before the one difference was reconciled, which is not an independent agreement rate.
