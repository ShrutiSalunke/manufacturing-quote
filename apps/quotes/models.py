import hashlib
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import Plant
from apps.templates_engine.models import ProductTemplate


class Customer(models.Model):
    """Client master (UI label: Clients). Reused across quotes."""

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")
    company = models.CharField(max_length=200, blank=True, default="")
    gstin = models.CharField(max_length=20, blank=True, default="")
    address_line1 = models.CharField(max_length=255, blank=True, default="")
    address_line2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    postal_code = models.CharField(max_length=30, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="India")
    notes = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        label = self.company or self.name
        return f"{self.code} — {label}" if self.code else label


class Quote(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        CALCULATED = "CALCULATED", "Calculated"
        ISSUED = "ISSUED", "Issued"

    number = models.CharField(max_length=40, unique=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="quotes")
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quotes",
    )
    currency = models.CharField(max_length=10, default="INR")
    valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="quotes"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    issued_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.number} v{self.version}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"Q-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        if not self.currency and self.plant_id:
            self.currency = self.plant.currency
        super().save(*args, **kwargs)

    @property
    def is_editable(self):
        return self.status != self.Status.ISSUED


class QuoteLine(models.Model):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="lines")
    template = models.ForeignKey(
        ProductTemplate, on_delete=models.PROTECT, related_name="quote_lines"
    )
    description = models.CharField(max_length=255, blank=True, default="")
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=1)
    sort_order = models.PositiveIntegerField(default=0)
    snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.description or f"Line {self.pk}"

    def save(self, *args, **kwargs):
        if not self.description and self.template_id:
            self.description = self.template.name
        super().save(*args, **kwargs)


class QuoteLineParameterValue(models.Model):
    line = models.ForeignKey(QuoteLine, on_delete=models.CASCADE, related_name="parameter_values")
    parameter_code = models.SlugField(max_length=50)
    value = models.CharField(max_length=200)

    class Meta:
        unique_together = [("line", "parameter_code")]

    def __str__(self):
        return f"{self.parameter_code}={self.value}"


class QuoteCalculationSnapshot(models.Model):
    quote = models.OneToOneField(Quote, on_delete=models.CASCADE, related_name="calculation")
    data = models.JSONField(default=dict)
    calculated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Snapshot for {self.quote}"


class QuoteDocument(models.Model):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="documents")
    pdf_file = models.FileField(upload_to="quotes/pdfs/")
    generated_at = models.DateTimeField(auto_now_add=True)
    file_hash = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return f"PDF {self.quote.number} @ {self.generated_at}"

    def compute_hash(self):
        if not self.pdf_file:
            return ""
        h = hashlib.sha256()
        for chunk in self.pdf_file.chunks():
            h.update(chunk)
        return h.hexdigest()
