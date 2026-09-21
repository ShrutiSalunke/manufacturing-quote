from django import forms
from django.forms import inlineformset_factory

from apps.catalog.models import LaborRole, Machine, Material
from apps.core.models import Plant
from apps.costing.engine import FormulaError, validate_formula_against_fields, validate_identifier

from . import labor_bridge, machine_bridge, material_bridge
from .models import (
    Process,
    ProcessField,
    ProcessSubProcessLink,
    SubProcess,
    SubProcessField,
)


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                w.attrs.setdefault("class", "form-check-input")
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault("class", "form-select")
            else:
                w.attrs.setdefault("class", "form-control mq-input")


def field_codes_from_formset(formset) -> set[str]:
    """Collect non-deleted field codes from a validated inline formset."""
    codes: set[str] = set()
    for f in formset.forms:
        if not hasattr(f, "cleaned_data") or not f.cleaned_data:
            continue
        if f.cleaned_data.get("DELETE"):
            continue
        code = (f.cleaned_data.get("code") or "").strip().upper()
        if code:
            codes.add(code)
    return codes


def apply_formula_field_validation(form, formset) -> bool:
    """
    Validate result_formula against formset field codes.
    Adds an error on form.result_formula and returns False if invalid.
    """
    if not form.is_valid() or not formset.is_valid():
        return False
    formula = form.cleaned_data.get("result_formula") or "0"
    codes = field_codes_from_formset(formset)
    try:
        validate_formula_against_fields(formula, codes)
    except FormulaError as exc:
        form.add_error("result_formula", str(exc))
        return False
    return True


def _configure_choice_property_field(
    form,
    *,
    field_name: str,
    choices_fn,
    label: str,
    help_text: str,
):
    if field_name not in form.fields:
        return
    choices = list(choices_fn())
    existing = ""
    if getattr(form, "instance", None) is not None:
        existing = getattr(form.instance, field_name, "") or ""
    allowed = {c[0] for c in choices}
    if existing and existing not in allowed:
        choices.append((existing, f"{existing} (saved)"))
    form.fields[field_name] = forms.ChoiceField(
        choices=choices,
        required=False,
        label=label,
        help_text=help_text,
        widget=forms.Select(attrs={"class": "form-select"}),
        initial=existing or "",
    )


def _configure_material_property_field(form):
    _configure_choice_property_field(
        form,
        field_name="material_property_key",
        choices_fn=material_bridge.material_property_choices,
        label="Auto-fill from material",
        help_text=(
            "Optional. Pick a property from the Material master. Used on the quote when "
            "“Use material properties” is on and a material is selected."
        ),
    )


def _configure_machine_property_field(form):
    _configure_choice_property_field(
        form,
        field_name="machine_property_key",
        choices_fn=machine_bridge.machine_property_choices,
        label="Auto-fill from machine",
        help_text=(
            "Optional. Pick a property from the Machine master. Used on the quote when "
            "“Use machine properties” is on and a machine is selected."
        ),
    )


def _configure_labor_property_field(form):
    _configure_choice_property_field(
        form,
        field_name="labor_property_key",
        choices_fn=labor_bridge.labor_property_choices,
        label="Auto-fill from labor",
        help_text=(
            "Optional. Pick a property from the Labor Roles master. Used on the quote when "
            "“Use labor properties” is on and a labor role is selected."
        ),
    )


def _configure_all_property_fields(form):
    _configure_material_property_field(form)
    _configure_machine_property_field(form)
    _configure_labor_property_field(form)


def _default_plant():
    plant = Plant.objects.filter(is_active=True).order_by("id").first()
    if plant is None:
        plant = Plant.objects.order_by("id").first()
    return plant


class ProcessForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Process
        fields = [
            "code",
            "name",
            "description",
            "is_active",
            "result_formula",
            "result_unit",
            "use_material_properties",
            "use_machine_properties",
            "use_labor_properties",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "result_formula": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "result_formula": (
                "Use only field codes from the Fields section above, plus numbers "
                "(e.g. LENGTH * RATE * 1.1). Catalog values must come via Auto-fill."
            ),
            "use_material_properties": (
                "When enabled, the quote asks for a material and can auto-fill fields that have "
                "Auto-fill from material set."
            ),
            "use_machine_properties": (
                "When enabled, the quote asks for a machine and can auto-fill fields that have "
                "Auto-fill from machine set."
            ),
            "use_labor_properties": (
                "When enabled, the quote asks for a labor role and can auto-fill fields that have "
                "Auto-fill from labor set."
            ),
        }

    def clean_code(self):
        code = (self.cleaned_data["code"] or "").upper()
        if not validate_identifier(code):
            raise forms.ValidationError("Code must match [A-Z][A-Z0-9_]*")
        return code

    def save(self, commit=True):
        obj = super().save(commit=False)
        if not obj.plant_id:
            plant = _default_plant()
            if plant is None:
                raise forms.ValidationError("No plant is configured. Create a plant first.")
            obj.plant = plant
        if commit:
            obj.save()
        return obj


class SubProcessForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SubProcess
        fields = [
            "code",
            "name",
            "description",
            "is_active",
            "result_formula",
            "result_unit",
            "use_material_properties",
            "use_machine_properties",
            "use_labor_properties",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "result_formula": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "result_formula": (
                "Use only field codes from the Fields section above, plus numbers "
                "(e.g. SETUP_MIN * RATE). Catalog values must come via Auto-fill."
            ),
            "use_material_properties": (
                "When enabled, inherits the quote process material for Auto-fill on fields."
            ),
            "use_machine_properties": (
                "When enabled, inherits the quote process machine for Auto-fill on fields."
            ),
            "use_labor_properties": (
                "When enabled, inherits the quote process labor role for Auto-fill on fields."
            ),
        }

    def clean_code(self):
        code = (self.cleaned_data["code"] or "").upper()
        if not validate_identifier(code):
            raise forms.ValidationError("Code must match [A-Z][A-Z0-9_]*")
        return code

    def save(self, commit=True):
        obj = super().save(commit=False)
        if not obj.plant_id:
            plant = _default_plant()
            if plant is None:
                raise forms.ValidationError("No plant is configured. Create a plant first.")
            obj.plant = plant
        if commit:
            obj.save()
        return obj


_FIELD_PROPERTY_KEYS = (
    "material_property_key",
    "machine_property_key",
    "labor_property_key",
)


class ProcessFieldForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProcessField
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
            "material_property_key",
            "machine_property_key",
            "labor_property_key",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _configure_all_property_fields(self)

    def clean_code(self):
        code = (self.cleaned_data["code"] or "").upper()
        if not validate_identifier(code):
            raise forms.ValidationError("Code must match [A-Z][A-Z0-9_]*")
        return code


class ProcessFieldInlineForm(BootstrapFormMixin, forms.ModelForm):
    """Compact field row used on Process create/edit."""

    class Meta:
        model = ProcessField
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
            "material_property_key",
            "machine_property_key",
            "labor_property_key",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empty_permitted = True
        self.fields["code"].required = False
        self.fields["label"].required = False
        _configure_all_property_fields(self)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("DELETE"):
            return cleaned
        code = (cleaned.get("code") or "").strip().upper()
        label = (cleaned.get("label") or "").strip()
        has_any = any(
            [
                code,
                label,
                cleaned.get("unit"),
                cleaned.get("default_value"),
                cleaned.get("min_value") is not None,
                cleaned.get("max_value") is not None,
                *[cleaned.get(k) for k in _FIELD_PROPERTY_KEYS],
            ]
        )
        if not has_any:
            return cleaned
        if not code:
            self.add_error("code", "This field is required.")
        elif not validate_identifier(code):
            self.add_error("code", "Code must match [A-Z][A-Z0-9_]*")
        else:
            cleaned["code"] = code
        if not label:
            self.add_error("label", "This field is required.")
        return cleaned


class SubProcessFieldForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SubProcessField
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
            "material_property_key",
            "machine_property_key",
            "labor_property_key",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _configure_all_property_fields(self)

    def clean_code(self):
        code = (self.cleaned_data["code"] or "").upper()
        if not validate_identifier(code):
            raise forms.ValidationError("Code must match [A-Z][A-Z0-9_]*")
        return code


class SubProcessFieldInlineForm(BootstrapFormMixin, forms.ModelForm):
    """Compact field row used on SubProcess create/edit."""

    class Meta:
        model = SubProcessField
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
            "material_property_key",
            "machine_property_key",
            "labor_property_key",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empty_permitted = True
        self.fields["code"].required = False
        self.fields["label"].required = False
        _configure_all_property_fields(self)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("DELETE"):
            return cleaned
        code = (cleaned.get("code") or "").strip().upper()
        label = (cleaned.get("label") or "").strip()
        has_any = any(
            [
                code,
                label,
                cleaned.get("unit"),
                cleaned.get("default_value"),
                cleaned.get("min_value") is not None,
                cleaned.get("max_value") is not None,
                *[cleaned.get(k) for k in _FIELD_PROPERTY_KEYS],
            ]
        )
        if not has_any:
            return cleaned
        if not code:
            self.add_error("code", "This field is required.")
        elif not validate_identifier(code):
            self.add_error("code", "Code must match [A-Z][A-Z0-9_]*")
        else:
            cleaned["code"] = code
        if not label:
            self.add_error("label", "This field is required.")
        return cleaned

