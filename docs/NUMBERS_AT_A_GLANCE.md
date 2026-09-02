# Numbers at a glance

commit `69388f5` · machine-extracted from `results/*.csv`, nothing retyped · regenerate: `./venv/Scripts/python.exe experiments/make_supervisor_brief.py`

`CI` is 95%. `clustered CI` resamples situations rather than rows, because phrasings of one situation are not independent observations. A blank means the field does not apply.

| Figure | Value | 95% CI | clustered CI | n | definition | stage | source | regenerate |
|---|---|---|---|---|---|---|---|---|
| Cross-statute: IPC-named, dense | **97.0%** | [84.7%, 99.5%] | [90.9%, 100.0%] | 33 | `dominant_corpus_among_top15` | `dense` | `hybrid_comparison.csv` | `./venv/Scripts/python.exe experiments/exp07_hybrid.py` |
| Cross-statute: BNS-named, dense | **51.5%** | [35.2%, 67.5%] | [33.3%, 69.7%] | 33 | `dominant_corpus_among_top15` | `dense` | `hybrid_comparison.csv` | `./venv/Scripts/python.exe experiments/exp07_hybrid.py` |
| Cross-statute: IPC-named, BM25 | **0.0%** | [0.0%, 10.4%] | [0.0%, 0.0%] | 33 | `dominant_corpus_among_top15` | `bm25` | `hybrid_comparison.csv` | `./venv/Scripts/python.exe experiments/exp07_hybrid.py` |
| Cross-statute: BNS-named, BM25 | **97.0%** | [84.7%, 99.5%] | [90.9%, 100.0%] | 33 | `dominant_corpus_among_top15` | `bm25` | `hybrid_comparison.csv` | `./venv/Scripts/python.exe experiments/exp07_hybrid.py` |
| Cross-statute: IPC-named, hybrid RRF | **45.5%** | [29.8%, 62.0%] | [27.3%, 63.6%] | 33 | `dominant_corpus_among_top15` | `hybrid_rrf` | `hybrid_comparison.csv` | `./venv/Scripts/python.exe experiments/exp07_hybrid.py` |
| Cross-statute: BNS-named, hybrid RRF | **78.8%** | [62.2%, 89.3%] | [63.6%, 90.9%] | 33 | `dominant_corpus_among_top15` | `hybrid_rrf` | `hybrid_comparison.csv` | `./venv/Scripts/python.exe experiments/exp07_hybrid.py` |
| Cross-statute pooled: dense | **74.2%** | [62.6%, 83.3%] | [65.2%, 83.3%] | 66 | `dominant_corpus_among_top15` | `dense` | `hybrid_comparison.csv` | `./venv/Scripts/python.exe experiments/exp07_hybrid.py` |
| Cross-statute pooled: BM25 | **48.5%** | [36.8%, 60.3%] | [45.5%, 50.0%] | 66 | `dominant_corpus_among_top15` | `bm25` | `hybrid_comparison.csv` | `./venv/Scripts/python.exe experiments/exp07_hybrid.py` |
| Cross-statute pooled: hybrid RRF | **62.1%** | [50.1%, 72.9%] | [53.0%, 71.2%] | 66 | `dominant_corpus_among_top15` | `hybrid_rrf` | `hybrid_comparison.csv` | `./venv/Scripts/python.exe experiments/exp07_hybrid.py` |
| Top-1 corpus: IPC-named, dense | **90.9%** | [76.4%, 96.9%] | [78.8%, 100.0%] | 33 | `corpus_of_top1_chunk` | `dense` | `hybrid_comparison.csv` | `./venv/Scripts/python.exe experiments/exp07_hybrid.py` |
| Top-1 corpus: BNS-named, dense | **42.4%** | [27.2%, 59.2%] | [24.2%, 60.6%] | 33 | `corpus_of_top1_chunk` | `dense` | `hybrid_comparison.csv` | `./venv/Scripts/python.exe experiments/exp07_hybrid.py` |
| Top-1 corpus: BNS-named, BM25 | **84.8%** | [69.1%, 93.3%] | [72.7%, 97.0%] | 33 | `corpus_of_top1_chunk` | `bm25` | `hybrid_comparison.csv` | `./venv/Scripts/python.exe experiments/exp07_hybrid.py` |
| Gold reachability ceiling, pooled | **85.7%** | [82.4%, 88.5%] | no CI | 518 | `retrieved@k` | `n/a` | `hybrid_comparison.csv` | `./venv/Scripts/python.exe experiments/exp07_hybrid.py` |
| Gold reachability ceiling, BNS-named | **33.3%** | [19.8%, 50.4%] | no CI | 33 | `retrieved@k` | `n/a` | `hybrid_comparison.csv` | `./venv/Scripts/python.exe experiments/exp07_hybrid.py` |
| Recall@15 generated | **0.692** | [0.624, 0.752] | [0.647, 0.735] | 198 | `retrieved@k` | `raw_15` | `retrieval_metrics.csv` | `./venv/Scripts/python.exe experiments/exp01_retrieval.py` |
| Recall@15 paired_recodification | **0.737** | [0.643, 0.814] | [0.687, 0.798] | 99 | `retrieved@k` | `raw_15` | `retrieval_metrics.csv` | `./venv/Scripts/python.exe experiments/exp01_retrieval.py` |
| Recall@15 paired_dated_conflict | **0.492** | [0.423, 0.562] | [0.437, 0.543] | 197 | `retrieved@k` | `raw_15` | `retrieval_metrics.csv` | `./venv/Scripts/python.exe experiments/exp01_retrieval.py` |
| Recall@15 layman | **0.150** | [0.097, 0.225] | [0.033, 0.275] | 120 | `retrieved@k` | `raw_15` | `retrieval_metrics.csv` | `./venv/Scripts/python.exe experiments/exp01_retrieval.py` |
| Recall@15 pooled | **0.530** | [0.491, 0.569] | [0.483, 0.576] | 617 | `retrieved@k` | `raw_15` | `retrieval_metrics.csv` | `./venv/Scripts/python.exe experiments/exp01_retrieval.py` |
| AUROC max_score | **0.7837** | [0.7470, 0.8195] | [0.7316, 0.8312] | 617 | `retrieved@k` | `raw_15` | `ablation.csv` | `./venv/Scripts/python.exe experiments/exp04_ablation.py` |
| AUROC top_k_mean | **0.7571** | [0.7188, 0.7939] | [0.7024, 0.8075] | 617 | `retrieved@k` | `raw_15` | `ablation.csv` | `./venv/Scripts/python.exe experiments/exp04_ablation.py` |
| AUROC score_gap (raw) | **0.7298** | [0.6894, 0.7684] | [0.6743, 0.7813] | 617 | `retrieved@k` | `raw_15` | `ablation.csv` | `./venv/Scripts/python.exe experiments/exp04_ablation.py` |
| AUROC composite (deployed) | **0.6631** | [0.6172, 0.7096] | [0.6047, 0.7212] | 617 | `retrieved@k` | `raw_15` | `ablation.csv` | `./venv/Scripts/python.exe experiments/exp04_ablation.py` |
| AUROC entity_coverage | **0.5806** | [0.5376, 0.6232] | [0.5435, 0.6183] | 617 | `retrieved@k` | `raw_15` | `ablation.csv` | `./venv/Scripts/python.exe experiments/exp04_ablation.py` |
| AUROC gap_term (deployed, inverted) | **0.2702** | [0.2316, 0.3106] | [0.2187, 0.3257] | 617 | `retrieved@k` | `raw_15` | `ablation.csv` | `./venv/Scripts/python.exe experiments/exp04_ablation.py` |
| AUROC composite, sign-corrected | **0.7207** | [0.6765, 0.7640] | [0.6666, 0.7717] | 617 | `retrieved@15 (raw_15)` | `raw_15` | `corrected_composite.csv` | `./venv/Scripts/python.exe experiments/exp09_corrected_composite.py` |
| Paired diff: corrected - max_score | **-0.0630** | [-0.0946, -0.0325] | no CI | 617 | `retrieved@15 (raw_15)` | `raw_15` | `corrected_composite.csv` | `./venv/Scripts/python.exe experiments/exp09_corrected_composite.py` |
| Paired diff: corrected - deployed | **0.0576** | [0.0376, 0.0780] | no CI | 617 | `retrieved@15 (raw_15)` | `raw_15` | `corrected_composite.csv` | `./venv/Scripts/python.exe experiments/exp09_corrected_composite.py` |
| Paired diff: deployed - max_score | **-0.1207** | [-0.1623, -0.0798] | no CI | 617 | `retrieved@15 (raw_15)` | `raw_15` | `corrected_composite.csv` | `./venv/Scripts/python.exe experiments/exp09_corrected_composite.py` |
| Best corrected weighting, held out | **0.7631** | no CI | no CI | 247 | `retrieved@15 (raw_15)` | `raw_15` | `corrected_composite.csv` | `./venv/Scripts/python.exe experiments/exp09_corrected_composite.py` |
| ECE composite (lower better) | **0.2410** | [0.2016, 0.2695] | [0.1983, 0.2737] | 617 | `retrieved@k` | `raw_15` | `calibration.csv` | `./venv/Scripts/python.exe experiments/exp03_calibration.py` |
| ECE max_score (lower better) | **0.1270** | [0.1065, 0.1681] | [0.0991, 0.1724] | 617 | `retrieved@k` | `raw_15` | `calibration.csv` | `./venv/Scripts/python.exe experiments/exp03_calibration.py` |
| Coverage at 10% risk, composite | **0.0000** | no CI | no CI | 617 | `retrieved@k` | `raw_15` | `calibration.csv` | `./venv/Scripts/python.exe experiments/exp03_calibration.py` |
| Coverage at 10% risk, max_score | **0.0486** | no CI | no CI | 617 | `retrieved@k` | `raw_15` | `calibration.csv` | `./venv/Scripts/python.exe experiments/exp03_calibration.py` |
| Over-representation CrPC, raw_15 | **1.49x** | [1.35, 1.62] | [1.22, 1.75] | 1800 | `retrieval_share/index_share` | `raw_15` | `routing_confusion.csv` | `./venv/Scripts/python.exe experiments/exp02_routing.py` |
| Over-representation CrPC, filtered_n | **1.80x** | [1.65, 1.93] | [1.47, 2.04] | 608 | `retrieval_share/index_share` | `filtered_n` | `routing_confusion.csv` | `./venv/Scripts/python.exe experiments/exp02_routing.py` |
| Over-representation BNS, raw_15 | **0.58x** | [0.47, 0.69] | [0.37, 0.81] | 1800 | `retrieval_share/index_share` | `raw_15` | `routing_confusion.csv` | `./venv/Scripts/python.exe experiments/exp02_routing.py` |
| Over-representation BNS, filtered_n | **0.34x** | [0.25, 0.44] | [0.18, 0.55] | 608 | `retrieval_share/index_share` | `filtered_n` | `routing_confusion.csv` | `./venv/Scripts/python.exe experiments/exp02_routing.py` |
| statute_consistency, pooled | **0.6845** | [0.6557, 0.7139] | [0.6585, 0.7089] | 617 | `retrieved@k` | `raw_15` | `statute_consistency.csv` | `./venv/Scripts/python.exe experiments/exp06_statute_consistency.py` |
| statute_consistency, dated-conflict | **0.8300** | [0.7819, 0.8750] | [0.7973, 0.8667] | 197 | `retrieved@k` | `raw_15` | `statute_consistency.csv` | `./venv/Scripts/python.exe experiments/exp06_statute_consistency.py` |
| IPC-BNS gap, retrieved@15 | **0.5455** | [0.3477, 0.7368] | [0.3030, 0.7576] | 66 | `retrieved@15` | `raw_15` | `robustness.csv` | `./venv/Scripts/python.exe experiments/exp05_robustness.py` |
| IPC-BNS gap, cited | **-0.0303** | [-0.1600, 0.0956] | [-0.1212, 0.0606] | 66 | `cited` | `n/a` | `robustness.csv` | `./venv/Scripts/python.exe experiments/exp05_robustness.py` |
| IPC-BNS gap, grounded | **-0.0303** | [-0.1000, 0.0000] | [-0.0909, 0.0000] | 66 | `grounded` | `n/a` | `robustness.csv` | `./venv/Scripts/python.exe experiments/exp05_robustness.py` |
| Layman rate, raw_15 | **0.150** | [0.092, 0.217] | [0.033, 0.275] | 120 | `retrieved@15` | `raw_15` | `robustness.csv` | `./venv/Scripts/python.exe experiments/exp05_robustness.py` |
| Layman rate, filtered_n | **0.075** | [0.033, 0.125] | [0.000, 0.167] | 120 | `retrieved@15` | `filtered_n` | `robustness.csv` | `./venv/Scripts/python.exe experiments/exp05_robustness.py` |

**Not listed here because it is not in any CSV:** the term-frequency and inverse-document-frequency evidence for statutory self-naming, which exists only as prose in `results/EXPLAIN.md`. It must be written to a results file before the paper cites it.