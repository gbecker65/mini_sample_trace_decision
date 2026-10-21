# mini_sample_trace_decision

A deterministic sampler that hashes a trace_id and returns a keep-or-drop boolean based on a configurable rate, giving consistent decisions per trace.

```python
from mini_sample_trace_decision import TraceSampler

sampler = TraceSampler(rate=0.1)
if sampler.should_keep("abc-123"):
    # keep this trace
    ...

# or inspect the full decision:
decision = sampler.decide("abc-123")
print(decision.kept, decision.ratio)
```

## Why this exists

Distributed tracing systems need to sample a subset of traces to keep volume manageable. Head sampling — deciding at trace start whether to keep it — is the cheapest place to do that, but it must be deterministic: every span in the same trace must reach the same decision, otherwise the trace is fragmented. This library provides that decision in a single call, keyed on the trace_id, with no external state and no randomness after construction.

The trade-off: this is head sampling only. It cannot dynamically adjust to traffic volume, and it cannot guarantee an exact percentage of traces in a small window — the guarantee is statistical and per-id. For exact downstream sampling, use a tail-based processor elsewhere.

## Edge cases

- `rate` must be a finite number in `[0, 1]`; NaN and infinities raise `ValueError`.
- `trace_id` must be a non-empty string; an empty id is rejected because every empty id would hash to the same value and silently bias the sample.
- The keep check is `ratio < rate`, so a rate of `1.0` keeps every trace and a rate of `0.0` drops every trace. There is no id whose ratio equals `1.0` because the ratio lives in the half-open interval `[0, 1)`.
- `SamplingDecision.ratio` is exposed so callers can build tiered sampling (e.g. keep at 1% or keep if already kept at 10%) without re-hashing the id.

## Exports

- `TraceSampler(rate: float)` — construct a sampler. `rate` must be a finite float in `[0, 1]`.
  - `.rate` — the configured rate.
  - `.decide(trace_id: str) -> SamplingDecision` — returns a decision with `kept` and `ratio`.
  - `.should_keep(trace_id: str) -> bool` — convenience wrapper returning `decision.kept`.
- `SamplingDecision` — frozen dataclass with `kept: bool` and `ratio: float`.
