from django.db import models


class Company(models.Model):
    legacy_code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    province_code = models.CharField(max_length=16, blank=True)
    region = models.CharField(max_length=128, blank=True)
    sales_rep = models.CharField(max_length=255, blank=True)

    class Meta:
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return self.name


class Contact(models.Model):
    legacy_code = models.CharField(max_length=64, unique=True)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="contacts")
    first_name = models.CharField(max_length=128, blank=True)
    last_name = models.CharField(max_length=128, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    fax = models.CharField(max_length=64, blank=True)

    class Meta:
        indexes = [models.Index(fields=["company", "last_name", "first_name"])]

    @property
    def full_name(self):
        return " ".join(part for part in (self.first_name, self.last_name) if part)

    def __str__(self):
        return self.full_name or self.legacy_code
