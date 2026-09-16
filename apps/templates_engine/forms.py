from django import forms

from apps.catalog.models import LaborRole, Machine, Material
from apps.core.models import Plant
from apps.costing.engine import validate_identifier

from .models import (
    ProductFamily,
    ProductTemplate,
    TemplateBomItem,
    TemplateCostElement,
    TemplateFormula,
    TemplateMarginRule,
    TemplateOperation,
    TemplateParameter,
)


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs.setdefault("class", "form-check-input")
            elif isinstance(w, forms.Select):
                w.attrs.setdefault("class", "form-select")
            else:
                w.attrs.setdefault("class", "form-control")


class ProductTemplateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProductTemplate
        fields = ["family", "plant", "name", "code"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["family"].queryset = ProductFamily.objects.all()
        self.fields["plant"].queryset = Plant.objects.filter(is_active=True)


class ParameterForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TemplateParameter
        fields = [
            "code",
            "label",
            "data_type",
            "unit",
            "default_value",
            "min_value",
            "max_value",
            "is_required",
            "sort_order",
            "help_text",
        ]

    def clean_code(self):
        code = self.cleaned_data["code"].upper()
        if not validate_identifier(code):
            raise forms.ValidationError("Code must match [A-Z][A-Z0-9_]*")
        return code


class FormulaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TemplateFormula
        fields = ["code", "expression", "return_unit", "description", "sort_order"]

    def clean_code(self):
        code = self.cleaned_data["code"].upper()
        if not validate_identifier(code):
            raise forms.ValidationError("Code must match [A-Z][A-Z0-9_]*")
        return code


class BomItemForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TemplateBomItem
        fields = ["name", "material", "qty_formula", "scrap_formula", "cost_group", "sort_order"]

    def __init__(self, *args, plant=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Material.objects.filter(is_active=True)
        if plant:
            qs = qs.filter(plant=plant)
        self.fields["material"].queryset = qs


class OperationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TemplateOperation
        fields = [
            "sequence",
            "name",
            "machine",
            "labor_role",
            "setup_time_formula_min",
            "cycle_time_formula_min",
            "labor_time_formula_min",
            "notes",
        ]

    def __init__(self, *args, plant=None, **kwargs):
        super().__init__(*args, **kwargs)
        mqs = Machine.objects.filter(is_active=True)
        lqs = LaborRole.objects.filter(is_active=True)
        if plant:
            mqs = mqs.filter(plant=plant)
            lqs = lqs.filter(plant=plant)
        self.fields["machine"].queryset = mqs
        self.fields["labor_role"].queryset = lqs


class CostElementForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TemplateCostElement
        fields = ["code", "name", "category", "amount_formula"]

    def clean_code(self):
        code = self.cleaned_data["code"].upper()
        if not validate_identifier(code):
            raise forms.ValidationError("Code must match [A-Z][A-Z0-9_]*")
        return code


class MarginRuleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TemplateMarginRule
        fields = ["method", "value_or_formula"]


class TestCalculatorForm(forms.Form):
    line_qty = forms.DecimalField(initial=1, min_value=0.0001, widget=forms.NumberInput(attrs={"class": "form-control"}))

    def __init__(self, template, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = template
        for p in template.parameters.all():
            self.fields[f"param_{p.code}"] = forms.CharField(
                label=f"{p.label} ({p.code})" + (f" [{p.unit}]" if p.unit else ""),
                required=p.is_required,
                initial=p.default_value,
                help_text=p.help_text,
                widget=forms.TextInput(attrs={"class": "form-control"}),
            )

    def parameter_values(self):
        vals = {}
        for p in self.template.parameters.all():
            key = f"param_{p.code}"
            if key in self.cleaned_data:
                vals[p.code] = self.cleaned_data[key]
        return vals
