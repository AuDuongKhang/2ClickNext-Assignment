import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import timezone as datetime_timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable

from django.db import IntegrityError, transaction

from activities.models import Activity, ActivityType, FollowUp, FollowUpStatus
from crm.models import Company, Contact, normalize_phone
from fairs.models import FairEdition
from imports.models import ImportBatch
from imports.parsers import normalize_status, parse_date, parse_datetime, parse_decimal
from opportunities.models import Opportunity, SalesStage


BATCH_SIZE = 2_000
ARCHIVE_FILES = (
    "fair_editions.csv",
    "companies_and_contacts.csv",
    "opportunities.csv",
    "activity_log.csv",
)
REQUIRED_HEADERS = {
    "fair_editions.csv": (
        "fair_edition_code",
        "fair_name",
        "city",
        "venue",
        "starts_on",
        "ends_on",
        "max_stand_height_m",
    ),
    "companies_and_contacts.csv": (
        "legacy_row_id",
        "company_code",
        "company_name",
        "province_code",
        "region",
        "sales_rep",
        "contact_code",
        "contact_first_name",
        "contact_last_name",
        "email",
        "phone",
        "fax",
        "legacy_print_layout",
    ),
    "opportunities.csv": (
        "opportunity_code",
        "company_code",
        "contact_code",
        "description",
        "amount_eur",
        "legacy_status",
        "opened_on",
        "expected_close_on",
        "historical_campaign_code",
        "fair_edition_code",
        "stand_area_sqm",
        "client_budget_eur",
        "requested_height_m",
        "brief_notes",
    ),
    "activity_log.csv": (
        "entry_id",
        "company_code",
        "opportunity_code",
        "activity_type",
        "occurred_at",
        "details",
        "follow_up_on",
        "completion_marker",
        "legacy_author",
    ),
}


class ArchiveValidationError(ValueError):
    def __init__(self, file_name: str, row_number: int, message: str):
        self.file_name = file_name
        self.row_number = row_number
        self.message = message
        super().__init__(f"{file_name} row {row_number}: {message}")


@dataclass(frozen=True)
class ArchiveData:
    manifest: dict
    manifest_checksum: str
    rows: dict[str, list[tuple[int, dict[str, str]]]]


def _clean(value: str) -> str:
    return value.strip()


def _normalized(value: str) -> str:
    return " ".join(value.split()).casefold()


def _required(row: dict[str, str], field: str, file_name: str, row_number: int) -> str:
    value = _clean(row[field])
    if not value:
        raise ArchiveValidationError(file_name, row_number, f"{field} is required")
    return value


def _parsed(
    parser: Callable[[str], object], row: dict[str, str], field: str, file_name: str, row_number: int
):
    try:
        return parser(row[field])
    except (InvalidOperation, ValueError) as error:
        raise ArchiveValidationError(file_name, row_number, f"invalid {field}: {row[field]!r}") from error


def _required_date(row: dict[str, str], field: str, file_name: str, row_number: int):
    value = _parsed(parse_date, row, field, file_name, row_number)
    if value is None:
        raise ArchiveValidationError(file_name, row_number, f"{field} is required")
    return value


def _required_datetime(row: dict[str, str], field: str, file_name: str, row_number: int):
    value = _parsed(parse_datetime, row, field, file_name, row_number)
    if value is None:
        raise ArchiveValidationError(file_name, row_number, f"{field} is required")
    return value


def _non_negative(value: Decimal | None, field: str, file_name: str, row_number: int) -> None:
    if value is not None and value < 0:
        raise ArchiveValidationError(file_name, row_number, f"{field} must not be negative")


