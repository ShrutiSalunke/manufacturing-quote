from django import forms

from apps.core.models import Plant
from apps.templates_engine.models import ProductTemplate

from .models import Customer, Quote, QuoteLine


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs.setdefault("class", "form-check-input")
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault("class", "form-select")
            else:
                w.attrs.setdefault("class", "form-control")


class CustomerForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "name",
            "email",
            "company",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
        ]


class QuoteForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Quote
        fields = ["plant", "valid_until", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plant"].queryset = Plant.objects.filter(is_active=True)


class QuoteLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = QuoteLine
        fields = ["template", "description", "quantity", "sort_order"]

    def __init__(self, *args, plant=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = ProductTemplate.objects.filter(status=ProductTemplate.Status.PUBLISHED)
        if plant:
            qs = qs.filter(plant=plant)
        self.fields["template"].queryset = qs


class QuoteLineParametersForm(forms.Form):
    def __init__(self, template, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = template
        for p in template.parameters.all():
            self.fields[f"param_{p.code}"] = forms.CharField(
                label=f"{p.label} ({p.code})",
                required=p.is_required,
                initial=p.default_value,
                help_text=p.help_text or (p.unit and f"Unit: {p.unit}"),
                widget=forms.TextInput(attrs={"class": "form-control"}),
            )

    def parameter_values(self):
        return {
            p.code: self.cleaned_data[f"param_{p.code}"]
            for p in self.template.parameters.all()
            if f"param_{p.code}" in self.cleaned_data
        }
