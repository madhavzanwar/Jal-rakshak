"""Pure time-series helpers: rainfall window features, discharge interpolation, gauge readings.

Conventions: hourly rain is a list aligned with ISO-UTC hour stamps; ``now_idx`` is the index
of the current hour. The forward 72 h window is ``[now_idx, now_idx + 72)``; antecedent rain is
the observed 168 h before ``now_idx``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from jalrakshak.models import DischargePoint, GaugeReading, RiverGauge
from jalrakshak.risk.thresholds import gauge_status

HORIZON_H = 72
STEP_H = 3
ANTECEDENT_H = 168


@dataclass(frozen=True)
class RainFeatures:
    rain_24h_mm: float
    rain_72h_mm: float
    max_intensity_mmph: float
    antecedent_7d_mm: float


def _window(mm: Sequence[float], start: int, end: int) -> list[float]:
    return [float(x) for x in mm[max(start, 0) : max(end, 0)]]


def max_rolling_sum(values: Sequence[float], width: int) -> float:
    """Maximum sum over any ``width``-long contiguous window (whole sum if shorter)."""
    if len(values) <= width:
        return float(sum(values))
    cur = best = float(sum(values[:width]))
    for i in range(width, len(values)):
        cur += values[i] - values[i - width]
        best = max(best, cur)
    return best


def forward_features(mm: Sequence[float], now_idx: int) -> RainFeatures:
    """Features for the next 72 h (max rolling 24 h, 72 h total, peak hour) + past 7 days."""
    win = _window(mm, now_idx, now_idx + HORIZON_H)
    past = _window(mm, now_idx - ANTECEDENT_H, now_idx)
    return RainFeatures(
        rain_24h_mm=max_rolling_sum(win, 24),
        rain_72h_mm=float(sum(win)),
        max_intensity_mmph=max(win, default=0.0),
        antecedent_7d_mm=float(sum(past)),
    )


def trailing_features(mm: Sequence[float], t_idx: int, antecedent_7d_mm: float) -> RainFeatures:
    """Conditions *at* hour ``t_idx`` for the horizon: trailing 24 h / 72 h sums and the
    maximum hourly rate over the trailing 6 h. Antecedent is held at its value for "now"."""
    end = t_idx + 1
    return RainFeatures(
        rain_24h_mm=float(sum(_window(mm, end - 24, end))),
        rain_72h_mm=float(sum(_window(mm, end - 72, end))),
        max_intensity_mmph=max(_window(mm, end - 6, end), default=0.0),
        antecedent_7d_mm=antecedent_7d_mm,
    )


def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def fmt_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def now_index(times: Sequence[str], now: datetime) -> int:
    """Index of the hour containing ``now`` (clamped to the series)."""
    if not times:
        return 0
    t0 = parse_ts(times[0])
    idx = int((now - t0).total_seconds() // 3600)
    return max(0, min(idx, len(times) - 1))


def discharge_at(dates: Sequence[str], m3s: Sequence[float], when: datetime) -> float:
    """Daily discharge linearly interpolated at ``when`` (daily values placed at 12:00 UTC)."""
    if not dates:
        return 0.0
    pts = [(parse_ts(d + "T12:00:00Z"), float(v)) for d, v in zip(dates, m3s, strict=False)]
    if when <= pts[0][0]:
        return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:], strict=False):
        if when <= t1:
            frac = (when - t0).total_seconds() / (t1 - t0).total_seconds()
            return v0 + (v1 - v0) * frac
    return pts[-1][1]


def gauge_reading(
    gauge: RiverGauge, dates: Sequence[str], m3s: Sequence[float], now: datetime
) -> GaugeReading:
    """Assemble a GaugeReading: current = today's value, peak = max over today..today+2."""
    today = now.date()
    series = [
        DischargePoint(date=d, m3s=round(float(v), 1)) for d, v in zip(dates, m3s, strict=False)
    ]
    current = next((p.m3s for p in series if p.date == today.isoformat()), None)
    if current is None:
        current = series[-1].m3s if series else 0.0
    horizon_dates = {(today + timedelta(days=k)).isoformat() for k in range(3)}
    window = [p for p in series if p.date in horizon_dates] or series[-1:]
    peak = max(window, key=lambda p: p.m3s) if window else DischargePoint(
        date=today.isoformat(), m3s=0.0
    )
    return GaugeReading(
        gauge=gauge,
        series=series,
        current_m3s=current,
        peak_m3s=peak.m3s,
        peak_date=peak.date,
        status=gauge_status(peak.m3s, gauge),
    )
