# JalRakshak risk formula

The risk score is a **transparent, deterministic, monotone** index (0–100) computed per ward from
free open data. Code: `jalrakshak/risk/scoring.py` (pure functions, fully unit-tested in
`tests/test_scoring.py`). It is decision support, not an official IMD/CWC warning.

## Inputs (per ward)

| Input | Source | Definition |
|---|---|---|
| `rain_24h_mm` | Open-Meteo Forecast (hourly `precipitation`) | max rolling 24 h sum within the next 72 h |
| `rain_72h_mm` | same | total of the next 72 h |
| `max_intensity_mmph` | same | max hourly rate within the next 72 h |
| `antecedent_7d_mm` | same (`past_days=7`) | observed rain of the past 168 h |
| `discharge_ratio` | Open-Meteo Flood API (GloFAS `river_discharge`) | forecast peak (today..+2 days) / danger threshold |
| `vulnerability` | synthetic ward attribute | 0..1 (low-lying, drainage, informal housing) |

## Components (0..1)

```
r24 = piecewise(rain_24h; 15.6→0, 64.5→0.35, 115.6→0.65, 204.4→1.0)   # IMD moderate/heavy/very heavy/extremely heavy
ri  = piecewise(max_intensity; 10 mm/h→0, 50 mm/h→1)
r72 = piecewise(rain_72h; 64.5→0, 300→1)
R   = min(1, max(r24, 0.8·ri) + 0.15·r72)                 # rain
D   = clamp((peak/danger − 0.5) / 0.7)                     # river; 0 if the city has no gauge
A   = clamp(antecedent_7d / 200)                           # antecedent wetness
V   = ward vulnerability
```

## Score

```
H     = 1 − (1 − R)(1 − D)                                 # hazard: rain OR river can each be severe
score = 100 · (0.75·H + 0.10·A + 0.15·V) · (0.6 + 0.4·V)
```

The noisy-OR hazard lets rain-only cities (e.g. Mumbai, which has no meaningful GloFAS cell)
reach red on extreme rain, and lets a river in spate drive risk even on a dry day.
The `(0.6 + 0.4·V)` multiplier means the same hazard matters more in vulnerable wards.

### Hard river rules (floors, `score = max(score, floor)`)

| Condition | Floor |
|---|---|
| peak ≥ danger (any ward) | 30 |
| peak ≥ warning and V ≥ 0.5 | 55 (orange) |
| peak ≥ danger and V ≥ 0.5 | 75 (red) |
| peak ≥ extreme and V ≥ 0.5 | 85 |

### Levels

green < 30 ≤ yellow < 55 ≤ orange < 75 ≤ red.

### Monotonicity

Every component is a non-decreasing function of its input, the score is a positive combination
of non-decreasing terms, and the floors are non-decreasing step functions of discharge and
vulnerability. Hence the score never decreases when rain, discharge, antecedent rain or
vulnerability increase (property-tested over a grid).

### Horizon, city risk, explanation

* **Horizon** (24 points, 3-hourly over 72 h): at each time *t* the score uses trailing 24 h /
  72 h sums and the max hourly rate of the trailing 6 h ending at *t*, plus GloFAS discharge
  linearly interpolated at *t*; the city horizon is the max over wards.
* **City risk** = the max ward risk; `peak_time` = time of the highest horizon point.
* **Explanation**: one deterministic sentence naming the IMD rain category, river % of danger,
  antecedent rain and ward vulnerability, plus a note when a hard rule fired.
* **`ml_probability`**: optional LightGBM P(flood-day) from `jalrakshak.ml.predict`, shown
  alongside but never used in the score.

## River gauges and thresholds

`scripts/find_gauges.py` probes a 3×3 or 5×5 grid (0.05°, GloFAS resolution) around a known point
on each city's main river, keeps the cell with the largest 2023 mean discharge, and derives
thresholds from GloFAS reanalysis daily discharge 1995–2024 (≈10 200 days available):
**warning = P90, danger = P98, extreme = P99.7**. Cells with P98 < 50 m³/s are not meaningful at
GloFAS resolution and are dropped (Mumbai/Mithi → rain-only). Cached in
`jalrakshak/data/gauges.json`, so runtime makes no history calls.

| City | River | Cell (lat, lon) | Warning P90 | Danger P98 | Extreme P99.7 (m³/s) |
|---|---|---|---|---|---|
| Chennai | Adyar | 13.01, 80.24 | 22.6 | 92.0 | 268.6 |
| Guwahati | Brahmaputra | 26.19, 91.64 | 32 960 | 45 548 | 56 749 |
| Patna | Ganga | 25.63, 85.10 | 27 226 | 39 806 | 46 093 |
| Kochi | Periyar | 10.11, 76.30 | 511.9 | 748.0 | 1 083.6 |
| Srinagar | Jhelum | 34.12, 74.70 | 318.9 | 464.0 | 639.7 |
| Kolkata | Hooghly | 22.57, 88.29 | 1 379 | 2 390 | 4 004 |
| Bhubaneswar | Mahanadi (near Cuttack) | 20.43, 85.98 | 6 949 | 13 520 | 23 137 |
| Surat | Tapi | 21.15, 72.77 | 1 640 | 3 710 | 8 228 |
| Hyderabad | Musi | 17.37, 78.53 | 48.4 | 112.0 | 189.1 |
| Pune | Mula-Mutha | 18.53, 73.92 | 166.3 | 648.3 | 1 256.8 |
| Dibrugarh | Brahmaputra | 27.50, 94.82 | 16 710 | 24 265 | 30 877 |
| Mumbai | Mithi | – (dropped, P98 = 35 m³/s) | – | – | – |

GloFAS is a ~5 km global model: absolute values at small urban rivers are indicative only,
which is why thresholds are percentiles of the model's own climatology rather than CWC levels.
