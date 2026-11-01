"""2-week outbreak forecast for the GHS dashboard. Simple statistics, NOT machine learning.

For each district and disease:
1. Trend:    average change per week over the last 3 weeks = (this week - 3 weeks ago) / 3
2. Expected: next week = this week + 1 x trend, the week after = this week + 2 x trend (never below 0)
3. Outbreak: the same rule as the alerts (at least 5 cases AND at least double the usual week)
4. Chance:   real counts go up and down by chance around the expected number. The Poisson
             formula (standard maths for "random events per week") gives the chance a week
             reaches the outbreak level. Over 2 weeks: 1 - (no outbreak next week x no outbreak after)

Why not ML: a trained model needs a year or more of real weekly data to learn patterns
such as malaria rising in the rainy season. The demo has 8 weeks of fake data.
"""
import math

TREND_WEEKS = 3


def chance_at_least(level, expected):
    """Poisson: the chance of `level` or more cases in a week when we expect `expected`."""
    if expected <= 0:
        return 0.0
    # Add up the chances of 0, 1, 2, ... (level - 1) cases, then take the rest
    term = math.exp(-expected)  # chance of exactly 0 cases
    below = 0.0
    for cases in range(level):
        below += term
        term *= expected / (cases + 1)  # chance of exactly (cases + 1)
    return max(0.0, 1 - below)


def forecast(weekly, outbreak_level):
    """weekly = case counts, newest week first. Returns the next 2 weeks' outlook."""
    trend = (weekly[0] - weekly[TREND_WEEKS]) / TREND_WEEKS
    next_week = max(0.0, weekly[0] + trend)
    week_after = max(0.0, weekly[0] + 2 * trend)
    no_outbreak = (1 - chance_at_least(outbreak_level, next_week)) * (1 - chance_at_least(outbreak_level, week_after))
    return {
        "expected_next_2_weeks": round(next_week + week_after),
        # words, not the exact number: small exact changes could hint at individual cases
        "direction": "rising" if trend >= 0.5 else "falling" if trend <= -0.5 else "steady",
        "chance": round(1 - no_outbreak, 2),  # 0.0 to 1.0
    }
