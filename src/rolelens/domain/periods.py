"""Date-window helpers using data dates rather than wall-clock time."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class DateWindow:
    start: date
    end: date


def month_start(value: date) -> date:
    return value.replace(day=1)


def shift_months(value: date, months: int) -> date:
    absolute = value.year * 12 + value.month - 1 + months
    return date(absolute // 12, absolute % 12 + 1, 1)


def recent_three_months(data_as_of: date) -> DateWindow:
    return DateWindow(start=shift_months(month_start(data_as_of), -2), end=data_as_of)


def previous_three_months(data_as_of: date) -> DateWindow:
    current_start = recent_three_months(data_as_of).start
    return DateWindow(start=shift_months(current_start, -3), end=current_start - timedelta(days=1))


def current_quarter(data_as_of: date) -> DateWindow:
    quarter_month = ((data_as_of.month - 1) // 3) * 3 + 1
    return DateWindow(start=date(data_as_of.year, quarter_month, 1), end=data_as_of)
