# TimesFM adapter

A focused walkthrough of `tsa.adapters.to_timesfm()` — the bridge from a messy raw
series to the finite `float32` array Google [TimesFM](https://github.com/google-research/timesfm)
(and similar zero-shot forecasters) expects.

`timesfm_adapter.ipynb` uses the real OGDC `Price` series and shows:

- **audit + repair + format in one call** — a data-feed gap and a fat outlier are cleaned,
  and `return_report=True` hands back the `GuardReport` so the repair isn't a black box;
- **context truncation** — a 1537-row series returns a 1024-point array (the most recent
  `context_len`; TimesFM 2.5 accepts up to 16k);
- **the finiteness guard** — a lone, unflagged NaN survives repair, so the adapter *raises*
  rather than let a NaN silently crash tokenization;
- **the model call** — shown (not executed) so the notebook needs only `tsauditor`.

The adapter adds **no `timesfm` dependency**: it only produces numpy; the model call stays
in your code.

## Run / regenerate

```bash
python examples/timesfm_adapter/build_timesfm_notebook.py
```

Writes and executes `timesfm_adapter.ipynb`; a failure means the example has drifted from
the library.