def _canonical_manifest_checksum(manifest: dict) -> str:
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_archive(archive_dir: Path) -> ArchiveData:
    manifest_path = archive_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ArchiveValidationError("manifest.json", 1, "invalid or missing manifest") from error
    if not isinstance(manifest, dict) or not _clean(str(manifest.get("dataset_version", ""))):
        raise ArchiveValidationError("manifest.json", 1, "dataset_version is required")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ArchiveValidationError("manifest.json", 1, "files must be an object")

    rows: dict[str, list[tuple[int, dict[str, str]]]] = {}
    for file_name in ARCHIVE_FILES:
        metadata = files.get(file_name)
        if not isinstance(metadata, dict):
            raise ArchiveValidationError("manifest.json", 1, f"missing metadata for {file_name}")
        path = archive_dir / file_name
        try:
            source = path.read_bytes()
        except FileNotFoundError as error:
            raise ArchiveValidationError(file_name, 1, "file is missing") from error
        expected_checksum = metadata.get("sha256")
        if not isinstance(expected_checksum, str) or hashlib.sha256(source).hexdigest() != expected_checksum:
            raise ArchiveValidationError(file_name, 1, "checksum mismatch")
        try:
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle, delimiter=";")
                headers = reader.fieldnames
                if headers is None:
                    raise ArchiveValidationError(file_name, 1, "missing headers")
                missing_headers = set(REQUIRED_HEADERS[file_name]) - set(headers)
                if missing_headers:
                    raise ArchiveValidationError(
                        file_name, 1, f"missing headers: {', '.join(sorted(missing_headers))}"
                    )
                parsed_rows = []
                for row_number, row in enumerate(reader, start=2):
                    if None in row or None in row.values():
                        raise ArchiveValidationError(file_name, row_number, "wrong number of columns")
                    parsed_rows.append((row_number, row))
        except UnicodeDecodeError as error:
            raise ArchiveValidationError(file_name, 1, "not valid UTF-8") from error
        expected_rows = metadata.get("data_rows")
        if not isinstance(expected_rows, int) or expected_rows != len(parsed_rows):
            raise ArchiveValidationError(file_name, 1, "data row count does not match manifest")
        rows[file_name] = parsed_rows
    return ArchiveData(manifest, _canonical_manifest_checksum(manifest), rows)


def _reconciled_company_details(
    rows: list[tuple[int, dict[str, str]]],
) -> dict[str, dict[str, str]]:
    companies: dict[str, dict[str, str]] = {}
    legacy_row_ids: set[str] = set()
    for row_number, row in rows:
        legacy_row_id = _required(row, "legacy_row_id", "companies_and_contacts.csv", row_number)
        if legacy_row_id in legacy_row_ids:
            raise ArchiveValidationError(
                "companies_and_contacts.csv", row_number, f"duplicate legacy row {legacy_row_id}"
            )
        legacy_row_ids.add(legacy_row_id)
        code = _required(row, "company_code", "companies_and_contacts.csv", row_number)
        details = {
            "name": _clean(row["company_name"]),
            "province_code": _clean(row["province_code"]),
            "region": _clean(row["region"]),
            "sales_rep": _clean(row["sales_rep"]),
        }
        if not details["name"]:
            raise ArchiveValidationError("companies_and_contacts.csv", row_number, "company_name is required")
        existing = companies.get(code)
        if existing is None:
            companies[code] = details
            continue
        for field, value in details.items():
            if value and existing[field] and _normalized(value) != _normalized(existing[field]):
                raise ArchiveValidationError(
                    "companies_and_contacts.csv",
                    row_number,
                    f"company {code} has conflicting {field}",
                )
            if not existing[field] and value:
                existing[field] = value
    return companies


