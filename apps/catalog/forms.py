import json

from django import forms

from apps.core.models import Plant

from .models import CustomFieldDefinition


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
