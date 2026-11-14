# Experiment 02: base vs fine-tuned

|Arm|Model|Passages|Points|Fully correct|Answerable pts|Citations supported|Has [S#]|Sources line|Mean s|
|---|---|---|---|---|---|---|---|---|---|
|base_rag|llama3.1:8b|yes|12/18|6/9|10/16|4/7|7/9|1/9|12.606|
|ft_rag|llama3.1-bls-ft|yes|16/18|8/9|14/16|6/8|8/9|9/9|14.13|
|base_closed_book|llama3.1:8b|no|2/18|1/9|0/16|n/a|n/a/9|n/a/9|13.443|
|ft_closed_book|llama3.1-bls-ft|no|2/18|1/9|0/16|n/a|n/a/9|n/a/9|13.958|
