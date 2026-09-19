"""
Process / SubProcess masters for automation quoting.

Product templates remain in the codebase (hidden from UI) and do not participate
in this flow. Material property injection is optional via material_bridge.
"""
from django.db import models

from apps.catalog.models import Material
from apps.core.models import Plant


class ResultUnit(models.TextChoices):
    MONEY = "MONEY", "Money"
    TIME = "TIME", "Time"


class DataType(models.TextChoices):
    NUMBER = "number", "Number"
    TEXT = "text", "Text"
    BOOL = "bool", "Boolean"


class Process(models.Model):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="processes")
    code = models.SlugField(max_length=50)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    result_formula = models.TextField(
        blank=True,
        default="0",
        help_text="Expression using field codes (e.g. LENGTH * RATE). Evaluated to the process final value.",
    )
    result_unit = models.CharField(
        max_length=10, choices=ResultUnit.choices, default=ResultUnit.MONEY
    )
    # When False, material properties are never injected into this process formula namespace.
    use_material_properties = models.BooleanField(
        default=False,
        help_text="If enabled, quote can pick a material and MAT_* properties enter the formula context.",
    )
    subprocesses = models.ManyToManyField(
        "SubProcess",
        through="ProcessSubProcessLink",
        related_name="processes",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("plant", "code")]
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class SubProcess(models.Model):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="subprocesses")
    code = models.SlugField(max_length=50)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    result_formula = models.TextField(
        blank=True,
        default="0",
        help_text="Expression using field codes. Result is added into the parent process total.",
    )
    result_unit = models.CharField(
        max_length=10, choices=ResultUnit.choices, default=ResultUnit.MONEY
    )
    use_material_properties = models.BooleanField(
        default=False,
        help_text="If enabled, inherits material context from the parent quote process when available.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("plant", "code")]
        ordering = ["code"]
        verbose_name = "sub process"
        verbose_name_plural = "sub processes"

    def __str__(self):
        return f"{self.code} — {self.name}"


class ProcessSubProcessLink(models.Model):
    """M2M: one process ↔ many subprocesses; one subprocess ↔ many processes."""

    process = models.ForeignKey(Process, on_delete=models.CASCADE, related_name="subprocess_links")
    subprocess = models.ForeignKey(
        SubProcess, on_delete=models.CASCADE, related_name="process_links"
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("process", "subprocess")]
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.process.code} → {self.subprocess.code}"


class ProcessField(models.Model):
    process = models.ForeignKey(Process, on_delete=models.CASCADE, related_name="fields")
    code = models.SlugField(max_length=50)
    label = models.CharField(max_length=200)
    data_type = models.CharField(max_length=20, choices=DataType.choices, default=DataType.NUMBER)
    unit = models.CharField(max_length=30, blank=True, default="")
    default_value = models.CharField(max_length=100, blank=True, default="")
    min_value = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    max_value = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    is_required = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    help_text = models.CharField(max_length=255, blank=True, default="")
    # Optional bind to a Material column or custom field key (used only when material bridge is on).
    material_property_key = models.SlugField(
        max_length=80,
        blank=True,
        default="",
        help_text="Optional. e.g. unit_price or a custom field key. Leave blank to disable.",
    )

    class Meta:
        unique_together = [("process", "code")]
        ordering = ["sort_order", "code"]

    def __str__(self):
        return f"{self.process.code}.{self.code}"


class SubProcessField(models.Model):
    subprocess = models.ForeignKey(SubProcess, on_delete=models.CASCADE, related_name="fields")
    code = models.SlugField(max_length=50)
    label = models.CharField(max_length=200)
    data_type = models.CharField(max_length=20, choices=DataType.choices, default=DataType.NUMBER)
    unit = models.CharField(max_length=30, blank=True, default="")
    default_value = models.CharField(max_length=100, blank=True, default="")
    min_value = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    max_value = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    is_required = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    help_text = models.CharField(max_length=255, blank=True, default="")
    material_property_key = models.SlugField(
        max_length=80,
        blank=True,
        default="",
        help_text="Optional. e.g. unit_price or a custom field key. Leave blank to disable.",
    )

    class Meta:
        unique_together = [("subprocess", "code")]
        ordering = ["sort_order", "code"]
        verbose_name = "sub process field"

    def __str__(self):
        return f"{self.subprocess.code}.{self.code}"


class QuoteProcess(models.Model):
    """A process instance on a quote (independent of product-template quote lines)."""

    quote = models.ForeignKey("quotes.Quote", on_delete=models.CASCADE, related_name="quote_processes")
    process = models.ForeignKey(Process, on_delete=models.PROTECT, related_name="quote_usages")
    material = models.ForeignKey(
        Material,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quote_processes",
    )
    sort_order = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=255, blank=True, default="")
    computed_own = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    computed_total = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.quote.number} / {self.process.code}"


class QuoteProcessFieldValue(models.Model):
    quote_process = models.ForeignKey(
        QuoteProcess, on_delete=models.CASCADE, related_name="field_values"
    )
    field_code = models.SlugField(max_length=50)
    value = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        unique_together = [("quote_process", "field_code")]

    def __str__(self):
        return f"{self.field_code}={self.value}"


class QuoteSubProcess(models.Model):
    quote_process = models.ForeignKey(
        QuoteProcess, on_delete=models.CASCADE, related_name="subprocesses"
    )
    subprocess = models.ForeignKey(
        SubProcess, on_delete=models.PROTECT, related_name="quote_usages"
    )
    sort_order = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=255, blank=True, default="")
    computed_value = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "quote sub process"

    def __str__(self):
        return f"{self.quote_process} → {self.subprocess.code}"


class QuoteSubProcessFieldValue(models.Model):
    quote_subprocess = models.ForeignKey(
        QuoteSubProcess, on_delete=models.CASCADE, related_name="field_values"
    )
    field_code = models.SlugField(max_length=50)
    value = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        unique_together = [("quote_subprocess", "field_code")]

    def __str__(self):
        return f"{self.field_code}={self.value}"
