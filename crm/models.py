from django.contrib.postgres.indexes import GinIndex
from django.db import models


def normalize_phone(value: str) -> str:
    """Return the digits used for exact phone search and indexing."""
    return "".join(character for character in value if character.isdigit())


class Company(models.Model):
    legacy_code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    province_code = models.CharField(max_length=16, blank=True)
    region = models.CharField(max_length=128, blank=True)
    sales_rep = models.CharField(max_length=255, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
            GinIndex(fields=["name"], name="company_name_trgm", opclasses=["gin_trgm_ops"]),
        ]

    def __str__(self):
        return self.name


class Contact(models.Model):
    legacy_code = models.CharField(max_length=64, unique=True)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="contacts")
    first_name = models.CharField(max_length=128, blank=True)
    last_name = models.CharField(max_length=128, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    phone_search = models.CharField(max_length=64, blank=True, editable=False)
    fax = models.CharField(max_length=64, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "last_name", "first_name"]),
            GinIndex(fields=["first_name"], name="contact_first_trgm", opclasses=["gin_trgm_ops"]),
            GinIndex(fields=["last_name"], name="contact_last_trgm", opclasses=["gin_trgm_ops"]),
            GinIndex(fields=["email"], name="contact_email_trgm", opclasses=["gin_trgm_ops"]),
            models.Index(fields=["phone_search"], name="contact_phone_search_idx"),
        ]

    def save(self, *args, **kwargs):
        self.phone_search = normalize_phone(self.phone)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"phone_search"}
        return super().save(*args, **kwargs)

    @property
    def full_name(self):
        return " ".join(part for part in (self.first_name, self.last_name) if part)

    def __str__(self):
        return self.full_name or self.legacy_code