def _validate_archive(data: ArchiveData) -> dict[str, dict[str, str]]:
    fair_codes: set[str] = set()
    for row_number, row in data.rows["fair_editions.csv"]:
        code = _required(row, "fair_edition_code", "fair_editions.csv", row_number)
        if code in fair_codes:
            raise ArchiveValidationError("fair_editions.csv", row_number, f"duplicate fair edition {code}")
        fair_codes.add(code)
        starts_on = _required_date(row, "starts_on", "fair_editions.csv", row_number)
        ends_on = _required_date(row, "ends_on", "fair_editions.csv", row_number)
        if ends_on < starts_on:
            raise ArchiveValidationError("fair_editions.csv", row_number, "ends_on is before starts_on")
        maximum = _parsed(parse_decimal, row, "max_stand_height_m", "fair_editions.csv", row_number)
        _non_negative(maximum, "max_stand_height_m", "fair_editions.csv", row_number)
        for field in ("fair_name", "city", "venue"):
            _required(row, field, "fair_editions.csv", row_number)

    companies = _reconciled_company_details(data.rows["companies_and_contacts.csv"])
    contact_companies: dict[str, str] = {}
    for row_number, row in data.rows["companies_and_contacts.csv"]:
        code = _required(row, "company_code", "companies_and_contacts.csv", row_number)
        contact_code = _required(row, "contact_code", "companies_and_contacts.csv", row_number)
        existing_company = contact_companies.get(contact_code)
        if existing_company is not None:
            raise ArchiveValidationError(
                "companies_and_contacts.csv",
                row_number,
                f"duplicate contact {contact_code}",
            )
        contact_companies[contact_code] = code

    opportunity_codes: set[str] = set()
    opportunity_companies: dict[str, str] = {}
    for row_number, row in data.rows["opportunities.csv"]:
        code = _required(row, "opportunity_code", "opportunities.csv", row_number)
        if code in opportunity_codes:
            raise ArchiveValidationError("opportunities.csv", row_number, f"duplicate opportunity {code}")
        opportunity_codes.add(code)
        company_code = _required(row, "company_code", "opportunities.csv", row_number)
        if company_code not in companies:
            raise ArchiveValidationError("opportunities.csv", row_number, f"unknown company {company_code}")
        opportunity_companies[code] = company_code
        contact_code = _clean(row["contact_code"])
        if contact_code and contact_companies.get(contact_code) != company_code:
            raise ArchiveValidationError(
                "opportunities.csv", row_number, f"contact {contact_code} does not belong to {company_code}"
            )
        fair_code = _required(row, "fair_edition_code", "opportunities.csv", row_number)
        if fair_code not in fair_codes:
            raise ArchiveValidationError("opportunities.csv", row_number, f"unknown fair edition {fair_code}")
        status = normalize_status(row["legacy_status"])
        if status not in SalesStage.values:
            raise ArchiveValidationError("opportunities.csv", row_number, f"invalid legacy_status {row['legacy_status']!r}")
        _required(row, "description", "opportunities.csv", row_number)
        _required_date(row, "opened_on", "opportunities.csv", row_number)
        for field in ("amount_eur", "stand_area_sqm", "client_budget_eur", "requested_height_m"):
            value = _parsed(parse_decimal, row, field, "opportunities.csv", row_number)
            _non_negative(value, field, "opportunities.csv", row_number)
        _parsed(parse_date, row, "expected_close_on", "opportunities.csv", row_number)

    activity_entry_ids: set[str] = set()
    for row_number, row in data.rows["activity_log.csv"]:
        entry_id = _required(row, "entry_id", "activity_log.csv", row_number)
        if entry_id in activity_entry_ids:
            raise ArchiveValidationError(
                "activity_log.csv", row_number, f"duplicate activity entry {entry_id}"
            )
        activity_entry_ids.add(entry_id)
        company_code = _required(row, "company_code", "activity_log.csv", row_number)
        if company_code not in companies:
            raise ArchiveValidationError("activity_log.csv", row_number, f"unknown company {company_code}")
        opportunity_code = _clean(row["opportunity_code"])
        if opportunity_code:
            if opportunity_code not in opportunity_codes:
                raise ArchiveValidationError("activity_log.csv", row_number, f"unknown opportunity {opportunity_code}")
            if opportunity_companies[opportunity_code] != company_code:
                raise ArchiveValidationError(
                    "activity_log.csv",
                    row_number,
                    f"opportunity {opportunity_code} does not belong to {company_code}",
                )
        activity_type = normalize_status(row["activity_type"])
        if activity_type not in ActivityType.values:
            raise ArchiveValidationError("activity_log.csv", row_number, f"invalid activity_type {row['activity_type']!r}")
        _required_datetime(row, "occurred_at", "activity_log.csv", row_number)
        follow_up_on = _parsed(parse_date, row, "follow_up_on", "activity_log.csv", row_number)
        marker = _clean(row["completion_marker"])
        if marker not in {"", "Y", "N"}:
            raise ArchiveValidationError("activity_log.csv", row_number, "invalid completion_marker")
        if activity_type == ActivityType.TASK and marker not in {"Y", "N"}:
            raise ArchiveValidationError("activity_log.csv", row_number, "task completion_marker must be Y or N")

    entities = data.manifest.get("entities")
    expected_entities = {
        "companies": len(companies),
        "contacts": len(contact_companies),
        "opportunities": len(opportunity_codes),
        "activity_log_entries": len(data.rows["activity_log.csv"]),
        "fair_editions": len(fair_codes),
    }
    if not isinstance(entities, dict):
        raise ArchiveValidationError("manifest.json", 1, "entities must be an object")
    for name, actual in expected_entities.items():
        if entities.get(name) != actual:
            raise ArchiveValidationError("manifest.json", 1, f"entity count mismatch for {name}")
    return companies


