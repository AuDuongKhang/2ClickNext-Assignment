from datetime import date
from decimal import Decimal

import pytest

from imports.parsers import normalize_status, parse_date, parse_datetime, parse_decimal


def test_archive_values_are_normalized_without_turning_empty_into_zero():
    """Removing empty-field handling would turn unknown archive values into values."""
    assert parse_date("01/09/2026") == date(2026, 9, 1)
    assert parse_date("") is None
    assert parse_decimal("12500,00") == Decimal("12500.00")
    assert parse_decimal("") is None
    assert normalize_status(" OPEN ") == "open"


def test_archive_datetime_is_interpreted_in_rome():
    """Removing Rome localization would shift every imported activity instant."""
    parsed = parse_datetime("01/09/2026 09:00")

    assert parsed.isoformat() == "2026-09-01T09:00:00+02:00"


@pytest.mark.parametrize("value", ["2026-09-01", "32/09/2026"])
def test_invalid_archive_date_is_rejected(value):
    """Permitting malformed dates would import data that cannot be traced to its source."""
    with pytest.raises(ValueError):
        parse_date(value)
