"""Evaluate the XGBoost maternal-risk model BEFORE wiring it into HealthConnect.

Run:  pip install -r requirements-ml.txt   then   python evaluate_model.py
Data: Kaggle "Maternal Health Risk" (1,014 rows, collected in Bangladesh).

Questions this answers:
  1. Is the data clean? (duplicates, units, class balance)
  2. How accurate does the model look the "quick" way most tutorials do it?
  3. How accurate is it when tested honestly (no duplicate rows leaking into the test)?
  4. Does it catch HIGH-risk mothers better than a simple blood-pressure rule?
"""
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from xgboost import XGBClassifier

LABELS = ["low risk", "mid risk", "high risk"]  # 0, 1, 2
FEATURES_APP = ["Age", "SystolicBP", "DiastolicBP", "BodyTemp", "HeartRate"]  # what the old model.pkl used
FEATURES_ALL = FEATURES_APP + ["BS"]  # + blood sugar


def make_model():
    return XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.1, eval_metric="mlogloss", random_state=0)


def scores(y_true, y_pred):
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, average="macro"),
        "high_recall": recall_score(y_true, y_pred, labels=[2], average="macro"),  # of real HIGH, how many caught
    }


def cross_validate(X, y, folds=5):
    """Every row is tested exactly once, by a model that never saw it."""
    preds = np.zeros_like(y)
    for train_idx, test_idx in StratifiedKFold(folds, shuffle=True, random_state=0).split(X, y):
        model = make_model().fit(X[train_idx], y[train_idx])
        preds[test_idx] = model.predict(X[test_idx])
    return scores(y, preds), confusion_matrix(y, preds)


def show(title, s):
    print(f"  {title:52} accuracy {s['accuracy']:.0%} | macro-F1 {s['macro_f1']:.2f} | HIGH-risk recall {s['high_recall']:.0%}")


df = pd.read_csv("data/Maternal Health Risk Data Set.csv", encoding="utf-8-sig")
df["y"] = df["RiskLevel"].map({label: i for i, label in enumerate(LABELS)})

print("1. DATA CHECK")
dupes = int(df.duplicated(subset=FEATURES_ALL + ["RiskLevel"]).sum())
print(f"  rows: {len(df)} | exact duplicate rows: {dupes} ({dupes / len(df):.0%}) | unique rows: {len(df) - dupes}")
print(f"  classes: {df['RiskLevel'].value_counts().to_dict()}")
print(f"  BodyTemp range: {df['BodyTemp'].min()}-{df['BodyTemp'].max()}  -> Fahrenheit (the app records Celsius)")
print("  missing for HealthConnect: haemoglobin, gestational age, previous complications")

print("\n2. QUICK WAY (random 80/20 split, duplicates kept)")
X, y = df[FEATURES_APP].to_numpy(), df["y"].to_numpy()
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=0, stratify=y)
quick = scores(y_te, make_model().fit(X_tr, y_tr).predict(X_te))
train_rows = {tuple(r) for r in X_tr}
leaked = np.mean([tuple(r) in train_rows for r in X_te])
show("XGBoost, 5 app features", quick)
print(f"  -> {leaked:.0%} of test rows also appear in the training data (the model has seen the answers)")

print("\n3. HONEST WAY (duplicates removed, 5-fold cross-validation)")
clean = df.drop_duplicates(subset=FEATURES_ALL + ["RiskLevel"]).reset_index(drop=True)
yc = clean["y"].to_numpy()
honest_app, cm = cross_validate(clean[FEATURES_APP].to_numpy(), yc)
honest_all, _ = cross_validate(clean[FEATURES_ALL].to_numpy(), yc)
show("XGBoost, 5 app features", honest_app)
show("XGBoost, 6 features (+ blood sugar)", honest_all)
print("  confusion matrix, 5 features (rows = real low/mid/high, columns = predicted):")
for label, row in zip(LABELS, cm):
    print(f"    {label:10} {row}")

print("\n4. SIMPLE RULE FOR COMPARISON (BP >= 140/90 -> HIGH, like HealthConnect's antenatal rule)")
rule_high = ((clean["SystolicBP"] >= 140) | (clean["DiastolicBP"] >= 90)).to_numpy()
rule_recall = rule_high[yc == 2].mean()
rule_false = rule_high[yc != 2].mean()
print(f"  catches {rule_recall:.0%} of real HIGH-risk mothers, but flags {rule_false:.0%} of the others as HIGH")
