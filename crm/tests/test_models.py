import pytest
from django.db import IntegrityError

from crm.models import Company, Contact


@pytest.mark.django_db
def test_company_legacy_code_is_unique():
    Company.objects.create(legacy_code="CO1", name="First")

    with pytest.raises(IntegrityError):
        Company.objects.create(legacy_code="CO1", name="Duplicate")


@pytest.mark.django_db
def test_contact_full_name_joins_non_empty_name_parts(company):
    contact = Contact.objects.create(
        legacy_code="P1", company=company, first_name="Ada", last_name=""
    )

    assert contact.full_name == "Ada"