def _bulk_create(model, objects: list) -> None:
    for start in range(0, len(objects), BATCH_SIZE):
        model.objects.bulk_create(objects[start : start + BATCH_SIZE], batch_size=BATCH_SIZE)


def _file_counts(data: ArchiveData, activity_accounted_rows: int) -> dict[str, dict[str, int]]:
    return {
        file_name: {
            "source_rows": len(data.rows[file_name]),
            "accounted_rows": activity_accounted_rows
            if file_name == "activity_log.csv"
            else len(data.rows[file_name]),
        }
        for file_name in ARCHIVE_FILES
    }


def _follow_up_key(
    *, company_id, opportunity_id, due_on, summary, created_at, author, status
) -> tuple:
    if created_at is not None and created_at.tzinfo is not None:
        created_at = created_at.astimezone(datetime_timezone.utc)
    return (
        company_id,
        opportunity_id,
        due_on,
        summary,
        created_at,
        author,
        status,
    )


def _backfill_existing_provenance(data: ArchiveData) -> None:
    """Fill provenance columns for domain rows imported before those columns existed."""
    with transaction.atomic():
        company_codes = {
            _clean(row["company_code"])
            for _, row in data.rows["companies_and_contacts.csv"]
        }
        company_map = Company.objects.in_bulk(company_codes, field_name="legacy_code")
        contact_codes = [
            _clean(row["contact_code"])
            for _, row in data.rows["companies_and_contacts.csv"]
        ]
        contact_map = Contact.objects.in_bulk(contact_codes, field_name="legacy_code")
        contact_updates = []
        for row_number, row in data.rows["companies_and_contacts.csv"]:
            contact_code = _clean(row["contact_code"])
            contact = contact_map.get(contact_code)
            if contact is None:
                raise ArchiveValidationError(
                    "companies_and_contacts.csv",
                    row_number,
                    f"cannot backfill missing contact {contact_code}",
                )
            legacy_row_id = _required(
                row, "legacy_row_id", "companies_and_contacts.csv", row_number
            )
            if contact.legacy_row_id not in (None, legacy_row_id):
                raise ArchiveValidationError(
                    "companies_and_contacts.csv",
                    row_number,
                    f"contact {contact_code} has conflicting legacy row {contact.legacy_row_id}",
                )
            if contact.legacy_row_id is None:
                contact.legacy_row_id = legacy_row_id
                contact_updates.append(contact)
        if contact_updates:
            Contact.objects.bulk_update(
                contact_updates, ["legacy_row_id"], batch_size=BATCH_SIZE
            )

        opportunity_codes = {
            _clean(row["opportunity_code"])
            for _, row in data.rows["opportunities.csv"]
        }
        opportunity_map = Opportunity.objects.in_bulk(
            opportunity_codes, field_name="legacy_code"
        )
        activity_entry_ids = [
            _clean(row["entry_id"])
            for _, row in data.rows["activity_log.csv"]
            if normalize_status(row["activity_type"]) != ActivityType.TASK
        ]
        activity_map = Activity.objects.in_bulk(
            activity_entry_ids, field_name="legacy_code"
        )
        task_entry_ids = [
            _required(row, "entry_id", "activity_log.csv", row_number)
            for row_number, row in data.rows["activity_log.csv"]
            if normalize_status(row["activity_type"]) == ActivityType.TASK
        ]
        existing_task_follow_ups = FollowUp.objects.in_bulk(
            task_entry_ids, field_name="legacy_entry_id"
        )
        linked_activity_ids = set(
            FollowUp.objects.filter(source_activity_id__in=[activity.pk for activity in activity_map.values()])
            .values_list("source_activity_id", flat=True)
        )
        unlinked_follow_ups = list(
            FollowUp.objects.filter(
                legacy_entry_id__isnull=True,
                source_activity__isnull=True,
            )
        )
        candidates_by_key: dict[tuple, list[FollowUp]] = {}
        for follow_up in unlinked_follow_ups:
            candidates_by_key.setdefault(
                _follow_up_key(
                    company_id=follow_up.company_id,
                    opportunity_id=follow_up.opportunity_id,
                    due_on=follow_up.due_on,
                    summary=follow_up.summary,
                    created_at=follow_up.created_at,
                    author=follow_up.author,
                    status=follow_up.status,
                ),
                [],
            ).append(follow_up)
        for candidates in candidates_by_key.values():
            candidates.sort(key=lambda follow_up: follow_up.pk)

        pending_by_key: dict[tuple, list[tuple]] = {}
        for row_number, row in data.rows["activity_log.csv"]:
            activity_type = normalize_status(row["activity_type"])
            entry_id = _clean(row["entry_id"])
            company = company_map.get(_clean(row["company_code"]))
            opportunity_code = _clean(row["opportunity_code"])
            opportunity = opportunity_map.get(opportunity_code) if opportunity_code else None
            occurred_at = parse_datetime(row["occurred_at"])
            follow_up_on = parse_date(row["follow_up_on"])
            author = _clean(row["legacy_author"])
            status = (
                FollowUpStatus.COMPLETED
                if _clean(row["completion_marker"]) == "Y"
                else FollowUpStatus.OPEN
            )

            if activity_type == ActivityType.TASK:
                if entry_id in existing_task_follow_ups:
                    continue
                if company is None or (opportunity_code and opportunity is None):
                    raise ArchiveValidationError(
                        "activity_log.csv",
                        row_number,
                        f"cannot backfill task {entry_id}: relationship is missing",
                    )
                key = _follow_up_key(
                    company_id=company.pk,
                    opportunity_id=opportunity.pk if opportunity else None,
                    due_on=follow_up_on,
                    summary=row["details"],
                    created_at=occurred_at,
                    author=author,
                    status=status,
                )
                pending_by_key.setdefault(key, []).append(
                    (row_number, "task", entry_id, None)
                )
                continue

            if follow_up_on is None:
                continue
            activity = activity_map.get(entry_id)
            if activity is None:
                raise ArchiveValidationError(
                    "activity_log.csv",
                    row_number,
                    f"cannot backfill missing source activity {entry_id}",
                )
            if company is None or (opportunity_code and opportunity is None):
                raise ArchiveValidationError(
                    "activity_log.csv",
                    row_number,
                    f"cannot backfill source activity {entry_id}: relationship is missing",
                )
            if (
                activity.company_id != company.pk
                or activity.opportunity_id != (opportunity.pk if opportunity else None)
            ):
                raise ArchiveValidationError(
                    "activity_log.csv",
                    row_number,
                    f"source activity {entry_id} does not match its archive relationship",
                )
            if activity.pk in linked_activity_ids:
                continue
            key = _follow_up_key(
                company_id=company.pk,
                opportunity_id=opportunity.pk if opportunity else None,
                due_on=follow_up_on,
                summary=row["details"],
                created_at=occurred_at,
                author=author,
                status=FollowUpStatus.OPEN,
            )
            pending_by_key.setdefault(key, []).append(
                (row_number, "derived", entry_id, activity)
            )

        follow_up_updates = []
        for key, pending in pending_by_key.items():
            candidates = candidates_by_key.pop(key, [])
            if len(candidates) != len(pending):
                row_number, kind, entry_id, _ = pending[0]
                description = (
                    f"imported task {entry_id}"
                    if kind == "task"
                    else f"derived follow-up for source activity {entry_id}"
                )
                raise ArchiveValidationError(
                    "activity_log.csv",
                    row_number,
                    f"cannot match {description} for provenance",
                )
            for follow_up, (_, kind, entry_id, activity) in zip(candidates, pending):
                if kind == "task":
                    follow_up.legacy_entry_id = entry_id
                else:
                    follow_up.source_activity = activity
                follow_up_updates.append(follow_up)

        if follow_up_updates:
            FollowUp.objects.bulk_update(
                follow_up_updates,
                ["legacy_entry_id", "source_activity"],
                batch_size=BATCH_SIZE,
            )


