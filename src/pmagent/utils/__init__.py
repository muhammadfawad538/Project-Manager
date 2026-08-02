# Line ending: LF
# Encoding: UTF-8

"""
pmagent.utils — GCC localization utilities.

Hijri calendar, weekend config, multi-currency formatting, VAT calculation.
"""

from pmagent.utils.gcc import (
    gregorian_to_hijri,
    hijri_to_gregorian,
    add_working_days,
    next_working_day,
    is_holiday,
    is_non_working_day,
    format_currency,
    format_vat,
    get_country_config,
    GCC_WORK_WEEK,
    GLOBAL_WORK_WEEK,
    WEEKEND_PRESETS,
    CURRENCIES,
    HIJRI_MONTHS_AR,
    HIJRI_MONTHS_EN,
    WorkWeek,
)


def is_working_day(date, work_week=GCC_WORK_WEEK) -> bool:
    """Check if a date is a working day.

    GCC: Sun-Thu working, Fri-Sat weekend.
    Global: Mon-Fri working, Sat-Sun weekend.
    """
    if hasattr(work_week, "sunday_thursday") and work_week.sunday_thursday:
        # GCC: Sun(6), Mon(0), Tue(1), Wed(2), Thu(3) are working
        return date.weekday() in (0, 1, 2, 3, 6)
    # Global: Mon(0) through Fri(4)
    return date.weekday() in (0, 1, 2, 3, 4)


__all__ = [
    "gregorian_to_hijri",
    "hijri_to_gregorian",
    "is_working_day",
    "add_working_days",
    "next_working_day",
    "is_holiday",
    "is_non_working_day",
    "format_currency",
    "format_vat",
    "get_country_config",
    "GCC_WORK_WEEK",
    "GLOBAL_WORK_WEEK",
    "WEEKEND_PRESETS",
    "CURRENCIES",
    "HIJRI_MONTHS_AR",
    "HIJRI_MONTHS_EN",
    "WorkWeek",
]
