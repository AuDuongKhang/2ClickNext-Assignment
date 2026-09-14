from django.db import models


class ImportBatch(models.Model):
    source_name = models.CharField(max_length=255, unique=True)
    source_checksum = models.CharField(max_length=64)
    status = models.CharField(max_length=32)
    imported_at = models.DateTimeField(auto_now_add=True)
    record_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
