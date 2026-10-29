"""Layer 4: permit-party math.

If each of ``n`` party members applies independently with win probability ``p``,
the chance that at least one wins is ``1 - (1 - p) ** n``. Whether draws are truly
independent depends on each lottery's rules; check before trusting this.
"""


def party_win_probability(p: float, n: int) -> float:
    """Probability that at least one of ``n`` independent applicants wins."""
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"p must be in [0, 1], got {p}")
    if n < 0:
        raise ValueError(f"n must be non-negative, got {n}")
    return 1.0 - (1.0 - p) ** n
