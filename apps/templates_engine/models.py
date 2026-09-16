from django.db import models

from apps.catalog.models import LaborRole, Machine, Material
from apps.core.models import Plant


class ProductFamily(models.Model):
    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True, default="")

    class Meta:
        verbose_name_plural = "product families"
        ordering = ["code"]

    def __str__(self):
        return self.name


class ProductTemplate(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"

    family = models.ForeignKey(ProductFamily, on_delete=models.PROTECT, related_name="templates")
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="product_templates")
    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=50)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("plant", "code", "version")]
        ordering = ["code", "-version"]

    def __str__(self):
        return f"{self.code} v{self.version} ({self.status})"


class TemplateParameter(models.Model):
    class DataType(models.TextChoices):
        NUMBER = "number", "Number"
        TEXT = "text", "Text"
        BOOL = "bool", "Boolean"

    template = models.ForeignKey(ProductTemplate, on_delete=models.CASCADE, related_name="parameters")
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

    class Meta:
        unique_together = [("template", "code")]
        ordering = ["sort_order", "code"]

    def __str__(self):
        return self.code


class TemplateFormula(models.Model):
    template = models.ForeignKey(ProductTemplate, on_delete=models.CASCADE, related_name="formulas")
    code = models.SlugField(max_length=50)
    expression = models.TextField()
    return_unit = models.CharField(max_length=30, blank=True, default="")
    description = models.CharField(max_length=255, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("template", "code")]
        ordering = ["sort_order", "code"]
        verbose_name_plural = "template formulas"

    def __str__(self):
        return f"{self.code} = {self.expression}"


class TemplateBomItem(models.Model):
    class CostGroup(models.TextChoices):
        MATERIAL = "MATERIAL", "Material"
        PACKAGING = "PACKAGING", "Packaging"
        OTHER = "OTHER", "Other"

    template = models.ForeignKey(ProductTemplate, on_delete=models.CASCADE, related_name="bom_items")
    name = models.CharField(max_length=200)
    material = models.ForeignKey(
        Material, null=True, blank=True, on_delete=models.SET_NULL, related_name="bom_usages"
    )
    qty_formula = models.TextField()
    scrap_formula = models.TextField(default="0")
    cost_group = models.CharField(max_length=20, choices=CostGroup.choices, default=CostGroup.MATERIAL)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class TemplateOperation(models.Model):
    template = models.ForeignKey(ProductTemplate, on_delete=models.CASCADE, related_name="operations")
    sequence = models.PositiveIntegerField(default=10)
    name = models.CharField(max_length=200)
    machine = models.ForeignKey(
        Machine, null=True, blank=True, on_delete=models.SET_NULL, related_name="template_ops"
    )
    labor_role = models.ForeignKey(
        LaborRole, null=True, blank=True, on_delete=models.SET_NULL, related_name="template_ops"
    )
    setup_time_formula_min = models.TextField(default="0")
    cycle_time_formula_min = models.TextField(default="0")
    labor_time_formula_min = models.TextField(default="0")
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["sequence", "id"]

    def __str__(self):
        return f"{self.sequence}. {self.name}"


class TemplateCostElement(models.Model):
    class Category(models.TextChoices):
        OVERHEAD = "OVERHEAD", "Overhead"
        FREIGHT = "FREIGHT", "Freight"
        TOOLING = "TOOLING", "Tooling"
        OTHER = "OTHER", "Other"

    template = models.ForeignKey(
        ProductTemplate, on_delete=models.CASCADE, related_name="cost_elements"
    )
    code = models.SlugField(max_length=50)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    amount_formula = models.TextField()

    class Meta:
        unique_together = [("template", "code")]
        ordering = ["code"]

    def __str__(self):
        return self.code


class TemplateMarginRule(models.Model):
    class Method(models.TextChoices):
        MARGIN_PERCENT = "MARGIN_PERCENT", "Margin %"
        MARKUP_PERCENT = "MARKUP_PERCENT", "Markup %"
        FIXED_PRICE = "FIXED_PRICE", "Fixed Price"

    template = models.OneToOneField(
        ProductTemplate, on_delete=models.CASCADE, related_name="margin_rule"
    )
    method = models.CharField(max_length=30, choices=Method.choices, default=Method.MARGIN_PERCENT)
    value_or_formula = models.TextField(default="25")

    def __str__(self):
        return f"{self.method}: {self.value_or_formula}"
