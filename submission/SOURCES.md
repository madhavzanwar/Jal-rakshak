# Sources for numbers used in the submission kits

Every figure on a slide carries a short source label; full references are below. Our own projections are labelled **Estimate** on the slides, with the assumption shown.

## External figures

1. ≈40 Mha (≈12% of land) flood-prone — Rashtriya Barh Ayog (1980), restated by PIB (Ministry of Jal Shakti), 2022  
   <https://pib.gov.in/PressReleasePage.aspx?PRID=1848476>
2. 1,09,374 deaths and ₹4,00,097 crore damage from floods and heavy rain, 1953–2018 — Standing Committee on Water Resources, 17th Lok Sabha, reported by Down To Earth (6 Aug 2021)  
   <https://www.downtoearth.org.in/natural-disasters/floods-heavy-rains-killed-100-000-in-65-years-caused-loss-of-rs-4-lakh-crore-78340>
3. 2.2 million (22 lakh) people affected in 2,542 villages of 28/35 Assam districts as of 26 June 2022; 217,413 people in 564 relief camps — UNICEF India, Assam Floods 2022 Situation Report, 27 June 2022  
   <https://www.unicef.org/media/123376/file/India-Assam-Foods-SitRep-27-June-2022.pdf>
4. 24 hours' warning of a hazard can reduce damage by 30% — Global Commission on Adaptation (2019), cited by the UN Early Warnings for All initiative  
   <https://www.un.org/en/climatechange/early-warnings-for-all>
5. UN Early Warnings for All fact sheet (Aug 2025), same 24 h / 30% figure  
   <https://www.un.org/sites/un2.un.org/files/earlywarnings_fastfacts_2025-08.pdf>
6. Mother-tongue shares, Census 2011 (C-16): Hindi 43.63%, Bengali 8.03%, Marathi 6.86%, Tamil 5.70% (sum ≈64%) — reported by Factly  
   <https://factly.in/a-major-dravidian-language-is-now-the-mother-tongue-of-only-18-9-indians-down-from-23-in-1971>
7. Flood-prone area later revised to 49.8 Mha by the 12th Plan working group — Central Water Commission  
   <https://cwc.gov.in/fm-projects>

## Our estimates (assumptions)

- ≈₹185 crore/yr avoidable damage = 30% damage reduction (GCA) × 10% of flood-exposed households reached (our assumption) × ₹6,150 crore/yr average flood damage (₹4,00,097 crore ÷ 65 years, Standing Committee). Illustrative only; ignores growth in exposure and inflation.
- 5.5 crore residents = sum of the city population figures in our seed data (backend/jalrakshak/data/cities.py) for the 12 cities; ward values are synthetic and labelled as such.

## Product facts

- Risk formula: `backend/RISK_FORMULA.md` and `backend/jalrakshak/risk/scoring.py`.
- Model metrics: `backend/models/backtest.json`, method in `docs/MODEL.md`.
- Ward, population and shelter seed data are synthetic and labelled as such in the app.
