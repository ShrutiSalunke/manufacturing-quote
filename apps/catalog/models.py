from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.models import Plant


class Material(models.Model):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="materials")
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    uom = models.CharField(max_length=30, default="kg")
    density = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)
    category = models.CharField(max_length=100, blank=True, default="")
    unit_price = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    currency = models.CharField(max_length=10, default="INR")
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("plant", "code")]
        ordering = ["code"]
        indexes = [
            models.Index(fields=["is_active"], name="catalog_mat_is_active_idx"),
            models.Index(fields=["plant", "is_active"], name="catalog_mat_plant_active_idx"),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"


class Machine(models.Model):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="machines")
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    hourly_rate = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    setup_rate = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    efficiency_percent = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("plant", "code")]
        ordering = ["code"]
        indexes = [
            models.Index(fields=["is_active"], name="catalog_mach_is_active_idx"),
            models.Index(fields=["plant", "is_active"], name="catalog_mach_plant_active_idx"),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"


class LaborRole(models.Model):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="labor_roles")
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    hourly_rate = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("plant", "code")]
        ordering = ["code"]
        indexes = [
            models.Index(fields=["is_active"], name="catalog_labor_is_active_idx"),
            models.Index(fields=["plant", "is_active"], name="catalog_labor_plant_active_idx"),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"


class CustomFieldDefinition(models.Model):
    class EntityType(models.TextChoices):
        MATERIAL = "MATERIAL", "Material"
        MACHINE = "MACHINE", "Machine"
        LABOR = "LABOR", "Labor"
        QUOTE_INPUT = "QUOTE_INPUT", "Quote Input"
        PRODUCT_PARAMETER = "PRODUCT_PARAMETER", "Product Parameter"

    class DataType(models.TextChoices):
        TEXT = "text", "Text"
        NUMBER = "number", "Number"
        BOOL = "bool", "Boolean"
        DATE = "date", "Date"
        ENUM = "enum", "Enum"

    plant = models.ForeignKey(
        Plant, null=True, blank=True, on_delete=models.CASCADE, related_name="custom_fields"
    )
    entity_type = models.CharField(max_length=30, choices=EntityType.choices)
    key = models.SlugField(max_length=80)
    label = models.CharField(max_length=200)
    data_type = models.CharField(max_length=20, choices=DataType.choices, default=DataType.TEXT)
    enum_choices = models.JSONField(default=list, blank=True)
    is_required = models.BooleanField(default=False)
    is_importable = models.BooleanField(default=True)
    import_column_header = models.CharField(max_length=120, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("plant", "entity_type", "key")]
        ordering = ["sort_order", "key"]
        indexes = [
            models.Index(
                fields=["entity_type", "is_active"],
                name="catalog_cfdef_ent_act_idx",
            ),
        ]

    def __str__(self):
        return f"{self.entity_type}.{self.key}"

    def save(self, *args, **kwargs):
        if not self.import_column_header:
            self.import_column_header = self.key
        super().save(*args, **kwargs)


class CustomFieldValue(models.Model):
    definition = models.ForeignKey(
        CustomFieldDefinition, on_delete=models.CASCADE, related_name="values"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    value_text = models.TextField(blank=True, default="")
    value_number = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    value_bool = models.BooleanField(null=True, blank=True)
    value_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = [("definition", "content_type", "object_id")]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def get_value(self):
        dt = self.definition.data_type
        if dt == CustomFieldDefinition.DataType.NUMBER:
            return self.value_number
        if dt == CustomFieldDefinition.DataType.BOOL:
            return self.value_bool
        if dt == CustomFieldDefinition.DataType.DATE:
            return self.value_date
        return self.value_text

    def set_value(self, value):
        dt = self.definition.data_type
        self.value_text = ""
        self.value_number = None
        self.value_bool = None
        self.value_date = None
        if value is None or value == "":
            return
        if dt == CustomFieldDefinition.DataType.NUMBER:
            self.value_number = value
        elif dt == CustomFieldDefinition.DataType.BOOL:
            if isinstance(value, bool):
                self.value_bool = value
            else:
                self.value_bool = str(value).strip().lower() in ("1", "true", "yes", "y")
        elif dt == CustomFieldDefinition.DataType.DATE:
            self.value_date = value
        else:
            self.value_text = str(value)
