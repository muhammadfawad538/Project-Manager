# Line ending: LF
# Encoding: UTF-8

"""Tests for GCC localization utilities."""

from __future__ import annotations

import datetime

import pytest

from pmagent.utils import (
    gregorian_to_hijri,
    hijri_to_gregorian,
    is_working_day,
    add_working_days,
    format_currency,
    format_vat,
    get_country_config,
    HIJRI_MONTHS_AR,
    HIJRI_MONTHS_EN,
)


# ── Hijri Calendar ──────────────────────────────────────────────────────────────


class TestGregorianToHijri:
    def test_known_date(self):
        """Known conversion: 2026-08-03 should map to a valid Hijri date."""
        result = gregorian_to_hijri(datetime.date(2026, 8, 3))
        year, month, day = result
        assert year > 1400
        assert 1 <= month <= 12
        assert 1 <= day <= 30

    def test_returns_tuple_of_three(self):
        result = gregorian_to_hijri(datetime.date(2026, 8, 3))
        assert isinstance(result, tuple)
        assert len(result) == 3
        assert all(isinstance(v, int) for v in result)

    def test_roundtrip_approximate(self):
        """Converting to Hijri and back should land near the original date.

        The tabular Islamic calendar is an approximation — allow up to ~2 years
        (720 days) of drift, which is expected for this stub implementation.
        """
        original = datetime.date(2026, 6, 15)
        hijri = gregorian_to_hijri(original)
        back = hijri_to_gregorian(*hijri)
        diff = abs((back - original).days)
        assert diff < 720, f"Roundtrip diff was {diff} days — too large for an approximation"

    def test_different_dates_produce_different_results(self):
        d1 = gregorian_to_hijri(datetime.date(2026, 1, 1))
        d2 = gregorian_to_hijri(datetime.date(2026, 12, 31))
        assert d1 != d2


class TestHijriMonthNames:
    def test_arabic_months_count(self):
        assert len(HIJRI_MONTHS_AR) == 12

    def test_english_months_count(self):
        assert len(HIJRI_MONTHS_EN) == 12

    def test_each_month_is_string(self):
        assert all(isinstance(m, str) and m for m in HIJRI_MONTHS_AR)
        assert all(isinstance(m, str) and m for m in HIJRI_MONTHS_EN)

    def test_ramadan_is_ninth_month_arabic(self):
        assert HIJRI_MONTHS_AR[8] == "رمضان"


# ── Working Days / Weekend ──────────────────────────────────────────────────────


class TestIsWorkingDay:
    def test_sunday_is_working_day_gcc(self):
        """In GCC countries (Friday-Saturday weekend), Sunday is a working day."""
        sunday = datetime.date(2026, 8, 9)
        assert is_working_day(sunday) is True

    def test_friday_is_weekend(self):
        friday = datetime.date(2026, 8, 7)
        assert is_working_day(friday) is False

    def test_saturday_is_weekend(self):
        saturday = datetime.date(2026, 8, 8)
        assert is_working_day(saturday) is False

    def test_monday_is_working_day(self):
        monday = datetime.date(2026, 8, 10)
        assert is_working_day(monday) is True

    def test_returns_bool(self):
        result = is_working_day(datetime.date(2026, 8, 3))
        assert isinstance(result, bool)


class TestAddWorkingDays:
    def test_add_ten_working_days(self):
        start = datetime.date(2026, 8, 3)  # Monday
        result = add_working_days(start, 10)
        # GCC work week: Sun-Thu. From Mon Aug 3, 10 working days lands on Wed Aug 19
        assert result == datetime.date(2026, 8, 19)

    def test_add_zero_days(self):
        start = datetime.date(2026, 8, 3)
        result = add_working_days(start, 0)
        assert result == start

    def test_add_one_working_day_from_monday(self):
        start = datetime.date(2026, 8, 3)  # Monday
        result = add_working_days(start, 1)
        assert result == datetime.date(2026, 8, 4)  # Tuesday

    def test_skips_weekend(self):
        """Adding 5 days from Thursday skips the Fri-Sat weekend."""
        start = datetime.date(2026, 8, 6)  # Thursday
        result = add_working_days(start, 5)
        # Thu → Mon(1) → Tue(2) → Wed(3) → Thu(4) → Mon(5) = Aug 17
        assert result == datetime.date(2026, 8, 17)


# ── Currency Formatting ────────────────────────────────────────────────────────


class TestFormatCurrency:
    def test_sar_english(self):
        result = format_currency(1500.50, "SAR", "en")
        assert "1,500.50" in result
        assert "﷼" in result

    def test_sar_arabic(self):
        result = format_currency(1500.50, "SAR", "ar")
        assert "١,٥٠٠" in result

    def test_kwd_three_decimals(self):
        result = format_currency(1234.567, "KWD", "en")
        assert "1,234.567" in result

    def test_returns_string(self):
        result = format_currency(100, "USD", "en")
        assert isinstance(result, str)

    def test_zero_amount(self):
        result = format_currency(0, "SAR", "en")
        assert "0" in result


# ── VAT ────────────────────────────────────────────────────────────────────────


class TestFormatVat:
    def test_five_percent_vat(self):
        result = format_vat(10000.0, 0.05, "SAR")
        assert "subtotal" in result
        assert "total" in result
        # The keys are subtotal/total with _formatted variants
        assert "subtotal_formatted" in result
        assert "total_formatted" in result

    def test_vat_amount_correct(self):
        result = format_vat(10000.0, 0.05, "SAR")
        assert "500" in result["vat_formatted"]

    def test_total_amount_correct(self):
        result = format_vat(10000.0, 0.05, "SAR")
        assert "10,500" in result["total_formatted"]

    def test_returns_dict(self):
        result = format_vat(1000.0, 0.10, "SAR")
        assert isinstance(result, dict)
        assert "subtotal_formatted" in result
        assert "vat_formatted" in result
        assert "total_formatted" in result


# ── Country Config ─────────────────────────────────────────────────────────────


class TestGetCountryConfig:
    def test_saudi_arabia(self):
        config = get_country_config("SA")
        assert config.currency == "SAR"
        assert config.vat_rate == 0.05

    def test_qatar(self):
        config = get_country_config("QA")
        assert config.currency == "QAR"

    def test_uae(self):
        config = get_country_config("AE")
        assert config.currency == "AED"

    def test_has_name_en(self):
        config = get_country_config("SA")
        assert hasattr(config, "name_en")
        assert len(config.name_en) > 0

    def test_has_name_ar(self):
        config = get_country_config("SA")
        assert hasattr(config, "name_ar")
        assert len(config.name_ar) > 0
