import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Barrier
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.db import close_old_connections

from activities.models import Activity, FollowUp
from crm.models import Company, Contact
from imports.services import ArchiveValidationError, import_archive
from imports.models import ImportBatch
from opportunities.models import Opportunity


ARCHIVE = Path("tests/fixtures/archive")


def update_fixture_checksum(archive: Path, file_name: str) -> None:
    manifest_path = archive / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][file_name]["sha256"] = hashlib.sha256(
        (archive / file_name).read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


@pytest.mark.django_db(transaction=True)
def test_import_is_complete_and_idempotent(settings):
    """Creating a second batch would duplicate an unchanged source archive."""
    first = import_archive(ARCHIVE)
    second = import_archive(ARCHIVE)

    assert first.pk == second.pk
    assert Company.objects.count() == 2
    assert Contact.objects.count() == 3
    assert Opportunity.objects.count() == 3
    assert first.file_counts["activity_log.csv"]["source_rows"] == 6
    assert first.file_counts["activity_log.csv"]["accounted_rows"] == 6


@pytest.mark.django_db(transaction=True)
def test_import_preserves_legacy_values_and_maps_activity_rows():
    """Dropping raw status, nulls, authors, or task markers would lose archive evidence."""
    import_archive(ARCHIVE)

    complete = Opportunity.objects.get(legacy_code="OP-001")
    missing_values = Opportunity.objects.get(legacy_code="OP-002")
    conversation = Activity.objects.get(legacy_code="AC-001")
    pending_task = FollowUp.objects.get(summary="Send updated height proposal")
    contact = Contact.objects.get(legacy_code="CO-001-P01")

    assert complete.raw_legacy_status == " OPEN "
    assert complete.requested_height_m.as_tuple().digits == (4, 0, 0)
    assert missing_values.amount_eur is None
    assert missing_values.primary_contact is None
    assert conversation.author == "a.morgan"
    assert contact.legacy_row_id == "AN-001"
    assert Activity.objects.filter(legacy_code="AC-003").count() == 0
    assert pending_task.status == "open"
    assert pending_task.author == "j.chen"
    assert pending_task.legacy_entry_id == "AC-003"
    assert FollowUp.objects.filter(status="completed").count() == 1


@pytest.mark.django_db(transaction=True)
def test_import_maps_every_task_and_company_follow_up_without_fabricating_due_dates():
    """Turning company tasks into Activities or inventing dates loses source meaning."""
    import_archive(ARCHIVE)

    opportunity_task = FollowUp.objects.get(summary="Send updated height proposal")
    company_task = FollowUp.objects.get(summary="Company-level task without due date")
    company_conversation = FollowUp.objects.get(summary="Company-level conversation follow-up")

    assert opportunity_task.company.legacy_code == "CO-001"
    assert opportunity_task.opportunity.legacy_code == "OP-001"
    assert opportunity_task.due_on == date(2026, 9, 6)
    assert opportunity_task.created_at.astimezone(ZoneInfo("Europe/Rome")).isoformat() == "2026-08-26T09:00:00+02:00"
    assert opportunity_task.status == "open"
    assert company_task.company.legacy_code == "CO-002"
    assert company_task.opportunity is None
    assert company_task.due_on is None
    assert company_task.created_at.astimezone(ZoneInfo("Europe/Rome")).isoformat() == "2026-08-28T10:00:00+02:00"
    assert company_task.status == "open"
    assert company_task.author == "j.chen"
    assert company_conversation.company.legacy_code == "CO-002"
    assert company_conversation.opportunity is None
    assert company_conversation.due_on == date(2026, 9, 12)
    assert company_conversation.source_activity.legacy_code == "AC-006"
    assert FollowUp.objects.get(summary="Confirmed requested height and plot").source_activity == Activity.objects.get(
        legacy_code="AC-001"
    )
    assert Activity.objects.filter(activity_type="task").count() == 0


@pytest.mark.django_db(transaction=True)
def test_import_reconciles_provenance_for_an_already_imported_batch():
    import_archive(ARCHIVE)

    Contact.objects.update(legacy_row_id=None)
    FollowUp.objects.update(legacy_entry_id=None, source_activity=None)

    first_reconciliation = import_archive(ARCHIVE)
    counts_after_reconciliation = (
        Company.objects.count(),
        Contact.objects.count(),
        Activity.objects.count(),
        FollowUp.objects.count(),
    )
    second_reconciliation = import_archive(ARCHIVE)

    assert first_reconciliation.pk == second_reconciliation.pk
    assert counts_after_reconciliation == (
        Company.objects.count(),
        Contact.objects.count(),
        Activity.objects.count(),
        FollowUp.objects.count(),
    )
    assert Contact.objects.get(legacy_code="CO-001-P01").legacy_row_id == "AN-001"
    assert FollowUp.objects.get(summary="Send updated height proposal").legacy_entry_id == "AC-003"
    assert FollowUp.objects.get(summary="Company-level conversation follow-up").source_activity.legacy_code == "AC-006"


@pytest.mark.django_db(transaction=True)
def test_import_reconciles_provenance_after_user_completes_open_task():
    first = import_archive(ARCHIVE)

    task = FollowUp.objects.get(summary="Send updated height proposal")
    task.status = "completed"
    task.save(update_fields=["status"])
    Contact.objects.update(legacy_row_id=None)
    FollowUp.objects.update(legacy_entry_id=None, source_activity=None)

    reconciled = import_archive(ARCHIVE)
    repeated = import_archive(ARCHIVE)

    assert reconciled.pk == first.pk == repeated.pk
    assert Company.objects.count() == 2
    assert Contact.objects.count() == 3
    assert Activity.objects.count() == 3
    assert FollowUp.objects.count() == 5
    assert Contact.objects.get(legacy_code="CO-001-P01").legacy_row_id == "AN-001"
    assert FollowUp.objects.get(summary="Send updated height proposal").legacy_entry_id == "AC-003"
    assert FollowUp.objects.get(summary="Send updated height proposal").status == "completed"
    assert FollowUp.objects.get(summary="Confirmed requested height and plot").source_activity.legacy_code == "AC-001"
    assert FollowUp.objects.get(summary="Company-level conversation follow-up").source_activity.legacy_code == "AC-006"


@pytest.mark.django_db(transaction=True)
def test_import_reconciles_colliding_task_and_derived_follow_up_in_archive_order(tmp_path):
    archive = tmp_path / "archive"
    archive.mkdir()
    for source in ARCHIVE.iterdir():
        (archive / source.name).write_bytes(source.read_bytes())

    activities = archive / "activity_log.csv"
    original_task_row = (
        "AC-003;CO-001;OP-001;task;26/08/2026 09:00;Send updated height proposal;"
        "06/09/2026;N;j.chen"
    )
    colliding_task_row = (
        "AC-003;CO-001;OP-001;task;25/08/2026 10:30;Confirmed requested height and plot;"
        "05/09/2026;N;a.morgan"
    )
    source = activities.read_text(encoding="utf-8")
    assert source.count(original_task_row) == 1
    activities.write_text(source.replace(original_task_row, colliding_task_row), encoding="utf-8")
    update_fixture_checksum(archive, "activity_log.csv")

    first = import_archive(archive)
    assert list(
        FollowUp.objects.filter(summary="Confirmed requested height and plot")
        .order_by("pk")
        .values_list("legacy_entry_id", "source_activity__legacy_code")
    ) == [(None, "AC-001"), ("AC-003", None)]
    task = FollowUp.objects.get(legacy_entry_id="AC-003")
    derived = FollowUp.objects.get(source_activity__legacy_code="AC-001")
    FollowUp.objects.update(legacy_entry_id=None, source_activity=None)

    reconciled = import_archive(archive)
    repeated = import_archive(archive)

    assert reconciled.pk == first.pk == repeated.pk
    assert Company.objects.count() == 2
    assert Contact.objects.count() == 3
    assert Activity.objects.count() == 3
    assert FollowUp.objects.count() == 5
    assert FollowUp.objects.get(pk=task.pk).legacy_entry_id == "AC-003"
    assert FollowUp.objects.get(pk=derived.pk).source_activity.legacy_code == "AC-001"


@pytest.mark.django_db(transaction=True)
def test_import_rolls_back_entire_batch_when_a_reference_is_broken(tmp_path):
    """Moving writes outside the transaction would leave partial data after a bad row."""
    archive = tmp_path / "archive"
    archive.mkdir()
    for source in ARCHIVE.iterdir():
        target = archive / source.name
        target.write_bytes(source.read_bytes())
    opportunities = archive / "opportunities.csv"
    opportunities.write_text(
        opportunities.read_text().replace("CO-002;", "CO-404;", 1), encoding="utf-8"
    )
    update_fixture_checksum(archive, "opportunities.csv")

    with pytest.raises(ArchiveValidationError, match="CO-404"):
        import_archive(archive)

    assert Company.objects.count() == 0
    assert Opportunity.objects.count() == 0
    assert Activity.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_import_rejects_conflicting_repeated_company_details(tmp_path):
    """Keeping the first repeated company value would conceal source contradictions."""
    archive = tmp_path / "archive"
    archive.mkdir()
    for source in ARCHIVE.iterdir():
        target = archive / source.name
        target.write_bytes(source.read_bytes())
    companies = archive / "companies_and_contacts.csv"
    companies.write_text(
        companies.read_text().replace("Aster Cosmetics S.r.l.;BA", "Aster Conflict;BA", 1),
        encoding="utf-8",
    )
    update_fixture_checksum(archive, "companies_and_contacts.csv")

    with pytest.raises(ArchiveValidationError, match="CO-001.*name"):
        import_archive(archive)

    assert Company.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_import_rejects_activity_attached_to_another_companys_opportunity(tmp_path):
    """Accepting mismatched activity references would attach history to the wrong account."""
    archive = tmp_path / "archive"
    archive.mkdir()
    for source in ARCHIVE.iterdir():
        target = archive / source.name
        target.write_bytes(source.read_bytes())
    activities = archive / "activity_log.csv"
    activities.write_text(
        activities.read_text().replace("AC-001;CO-001;OP-001", "AC-001;CO-002;OP-001"),
        encoding="utf-8",
    )
    update_fixture_checksum(archive, "activity_log.csv")

    with pytest.raises(ArchiveValidationError, match="OP-001.*CO-002"):
        import_archive(archive)

    assert Company.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_import_rejects_duplicate_contact_code_with_source_location(tmp_path):
    """Letting duplicate contact identifiers reach bulk insert hides the bad source row."""
    archive = tmp_path / "archive"
    archive.mkdir()
    for source in ARCHIVE.iterdir():
        (archive / source.name).write_bytes(source.read_bytes())
    companies = archive / "companies_and_contacts.csv"
    companies.write_text(
        companies.read_text().replace("CO-001-P02", "CO-001-P01"), encoding="utf-8"
    )
    update_fixture_checksum(archive, "companies_and_contacts.csv")
    manifest_path = archive / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["entities"]["contacts"] = 2
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ArchiveValidationError, match="companies_and_contacts.csv row 3: duplicate contact CO-001-P01"):
        import_archive(archive)

    assert Contact.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_import_rejects_duplicate_legacy_row_id_with_source_location(tmp_path):
    """Allowing duplicate source row identifiers would make the company export non-auditable."""
    archive = tmp_path / "archive"
    archive.mkdir()
    for source in ARCHIVE.iterdir():
        (archive / source.name).write_bytes(source.read_bytes())
    companies = archive / "companies_and_contacts.csv"
    companies.write_text(companies.read_text().replace("AN-002", "AN-001"), encoding="utf-8")
    update_fixture_checksum(archive, "companies_and_contacts.csv")

    with pytest.raises(ArchiveValidationError, match="companies_and_contacts.csv row 3: duplicate legacy row AN-001"):
        import_archive(archive)

    assert Company.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_import_rejects_duplicate_activity_entry_id_with_source_location(tmp_path):
    """Letting duplicate entry IDs reach bulk insert hides the bad source row."""
    archive = tmp_path / "archive"
    archive.mkdir()
    for source in ARCHIVE.iterdir():
        (archive / source.name).write_bytes(source.read_bytes())
    activities = archive / "activity_log.csv"
    activities.write_text(activities.read_text().replace("AC-002", "AC-001"), encoding="utf-8")
    update_fixture_checksum(archive, "activity_log.csv")

    with pytest.raises(ArchiveValidationError, match="activity_log.csv row 3: duplicate activity entry AC-001"):
        import_archive(archive)

    assert Activity.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_import_uses_reconciled_later_company_details_when_first_row_is_blank(tmp_path):
    """Rebuilding company data from the first row discards a later non-empty value."""
    archive = tmp_path / "archive"
    archive.mkdir()
    for source in ARCHIVE.iterdir():
        (archive / source.name).write_bytes(source.read_bytes())
    companies = archive / "companies_and_contacts.csv"
    companies.write_text(
        companies.read_text().replace("Apulia;Casey Martin;CO-001-P01", "Apulia;;CO-001-P01"),
        encoding="utf-8",
    )
    update_fixture_checksum(archive, "companies_and_contacts.csv")

    import_archive(archive)

    assert Company.objects.get(legacy_code="CO-001").sales_rep == "Casey Martin"


@pytest.mark.django_db(transaction=True)
def test_concurrent_retries_return_one_completed_batch_without_partial_rows(tmp_path):
    """A race on ImportBatch must not surface as a unique-key error or duplicate records."""
    archive = tmp_path / "archive"
    archive.mkdir()
    for source in ARCHIVE.iterdir():
        (archive / source.name).write_bytes(source.read_bytes())
    barrier = Barrier(2)

    def retry_import():
        close_old_connections()
        try:
            barrier.wait()
            return import_archive(archive)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = list(executor.map(lambda _: retry_import(), range(2)))

    assert first.pk == second.pk
    assert first.status == "completed"
    assert ImportBatch.objects.filter(status="completed").count() == 1
    assert Company.objects.count() == 2
    assert FollowUp.objects.count() == 5


@pytest.mark.django_db(transaction=True)
def test_import_archive_command_reports_completed_batch():
    """Removing the command's service call would leave deployment with no archive import."""
    from io import StringIO

    output = StringIO()

    call_command("import_archive", str(ARCHIVE), stdout=output)

    assert "Import batch " in output.getvalue()
    assert output.getvalue().rstrip().endswith(": completed")
