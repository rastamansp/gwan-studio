"""
F17 — regras puras do pipeline de highlights de futebol.

Sem I/O, sem Django: entra dados, sai dados. Ver
docs/spec/20-features/F17-futebol-highlights.md (RN-F17-02/03).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Interval:
    start: float
    end: float


def filter_by_importance(moments: list[dict], importancia_min: int) -> list[dict]:
    """RN-F17-02 — só entram momentos com importancia >= importancia_min."""
    return [m for m in moments if m.get('importancia', 0) >= importancia_min]


def merge_moments(
    moments: list[dict],
    duration_sec: float,
    pre_roll: float,
    post_roll: float,
    merge_gap: float,
) -> list[Interval]:
    """RN-F17-03 — converte momentos em intervalos de corte, unindo os próximos.

    `start = max(0, timestamp - pre_roll)`, `end = min(duration, timestamp + post_roll)`.
    Intervalos com gap <= merge_gap entre si são unidos em um só.
    """
    if not moments:
        return []

    raw = sorted(
        (
            Interval(
                start=max(0.0, m['timestamp'] - pre_roll),
                end=min(duration_sec, m['timestamp'] + post_roll),
            )
            for m in moments
        ),
        key=lambda i: i.start,
    )

    merged: list[Interval] = [raw[0]]
    for current in raw[1:]:
        last = merged[-1]
        if current.start - last.end <= merge_gap:
            merged[-1] = Interval(start=last.start, end=max(last.end, current.end))
        else:
            merged.append(current)
    return merged
