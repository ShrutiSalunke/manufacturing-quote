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


class CustomFieldForm(forms.ModelForm):
    enum_choices_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        help_text="For enum type: comma-separated choices",
    )

    class Meta:
        model = CustomFieldDefinition
        fields = [
            "plant",
            "entity_type",
            "key",
            "label",
            "data_type",
            "is_required",
            "is_importable",
            "import_column_header",
            "sort_order",
            "is_active",
        ]
        widgets = {
            "plant": forms.Select(attrs={"class": "form-select"}),
            "entity_type": forms.Select(attrs={"class": "form-select"}),
            "key": forms.TextInput(attrs={"class": "form-control"}),
            "label": forms.TextInput(attrs={"class": "form-control"}),
            "data_type": forms.Select(attrs={"class": "form-select"}),
            "import_column_header": forms.TextInput(attrs={"class": "form-control"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plant"].queryset = Plant.objects.filter(is_active=True)
        self.fields["plant"].required = False
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
