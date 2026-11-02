# Fresh paired comparison

K=4; relevance unit=PDF page. Recall is non-exhaustive reference-evidence recall. B9 assessed separately.

|ID|Precision@4|Reference recall@4|Sufficient|RAG /2|Baseline /2|Citation /1|Assessment|
|---|---|---|---|---|---|---|---|
|B1|0.25|1.0|1|0|0|None|Wrong abstention although S4 contains the annual 2024 Washington row.|
|B2|0.25|1.0|1|0|0|0|Correct 4.5 figure but reverses required preliminary qualification; core contradiction.|
|B3|0.5|1.0|1|0|0|0|Both numbers are correct, but the answer explicitly disclaims the requested all-occupation result; internally contradictory core answer rather than a reliable completed comparison.|
|B4|1.0|1.0|1|2|0|0|Correct totals, establishment types and extra component figures; additional figures verified on PDF p2.|
|B5|0.25|1.0|1|2|0|1|Correct national 5.2 million added jobs, 3.1 percent growth, 175.2 million total.|
|B6|0.25|1.0|1|2|0|1|Correct four counts and source context.|
|B7|0.25|1.0|1|2|0|1|Correct 256000 and 4.1 percent from January10 release.|
|B8|0.5|1.0|1|2|0|1|Correct 7.6 million openings, 5.5 million hires and 5.3 million separations with requested timing.|
|B9|None|None|None|2|2|None|Correct explicit corpus abstention; no tax rate fabricated.|

Macro over eight answerable cases: Precision@4=0.406; reference-evidence Recall@4=1.000.
