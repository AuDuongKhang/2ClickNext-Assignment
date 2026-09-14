from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo


ROME = ZoneInfo("Europe/Rome")


def parse_date(value: str):
    cleaned = value.strip()
    return None if cleaned == "" else datetime.strptime(cleaned, "%d/%m/%Y").date()


def parse_datetime(value: str):
    cleaned = value.strip()
    return None if cleaned == "" else datetime.strptime(cleaned, "%d/%m/%Y %H:%M").replace(tzinfo=ROME)


def parse_decimal(value: str) -> Decimal | None:
    cleaned = value.strip()
    return None if cleaned == "" else Decimal(cleaned.replace(",", "."))


def normalize_status(value: str) -> str:
    return value.strip().lower()
