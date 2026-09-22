from __future__ import annotations

from datetime import date

import pandas as pd

from rolelens.domain.metrics import (
    conversion_rate,
    period_growth,
    rank_values,
    safe_ratio,
    share,
    target_achievement,
)
from rolelens.domain.periods import current_quarter, previous_three_months, recent_three_months


def test_period_windows_use_data_as_of() -> None:
    as_of = date(2026, 9, 15)
    assert recent_three_months(as_of).start == date(2026, 7, 1)
    assert recent_three_months(as_of).end == as_of
    assert previous_three_months(as_of).start == date(2026, 4, 1)
    assert previous_three_months(as_of).end == date(2026, 6, 30)
    assert current_quarter(as_of).start == date(2026, 7, 1)


def test_ratio_functions_handle_zero() -> None:
    assert safe_ratio(1, 0) is None
    assert target_achievement(95, 100) == 95
    assert period_growth(120, 100) == 20
    assert conversion_rate(43, 100) == 43
    assert conversion_rate(1, 0) is None
    assert share(25, 100) == 25
    assert rank_values([30, 10, 20]) == [1, 3, 2]


def test_pandas_is_available_for_deterministic_analysis() -> None:
    frame = pd.DataFrame({"value": [1, 2, 3]})
    assert frame["value"].sum() == 6
