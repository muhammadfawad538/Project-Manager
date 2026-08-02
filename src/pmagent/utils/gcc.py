# Line ending: LF
# Encoding: UTF-8

"""
GCC localization utilities for pmagent.

Covers:
- Hijri calendar conversion (Umm al-Qura for Saudi Arabia)
- Friday-Saturday weekend configuration
- Multi-currency formatting (SAR, AED, QAR, KWD, BHD, OMR, USD)
- Local holiday calendars per GCC country
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Optional

# ── Hijri Calendar ────────────────────────────────────────────────────────────
# Approximate conversion based on the tabular Islamic calendar.
# For production use, replace with the official Umm al-Qura calendar
# from Saudi Arabia (available as JSON from multiple open-source repos).
# This approximation is accurate within ±1-2 days for most dates.

_HIJRI_EPOCH = datetime.date(622, 7, 16)  # July 16, 622 CE (1 Muharram 1 AH)
_HIJRI_YEAR_DAYS = 354.36667  # Average lunar year length


def _is_hijri_leap(year: int) -> bool:
    """Tabular Islamic calendar leap year: years 2, 5, 7, 10, 13, 16, 18, 21, 24, 26, 29."""
    return year % 30 in (2, 5, 7, 10, 13, 16, 18, 21, 24, 26, 29)


def _hijri_month_days(year: int, month: int) -> int:
    """Days in a Hijri month. Dhu al-Hijjah has 30 days in leap years, 29 otherwise."""
    if month == 12 and _is_hijri_leap(year):
        return 30
    return 30 if month % 2 == 1 else 29


def gregorian_to_hijri(date: datetime.date) -> tuple[int, int, int]:
    """Convert Gregorian date to Hijri (year, month, day).

    Uses tabular Islamic calendar approximation.
    For Saudi government use, replace with Umm al-Qura calendar data.
    """
    days_since_epoch = (date - _HIJRI_EPOCH).days
    hijri_year = int(days_since_epoch / _HIJRI_YEAR_DAYS)

    # Find exact Hijri year
    while True:
        year_days = sum(_hijri_month_days(hijri_year, m) for m in range(1, 13))
        if days_since_epoch < year_days:
            break
        days_since_epoch -= year_days
        hijri_year += 1

    # Find month
    month = 1
    while month <= 12:
        month_days = _hijri_month_days(hijri_year, month)
        if days_since_epoch < month_days:
            break
        days_since_epoch -= month_days
        month += 1

    day = days_since_epoch + 1
    return (hijri_year, month, day)


def hijri_to_gregorian(year: int, month: int, day: int) -> datetime.date:
    """Convert Hijri (year, month, day) to Gregorian date."""
    days = 0
    for y in range(1, year):
        days += sum(_hijri_month_days(y, m) for m in range(1, 13))
    for m in range(1, month):
        days += _hijri_month_days(year, m)
    days += day - 1
    return _HIJRI_EPOCH + datetime.timedelta(days=days)


# Hijri month names (Arabic)
HIJRI_MONTHS_AR = [
    "محرم",       # Muharram
    "صفر",         # Safar
    "ربيع الأول",  # Rabi' al-Awwal
    "ربيع الثاني", # Rabi' al-Thani
    "جمادى الأولى", # Jumada al-Ula
    "جمادى الآخرة", # Jumada al-Thani
    "رجب",         # Rajab
    "شعبان",       # Sha'ban
    "رمضان",       # Ramadan
    "شوال",        # Shawwal
    "ذو القعدة",   # Dhu al-Qi'dah
    "ذو الحجة",    # Dhu al-Hijjah
]

# Hijri month names (English)
HIJRI_MONTHS_EN = [
    "Muharram", "Safar", "Rabi' al-Awwal", "Rabi' al-Thani",
    "Jumada al-Ula", "Jumada al-Thani", "Rajab", "Sha'ban",
    "Ramadan", "Shawwal", "Dhu al-Qi'dah", "Dhu al-Hijjah",
]


# ── Weekend Configuration ─────────────────────────────────────────────────────

@dataclass
class WorkWeek:
    """Defines working days for a region.

    Uses Python's weekday() convention: Monday=0, Sunday=6.
    """

    working_days: list[int] = field(default_factory=lambda: [0, 1, 2, 3])  # Mon-Thu
    weekend_days: list[int] = field(default_factory=lambda: [4, 5])  # Fri-Sat

    @property
    def sunday_thursday(self) -> bool:
        """GCC standard: Sunday-Thursday work week (Mon-Thu in Python weekday)."""
        return self.working_days == [0, 1, 2, 3] and self.weekend_days == [4, 5]

    @property
    def monday_friday(self) -> bool:
        """Global standard: Monday-Friday work week."""
        return self.working_days == [0, 1, 2, 3, 4] and self.weekend_days == [5, 6]


# GCC work week: Sunday-Thursday, Friday-Saturday weekend
# Python weekday: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
GCC_WORK_WEEK = WorkWeek(
    working_days=[0, 1, 2, 3],  # Monday through Thursday
    weekend_days=[4, 5],         # Friday and Saturday
    # Note: Sunday (6) is treated as a working day in GCC
)

# Override is_working_day to include Sunday as working for GCC
def _gcc_is_working_day(date: datetime.date) -> bool:
    """GCC: Sun-Thu are working, Fri-Sat are weekend."""
    wd = date.weekday()  # Mon=0 ... Sun=6
    return wd in [0, 1, 2, 3, 6]  # Mon, Tue, Wed, Thu, Sun

# Global work week: Monday-Friday, Saturday-Sunday weekend
GLOBAL_WORK_WEEK = WorkWeek(
    working_days=[0, 1, 2, 3, 4],  # Monday through Friday
    weekend_days=[5, 6],            # Saturday and Sunday
)

# Weekend presets per GCC country
WEEKEND_PRESETS: dict[str, WorkWeek] = {
    "SA": GCC_WORK_WEEK,   # Saudi Arabia — Sun-Thu
    "AE": GCC_WORK_WEEK,   # UAE — Sun-Thu
    "QA": GCC_WORK_WEEK,   # Qatar — Sun-Thu
    "KW": GCC_WORK_WEEK,   # Kuwait — Sun-Thu
    "BH": GCC_WORK_WEEK,   # Bahrain — Sun-Thu
    "OM": GCC_WORK_WEEK,   # Oman — Sun-Thu
    "US": GLOBAL_WORK_WEEK, # Global fallback — Mon-Fri
}


def is_working_day(date: datetime.date, work_week: WorkWeek = GCC_WORK_WEEK) -> bool:
    """Check if a date is a working day."""
    return date.weekday() in work_week.working_days


def next_working_day(date: datetime.date, work_week: WorkWeek = GCC_WORK_WEEK) -> datetime.date:
    """Find the next working day from a given date."""
    while date.weekday() not in work_week.working_days:
        date += datetime.timedelta(days=1)
    return date


def add_working_days(date: datetime.date, days: int, work_week: WorkWeek = GCC_WORK_WEEK) -> datetime.date:
    """Add N working days to a date, skipping weekends."""
    current = date
    added = 0
    while added < days:
        current += datetime.timedelta(days=1)
        if current.weekday() in work_week.working_days:
            added += 1
    return current


# ── Local Holidays ────────────────────────────────────────────────────────────

@dataclass
class Holiday:
    """A public holiday in a GCC country."""

    name_ar: str
    name_en: str
    date: datetime.date  # Fixed date or representative date for movable holidays
    country: str
    movable: bool = False  # True if date varies by Hijri year


# GCC public holidays (fixed dates and representative dates for movable ones)
# For movable holidays (Eid, Hajj), this provides the most common date;
# production should use Umm al-Qura calendar for accuracy.
_GCC_HOLIDAYS: list[Holiday] = [
    # Saudi Arabia
    Holiday("يوم التأسيس", "Founding Day", datetime.date(2024, 2, 22), "SA"),
    Holiday("يوم العلم", "Saudi Flag Day", datetime.date(2024, 3, 11), "SA"),
    Holiday("العيد الوطني", "Saudi National Day", datetime.date(2024, 9, 23), "SA"),
    # UAE
    Holiday("رأس السنة", "New Year's Day", datetime.date(2024, 1, 1), "AE"),
    Holiday("عيد الفطر", "Eid al-Fitr", datetime.date(2024, 4, 10), "AE", movable=True),
    Holiday("عيد الأضحى", "Eid al-Adha", datetime.date(2024, 6, 17), "AE", movable=True),
    Holiday("رأس السنة الهجرية", "Islamic New Year", datetime.date(2024, 7, 8), "AE", movable=True),
    Holiday("اليوم الوطني", "UAE National Day", datetime.date(2024, 12, 2), "AE"),
    # Qatar
    Holiday("اليوم الوطني", "Qatar National Day", datetime.date(2024, 12, 18), "QA"),
    Holiday("يوم الرياضة", "Sports Day", datetime.date(2024, 2, 13), "QA"),
    # Kuwait
    Holiday("اليوم الوطني", "Kuwait National Day", datetime.date(2024, 2, 25), "KW"),
    Holiday("يوم التحرير", "Liberation Day", datetime.date(2024, 2, 26), "KW"),
    # Bahrain
    Holiday("رأس السنة", "New Year's Day", datetime.date(2024, 1, 1), "BH"),
    Holiday("اليوم الوطني", "Bahrain National Day", datetime.date(2024, 12, 16), "BH"),
    Holiday("يوم الشهداء", "Martyrs' Day", datetime.date(2024, 12, 17), "BH"),
    # Oman
    Holiday("رأس السنة", "New Year's Day", datetime.date(2024, 1, 1), "OM"),
    Holiday("اليوم الوطني", "Oman National Day", datetime.date(2024, 11, 18), "OM"),
    Holiday("عيد النهضة", "Renaissance Day", datetime.date(2024, 7, 23), "OM"),
]


def get_holidays(country: str, year: int) -> list[Holiday]:
    """Return holidays for a given country and year.

    For movable holidays (Eid, Hajj, Islamic New Year), this returns
    representative dates. Production should use Umm al-Qura calendar
    data for accurate Hijri-based dates.
    """
    return [h for h in _GCC_HOLIDAYS if h.country == country]


def is_holiday(date: datetime.date, country: str = "SA") -> bool:
    """Check if a date is a public holiday in the given country."""
    return any(h.date == date for h in get_holidays(country, date.year))


def is_non_working_day(date: datetime.date, work_week: WorkWeek = GCC_WORK_WEEK, country: str = "SA") -> bool:
    """Check if a date is a weekend or public holiday."""
    return date.weekday() in work_week.weekend_days or is_holiday(date, country)


# ── Multi-Currency Formatting ─────────────────────────────────────────────────

# GCC currencies with symbol, Arabic name, and decimal precision
CURRENCIES: dict[str, dict] = {
    "SAR": {"symbol": "﷼", "name_en": "Saudi Riyal", "name_ar": "ريال سعودي", "decimals": 2},
    "AED": {"symbol": "د.إ", "name_en": "UAE Dirham", "name_ar": "درهم إماراتي", "decimals": 2},
    "QAR": {"symbol": "﷼", "name_en": "Qatari Riyal", "name_ar": "ريال قطري", "decimals": 2},
    "KWD": {"symbol": "ك.د", "name_en": "Kuwaiti Dinar", "name_ar": "دينار كويتي", "decimals": 3},
    "BHD": {"symbol": "د.ب", "name_en": "Bahraini Dinar", "name_ar": "دينار بحريني", "decimals": 3},
    "OMR": {"symbol": "﷼", "name_en": "Omani Rial", "name_ar": "ريال عماني", "decimals": 3},
    "USD": {"symbol": "$", "name_en": "US Dollar", "name_ar": "دولار أمريكي", "decimals": 2},
}

DEFAULT_CURRENCY = "SAR"


def format_currency(amount: float, currency: str = DEFAULT_CURRENCY, locale: str = "en") -> str:
    """Format a number as a currency string.

    Args:
        amount: The amount to format
        currency: ISO currency code (SAR, AED, QAR, KWD, BHD, OMR, USD)
        locale: "en" or "ar" for language

    Returns:
        Formatted string like "1,500.00 ﷼" or "١,٥٠٠.٠٠ ﷼"
    """
    curr = CURRENCIES.get(currency.upper(), CURRENCIES["USD"])
    decimals = curr["decimals"]
    symbol = curr["symbol"]

    if locale == "ar":
        # Arabic-Indic digits
        formatted = f"{amount:,.{decimals}f}"
        arabic_digits = str.maketrans("0123456789.", "٠١٢٣٤٥٦٧٨٩٫")
        formatted = formatted.translate(arabic_digits)
        return f"{formatted} {symbol}"
    else:
        return f"{curr['symbol'] if locale == 'en' else symbol} {amount:,.{decimals}f}"


# ── GCC Country Config ────────────────────────────────────────────────────────

@dataclass
class GCCCountryConfig:
    """Configuration for a GCC country."""

    code: str
    name_en: str
    name_ar: str
    currency: str
    weekend: WorkWeek
    vat_rate: float = 0.0
    vat_enabled: bool = False
    date_format: str = "%Y-%m-%d"  # Gregorian
    hijri_date_format: str = "%Y/%m/%d"  # Hijri


GCC_COUNTRIES: dict[str, GCCCountryConfig] = {
    "SA": GCCCountryConfig(
        code="SA", name_en="Saudi Arabia", name_ar="المملكة العربية السعودية",
        currency="SAR", weekend=GCC_WORK_WEEK, vat_rate=0.05, vat_enabled=True,
    ),
    "AE": GCCCountryConfig(
        code="AE", name_en="United Arab Emirates", name_ar="الإمارات العربية المتحدة",
        currency="AED", weekend=GCC_WORK_WEEK, vat_rate=0.05, vat_enabled=True,
    ),
    "QA": GCCCountryConfig(
        code="QA", name_en="Qatar", name_ar="دولة قطر",
        currency="QAR", weekend=GCC_WORK_WEEK, vat_rate=0.0, vat_enabled=False,
    ),
    "KW": GCCCountryConfig(
        code="KW", name_en="Kuwait", name_ar="دولة الكويت",
        currency="KWD", weekend=GCC_WORK_WEEK, vat_rate=0.0, vat_enabled=False,
    ),
    "BH": GCCCountryConfig(
        code="BH", name_en="Bahrain", name_ar="مملكة البحرين",
        currency="BHD", weekend=GCC_WORK_WEEK, vat_rate=0.0, vat_enabled=False,
    ),
    "OM": GCCCountryConfig(
        code="OM", name_en="Oman", name_ar="سلطنة عمان",
        currency="OMR", weekend=GCC_WORK_WEEK, vat_rate=0.0, vat_enabled=False,
    ),
}


def get_country_config(country_code: str) -> GCCCountryConfig:
    """Get configuration for a GCC country. Defaults to Saudi Arabia."""
    return GCC_COUNTRIES.get(country_code.upper(), GCC_COUNTRIES["SA"])


def format_vat(amount: float, vat_rate: float, currency: str = "SAR") -> dict:
    """Calculate VAT breakdown for a given amount.

    Returns dict with subtotal, vat_amount, total, and formatted strings.
    """
    vat_amount = round(amount * vat_rate, 2)
    total = round(amount + vat_amount, 2)
    return {
        "subtotal": amount,
        "vat_rate": vat_rate,
        "vat_amount": vat_amount,
        "total": total,
        "subtotal_formatted": format_currency(amount, currency),
        "vat_formatted": format_currency(vat_amount, currency),
        "total_formatted": format_currency(total, currency),
    }