ProcessFieldFormSet = inlineformset_factory(
    Process,
    ProcessField,
    form=ProcessFieldInlineForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)

SubProcessFieldFormSet = inlineformset_factory(
    SubProcess,
    SubProcessField,
    form=SubProcessFieldInlineForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


class ProcessLinkSubProcessesForm(BootstrapFormMixin, forms.Form):
    subprocesses = forms.ModelMultipleChoiceField(
        queryset=SubProcess.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, process, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.process = process
        self.fields["subprocesses"].queryset = SubProcess.objects.filter(
            plant=process.plant, is_active=True
        ).order_by("code")
        self.fields["subprocesses"].initial = list(
            process.subprocesses.values_list("pk", flat=True)
        )


class QuoteAddProcessForm(BootstrapFormMixin, forms.Form):
    process = forms.ModelChoiceField(queryset=Process.objects.none())
    material = forms.ModelChoiceField(queryset=Material.objects.none(), required=False)
    machine = forms.ModelChoiceField(queryset=Machine.objects.none(), required=False)
    labor_role = forms.ModelChoiceField(queryset=LaborRole.objects.none(), required=False)
    notes = forms.CharField(required=False, max_length=255)

    def __init__(self, quote, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.quote = quote
        self.fields["process"].queryset = Process.objects.filter(
            plant=quote.plant, is_active=True
        ).order_by("code")
        mats = Material.objects.filter(plant=quote.plant, is_active=True).order_by("code")
        self.fields["material"].queryset = mats
        self.fields["material"].required = False
        self.fields["material"].empty_label = "— No material —"
        machines = Machine.objects.filter(plant=quote.plant, is_active=True).order_by("code")
        self.fields["machine"].queryset = machines
        self.fields["machine"].required = False
        self.fields["machine"].empty_label = "— No machine —"
        roles = LaborRole.objects.filter(plant=quote.plant, is_active=True).order_by("code")
        self.fields["labor_role"].queryset = roles
        self.fields["labor_role"].required = False
        self.fields["labor_role"].empty_label = "— No labor role —"


class QuoteAddSubProcessForm(BootstrapFormMixin, forms.Form):
    subprocess = forms.ModelChoiceField(queryset=SubProcess.objects.none())
    notes = forms.CharField(required=False, max_length=255)

    def __init__(self, quote_process, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.quote_process = quote_process
        linked = quote_process.process.subprocesses.filter(is_active=True)
        self.fields["subprocess"].queryset = linked.order_by("code")


def build_dynamic_field_form(field_defs, data=None, initial=None, prefix="fld"):
    """Runtime form for process/subprocess field values with min/max/required validation."""

    class DynamicFieldsForm(forms.Form):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            for f in field_defs:
                name = f"fld_{f.code}"
                if f.data_type == "bool":
                    field = forms.BooleanField(required=False, label=f.label)
                elif f.data_type == "number":
                    field = forms.DecimalField(
                        required=f.is_required,
                        label=f.label,
                        min_value=f.min_value,
                        max_value=f.max_value,
                        decimal_places=6,
                        max_digits=18,
                    )
                else:
                    field = forms.CharField(required=f.is_required, label=f.label, max_length=200)
                if f.unit:
                    field.help_text = f.unit
                if f.help_text:
                    field.help_text = (
                        f"{field.help_text} — {f.help_text}" if field.help_text else f.help_text
                    )
                w = field.widget
                if isinstance(w, forms.CheckboxInput):
                    w.attrs.setdefault("class", "form-check-input")
                else:
                    w.attrs.setdefault("class", "form-control mq-input")
                self.fields[name] = field

        def values_by_code(self):
            out = {}
            for f in field_defs:
                name = f"fld_{f.code}"
                val = self.cleaned_data.get(name)
                if f.data_type == "bool":
                    out[f.code] = "1" if val else "0"
                elif val is None:
                    out[f.code] = ""
                else:
                    out[f.code] = str(val)
            return out

    return DynamicFieldsForm(data=data, initial=initial, prefix=prefix)
