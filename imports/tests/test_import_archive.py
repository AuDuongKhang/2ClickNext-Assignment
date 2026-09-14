import hashlib
import json
from pathlib import Path

import pytest
from django.core.management import call_command

from activities.models import Activity, FollowUp
from crm.models import Company, Contact
from imports.services import ArchiveValidationError, import_archive
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
    assert first.file_counts["activity_log.csv"]["source_rows"] == 4
    assert first.file_counts["activity_log.csv"]["accounted_rows"] == 4


@pytest.mark.django_db(transaction=True)
def test_import_preserves_legacy_values_and_maps_activity_rows():
    """Dropping raw status, nulls, authors, or task markers would lose archive evidence."""
    import_archive(ARCHIVE)

    complete = Opportunity.objects.get(legacy_code="OP-001")
    missing_values = Opportunity.objects.get(legacy_code="OP-002")
    conversation = Activity.objects.get(legacy_code="AC-001")
    pending_task = FollowUp.objects.get(summary="Send updated height proposal")

    assert complete.raw_legacy_status == " OPEN "
    assert complete.requested_height_m.as_tuple().digits == (4, 0, 0)
    assert missing_values.amount_eur is None
    assert missing_values.primary_contact is None
    assert conversation.author == "a.morgan"
    assert Activity.objects.filter(legacy_code="AC-003").count() == 0
    assert pending_task.status == "open"
    assert pending_task.author == "j.chen"
    assert FollowUp.objects.filter(status="completed").count() == 1


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
def test_import_archive_command_reports_completed_batch():
    """Removing the command's service call would leave deployment with no archive import."""
    from io import StringIO

    output = StringIO()

    call_command("import_archive", str(ARCHIVE), stdout=output)

    assert "Import batch " in output.getvalue()
    assert output.getvalue().rstrip().endswith(": completed")
