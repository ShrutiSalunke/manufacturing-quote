from django import forms

from apps.core.models import Plant

from .models import CustomFieldDefinition, LaborRole, Machine, Material


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _name, field in self.fields.items():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs.setdefault("class", "form-check-input")
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault("class", "form-select")
            elif isinstance(w, forms.DateInput):
                w.attrs.setdefault("class", "form-control mq-input")
                w.attrs.setdefault("type", "date")
            else:
                w.attrs.setdefault("class", "form-control mq-input")


class MaterialForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Material
        fields = [
            "plant",
            "code",
            "name",
            "uom",
            "density",
            "category",
            "unit_price",
            "currency",
            "effective_from",
            "effective_to",
            "is_active",
        ]
        widgets = {
            "effective_from": forms.DateInput(attrs={"type": "date"}),
            "effective_to": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "uom": "Unit of measure",
            "unit_price": "Unit price",
            "effective_from": "Effective from",
            "effective_to": "Effective to",
        }
        help_texts = {
            "code": "Stable unique key within the plant (e.g. SS-304).",
            "density": "g/cm³ — used by the weight calculator.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plant"].queryset = Plant.objects.filter(is_active=True)


class MachineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Machine
        fields = [
            "plant",
            "code",
            "name",
            "hourly_rate",
            "setup_rate",
            "efficiency_percent",
            "is_active",
        ]
        labels = {
            "hourly_rate": "Hourly rate",
            "setup_rate": "Setup rate",
            "efficiency_percent": "Efficiency %",
        }
        help_texts = {
            "code": "Stable unique key within the plant (e.g. LASER-01).",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plant"].queryset = Plant.objects.filter(is_active=True)


class LaborRoleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = LaborRole
        fields = [
            "plant",
            "code",
            "name",
            "hourly_rate",
            "is_active",
        ]
        labels = {
            "hourly_rate": "Hourly rate",
        }
        help_texts = {
            "code": "Stable unique key within the plant (e.g. OP-01).",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plant"].queryset = Plant.objects.filter(is_active=True)


class CustomFieldForm(BootstrapFormMixin, forms.ModelForm):
    enum_choices_text = forms.CharField(
        required=False,
        label="Enum choices",
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control mq-input"}),
        help_text="For Enum type only: comma-separated choices (e.g. Red, Blue, Green).",
    )

    class Meta:
        model = CustomFieldDefinition
        fields = [
            "entity_type",
            "plant",
            "key",
            "label",
            "data_type",
            "is_required",
            "is_importable",
            "import_column_header",
            "sort_order",
            "is_active",
        ]
        labels = {
            "entity_type": "Applies to table",
            "key": "Column key",
            "label": "Column label",
            "data_type": "Data type",
            "is_required": "Required when saving rows",
            "is_importable": "Include in Excel import template",
            "import_column_header": "Excel column header",
            "sort_order": "Display order",
            "plant": "Plant (optional)",
        }
        help_texts = {
            "entity_type": "Which master table gets this extra column (Materials, Machines, or Labor Roles).",
            "key": "Stable machine name (letters, numbers, underscores). Used in formulas as MAT_<KEY> for materials.",
            "label": "What users see as the column / field name.",
            "plant": "Leave blank to apply to all plants. Set a plant to limit this column to that plant only.",
            "import_column_header": "Defaults to the column key if left blank.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Focus Custom Fields on master tables the user can edit in the UI.
        self.fields["entity_type"].choices = [
            (CustomFieldDefinition.EntityType.MATERIAL, "Materials"),
            (CustomFieldDefinition.EntityType.MACHINE, "Machines"),
            (CustomFieldDefinition.EntityType.LABOR, "Labor Roles"),
        ]
        self.fields["plant"].queryset = Plant.objects.filter(is_active=True)
        self.fields["plant"].required = False
        self.fields["plant"].empty_label = "All plants"
        if self.instance and self.instance.pk and self.instance.enum_choices:
            self.fields["enum_choices_text"].initial = ", ".join(self.instance.enum_choices)

    def save(self, commit=True):
        obj = super().save(commit=False)
        text = self.cleaned_data.get("enum_choices_text") or ""
        obj.enum_choices = [c.strip() for c in text.split(",") if c.strip()]
        if not obj.import_column_header:
            obj.import_column_header = obj.key
        if commit:
            obj.save()
        return obj