def import_archive(archive_dir: Path) -> ImportBatch:
    """Validate and atomically import one manifest-defined legacy archive."""
    data = _load_archive(Path(archive_dir))
    dataset_version = str(data.manifest["dataset_version"]).strip()
    source_name = f"archive:{dataset_version}:{data.manifest_checksum}"
    company_details = _validate_archive(data)
    existing = ImportBatch.objects.filter(
        source_name=source_name, source_checksum=data.manifest_checksum, status="completed"
    ).first()
    if existing is not None:
        _backfill_existing_provenance(data)
        return existing

    try:
        with transaction.atomic():
            batch, created = ImportBatch.objects.get_or_create(
                source_name=source_name,
                defaults={"source_checksum": data.manifest_checksum, "status": "importing"},
            )
            if not created and batch.status == "completed":
                _backfill_existing_provenance(data)
                return batch
            if not created:
                batch.source_checksum = data.manifest_checksum
                batch.status = "importing"
                batch.record_count = 0
                batch.file_counts = {}
                batch.error_message = ""
                batch.save(
                    update_fields=["source_checksum", "status", "record_count", "file_counts", "error_message"]
                )
            fair_objects = [
                FairEdition(
                    legacy_code=_clean(row["fair_edition_code"]),
                    fair_name=_clean(row["fair_name"]),
                    city=_clean(row["city"]),
                    venue=_clean(row["venue"]),
                    starts_on=parse_date(row["starts_on"]),
                    ends_on=parse_date(row["ends_on"]),
                    max_stand_height_m=parse_decimal(row["max_stand_height_m"]),
                )
                for _, row in data.rows["fair_editions.csv"]
            ]
            _bulk_create(FairEdition, fair_objects)
            fair_map = FairEdition.objects.in_bulk(
                [fair.legacy_code for fair in fair_objects], field_name="legacy_code"
            )

            company_objects = [
                Company(legacy_code=code, **details) for code, details in company_details.items()
            ]
            _bulk_create(Company, company_objects)
            company_map = Company.objects.in_bulk(
                [company.legacy_code for company in company_objects], field_name="legacy_code"
            )

            contact_objects = [
                Contact(
                    legacy_code=_clean(row["contact_code"]),
                    legacy_row_id=_clean(row["legacy_row_id"]),
                    company=company_map[_clean(row["company_code"])],
                    first_name=_clean(row["contact_first_name"]),
                    last_name=_clean(row["contact_last_name"]),
                    email=_clean(row["email"]),
                    phone=_clean(row["phone"]),
                    phone_search=normalize_phone(_clean(row["phone"])),
                    fax=_clean(row["fax"]),
                )
                for _, row in data.rows["companies_and_contacts.csv"]
            ]
            _bulk_create(Contact, contact_objects)
            contact_map = Contact.objects.in_bulk(
                [contact.legacy_code for contact in contact_objects], field_name="legacy_code"
            )

            opportunity_objects = [
                Opportunity(
                    legacy_code=_clean(row["opportunity_code"]),
                    company=company_map[_clean(row["company_code"])],
                    primary_contact=contact_map.get(_clean(row["contact_code"])),
                    fair_edition=fair_map[_clean(row["fair_edition_code"])],
                    description=_clean(row["description"]),
                    amount_eur=parse_decimal(row["amount_eur"]),
                    sales_stage=normalize_status(row["legacy_status"]),
                    raw_legacy_status=row["legacy_status"],
                    opened_on=parse_date(row["opened_on"]),
                    expected_close_on=parse_date(row["expected_close_on"]),
                    historical_campaign_code=_clean(row["historical_campaign_code"]),
                    stand_area_sqm=parse_decimal(row["stand_area_sqm"]),
                    client_budget_eur=parse_decimal(row["client_budget_eur"]),
                    requested_height_m=parse_decimal(row["requested_height_m"]),
                    brief_notes=row["brief_notes"],
                )
                for _, row in data.rows["opportunities.csv"]
            ]
            _bulk_create(Opportunity, opportunity_objects)
            opportunity_map = Opportunity.objects.in_bulk(
                [opportunity.legacy_code for opportunity in opportunity_objects], field_name="legacy_code"
            )

            activity_objects: list[Activity] = []
            follow_up_objects: list[FollowUp] = []
            derived_follow_up_rows: list[tuple[str, object, object, object, str, object, str]] = []
            activity_accounted_rows = 0
            for _, row in data.rows["activity_log.csv"]:
                activity_type = normalize_status(row["activity_type"])
                opportunity = opportunity_map.get(_clean(row["opportunity_code"]))
                occurred_at = parse_datetime(row["occurred_at"])
                follow_up_on = parse_date(row["follow_up_on"])
                marker = _clean(row["completion_marker"])
                company = company_map[_clean(row["company_code"])]
                if activity_type == ActivityType.TASK:
                    follow_up_objects.append(
                        FollowUp(
                            legacy_entry_id=_clean(row["entry_id"]),
                            company=company,
                            opportunity=opportunity,
                            due_on=follow_up_on,
                            summary=row["details"],
                            created_at=occurred_at,
                            author=_clean(row["legacy_author"]),
                            status=(
                                FollowUpStatus.COMPLETED if marker == "Y" else FollowUpStatus.OPEN
                            ),
                        )
                    )
                else:
                    activity_objects.append(
                        Activity(
                            legacy_code=_clean(row["entry_id"]),
                            company=company,
                            opportunity=opportunity,
                            activity_type=activity_type,
                            occurred_at=occurred_at,
                            details=row["details"],
                            completed={"Y": True, "N": False}.get(marker),
                            legacy_author=_clean(row["legacy_author"]),
                            author=_clean(row["legacy_author"]),
                        )
                    )
                    if follow_up_on is not None:
                        derived_follow_up_rows.append(
                            (
                                _clean(row["entry_id"]),
                                company,
                                opportunity,
                                follow_up_on,
                                row["details"],
                                occurred_at,
                                _clean(row["legacy_author"]),
                            )
                        )
                activity_accounted_rows += 1
            _bulk_create(Activity, activity_objects)
            activity_map = {
                activity.legacy_code: activity for activity in activity_objects
            }
            for (
                entry_id,
                company,
                opportunity,
                due_on,
                summary,
                created_at,
                author,
            ) in derived_follow_up_rows:
                follow_up_objects.append(
                    FollowUp(
                        company=company,
                        opportunity=opportunity,
                        source_activity=activity_map[entry_id],
                        due_on=due_on,
                        summary=summary,
                        created_at=created_at,
                        author=author,
                        status=FollowUpStatus.OPEN,
                    )
                )
            _bulk_create(FollowUp, follow_up_objects)

            batch.status = "completed"
            batch.record_count = sum(len(rows) for rows in data.rows.values())
            batch.file_counts = _file_counts(data, activity_accounted_rows)
            batch.save(update_fields=["status", "record_count", "file_counts"])
            return batch
    except IntegrityError:
        completed = ImportBatch.objects.filter(
            source_name=source_name, source_checksum=data.manifest_checksum, status="completed"
        ).first()
        if completed is not None:
            _backfill_existing_provenance(data)
            return completed
        raise
