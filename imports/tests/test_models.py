import pytest

from imports.models import ImportBatch


@pytest.mark.django_db
def test_import_batch_stores_per_file_counts():
    batch = ImportBatch.objects.create(
        source_name="archive-2027",
        source_checksum="a" * 64,
        status="completed",
        file_counts={"companies_and_contacts.csv": 12, "opportunities.csv": 8},
    )

    assert batch.file_counts == {"companies_and_contacts.csv": 12, "opportunities.csv": 8}
