"""Core sampling logic.

A sampler that produces a deterministic keep/drop decision for a given
trace_id by hashing the id and comparing the resulting ratio in [0, 1)
against a configured sampling rate.

Design choices
--------------
* SHA-256 is used for the hash because it is in the Python standard library
  and has a uniform enough distribution across the low-order bits for this
  use.  Only the first eight bytes of the digest are converted into an
  unsigned integer; that is already far more precision than the sampling
  threshold needs and keeps the computation cheap.
* The hash-to-ratio conversion divides by 2**64 so that the ratio lives in
  the half-open interval [0, 1).  A ratio of exactly 0 is therefore
  possible (a zero hash) while a ratio of exactly 1 is not, which means a
  rate of 1.0 keeps every trace and a rate of 0.0 drops every trace.
* Empty trace ids are rejected explicitly.  Allowing them would make a
  blank id always hash to the same value, silently biasing the sample.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SamplingDecision:
    """The outcome of a sampling check.

    ``kept`` is the boolean decision the caller should act on.  ``ratio``
    is the [0, 1) value derived from the trace_id hash; it is exposed so
    that callers can build consistent rate tiers (e.g. keep at 1% OR keep
    if already kept at 10%) without re-hashing.
    """

    kept: bool
    ratio: float


class TraceSampler:
    """Deterministic per-trace sampler.

    Parameters
    ----------
    rate:
        Sampling rate in the closed interval [0, 1].  A rate of 0.0 drops
        every trace; 1.0 keeps every trace.

    Raises
    ------
    ValueError
        If ``rate`` is NaN, infinite, or outside [0, 1].
    """

    __slots__ = ("_rate",)

    def __init__(self, rate: float) -> None:
        # math.isnan / math.isinf reject NaN and infinities.  Plain range
        # checks would silently accept NaN because every comparison with
        # NaN returns False, so these guards must come first.
        if math.isnan(rate) or math.isinf(rate):
            raise ValueError("rate must be a finite number")
        if not 0.0 <= rate <= 1.0:
            raise ValueError("rate must be in [0, 1]")
        self._rate = rate

    @property
    def rate(self) -> float:
        return self._rate

    def _ratio_for(self, trace_id: str) -> float:
        """Return the [0, 1) hash ratio for ``trace_id``."""
        if not isinstance(trace_id, str):
            raise TypeError("trace_id must be a string")
        if trace_id == "":
            raise ValueError("trace_id must not be empty")
        digest = hashlib.sha256(trace_id.encode("utf-8")).digest()
        # Take the leading eight bytes as a big-endian unsigned integer.
        # Dividing by 2**64 maps it into [0, 1).
        value = int.from_bytes(digest[:8], "big", signed=False)
        return value / (2**64)

    def decide(self, trace_id: str) -> SamplingDecision:
        """Return a :class:`SamplingDecision` for ``trace_id``."""
        ratio = self._ratio_for(trace_id)
        return SamplingDecision(kept=ratio < self._rate, ratio=ratio)

    def should_keep(self, trace_id: str) -> bool:
        """Convenience boolean wrapper around :meth:`decide`."""
        return self.decide(trace_id).kept
