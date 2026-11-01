# ML evaluation: should HealthConnect use the XGBoost risk model?

**Short answer: not yet.** The model was evaluated before wiring it in (PROSIT 2, Week 3). HealthConnect keeps its transparent rule-based checks, and this document explains why.

Reproduce: `cd backend && pip install -r requirements-ml.txt && python evaluate_model.py`

---

## What was evaluated

| Item | Detail |
|---|---|
| Model | XGBoost classifier (200 trees, depth 4), predicting low / mid / high maternal risk |
| Data | Kaggle *Maternal Health Risk* dataset: 1,014 rows, collected in **Bangladesh** |
| Features | Age, systolic BP, diastolic BP, body temperature, heart rate (the 5 the old `train_model.py` used); also tested with blood sugar added |

## Findings

### 1. More than half the data is duplicated
**562 of 1,014 rows (55%) are exact copies**, leaving only **452 unique rows**. Duplicates make a model look better than it is: the same row lands in both the training and the test set.

### 2. The "quick" test is misleading
With a random 80/20 split (the usual tutorial approach), **92% of test rows also appear in the training data**, so the model is graded partly on answers it has memorised.

### 3. Honest performance is weak for a safety decision
Duplicates removed, 5-fold cross-validation (every row tested by a model that never saw it):

| Model | Accuracy | Macro-F1 | HIGH-risk recall |
|---|---|---|---|
| XGBoost, 5 features | 64% | 0.56 | **57%** |
| XGBoost, + blood sugar | 66% | 0.59 | 71% |
| Simple rule: BP ≥ 140/90 → HIGH | – | – | 48% (but 19% of others wrongly flagged) |

**HIGH-risk recall** = of the mothers who really were high-risk, how many the model caught. At 57%, the model **misses about 4 in 10 high-risk mothers**. For a referral decision, a miss can mean a death.

Confusion matrix (5 features; rows = real, columns = predicted):

| real \ predicted | low | mid | high |
|---|---|---|---|
| **low** | 199 | 18 | 17 |
| **mid** | 62 | 27 | 17 |
| **high** | 27 | 21 | 64 |

Mid-risk is mostly confused with low-risk: the model barely learns that class.

### 4. Units don't match the app
The dataset's body temperature is in **Fahrenheit (98–103 °F)**. HealthConnect records **Celsius (~37 °C)**. The old prediction code in `train_model.py` would feed 37 into a model that expects ~98, so every patient would look severely hypothermic and the predictions would be meaningless. *(This code was never wired in, so no patient was affected.)*

### 5. The data doesn't fit our patients or our checks
- **Population:** Bangladesh, not Ghana. Risk patterns (anaemia, malaria in pregnancy, access to care) differ.
- **Missing inputs:** no haemoglobin, gestational age or previous complications, which are central to HealthConnect's antenatal check.
- **Unknown labelling:** how "high risk" was decided is not documented.

## Decision

| Option | Decision |
|---|---|
| Wire XGBoost into the antenatal check now | ❌ No: misses too many high-risk mothers, wrong units, wrong population |
| Keep the rule-based checks | ✅ Yes: transparent, explainable line by line, based on WHO danger signs, same result online and offline |
| Use ML later | ✅ Once HealthConnect has collected **consented, de-identified Ghanaian data**, with ethics approval, and a clinician has reviewed the labels |

## What the PROSIT asks for: predicting outbreaks
The Week 3 brief asks for *"AI/ML disease prediction based on symptom patterns and community data"* and *"predictive analytics for health resource allocation"*: predict **where disease is coming next** from community totals, so GHS can send medicines and supplies **before** an outbreak peaks. This is population-level (district totals), not one patient's risk.

### Built now: a 2-week forecast with statistics (`backend/forecast.py`)
For each district and infectious disease, on the GHS dashboard:
1. **Trend:** average change per week over the last 3 weeks.
2. **Expected cases:** this week + 1 × trend (next week) and + 2 × trend (the week after), never below 0.
3. **Outbreak level:** the same rule as the alerts (≥ 5 cases and ≥ 2× the usual week).
4. **Chance:** the **Poisson** formula (standard maths for counts of random events per week) gives the chance each week reaches the outbreak level; over 2 weeks = 1 − (no outbreak next week × no outbreak the week after).
5. **Supplies:** about 1 test or treatment per expected case. An example ratio, not GHS guidance.

Example from the demo data: *Cholera, Tamale: >99% chance, ~35 cases expected in 2 weeks, prepare ~35 ORS sachets and rapid tests.*

**Why statistics, not ML:** a trained model would only learn our random demo data. Every step here can be explained and checked, and it works with a few weeks of data. **Limits:** it assumes the recent trend continues, cannot know seasons, and small numbers are less certain (the screen says so).

### Planned: trained ML
| Step | Plan |
|---|---|
| Data | At least **1 year** (ideally 2–3) of **real** weekly counts per district from HealthConnect, or historical DHIMS2 data shared by GHS under an agreement |
| Inputs | Recent weekly counts, week of the year (season), rainfall, neighbouring districts' counts |
| Model | Start simple (Poisson regression), then try gradient boosting (e.g. XGBoost) only if it does better |
| Testing | Train on earlier months, test on later months the model never saw (never shuffle time). Compare against the statistics forecast above: ML is used only if it predicts outbreaks better |
| Safety | A forecast supports GHS decisions; people decide. A wrong forecast means extra preparation, not a missed patient |

## Exam points
- **Data leakage:** duplicates or future information in the training set inflate test scores. Always remove duplicates and test on unseen data.
- **Cross-validation:** split the data into k folds; each fold is tested by a model trained on the others. A more reliable score than one random split.
- **Recall over accuracy** for safety: missing a high-risk mother (false negative) is far worse than an extra referral (false positive).
- **Dataset shift:** a model trained on one population (Bangladesh) may not work on another (Ghana).
