from django import forms
import re
import uuid

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
                w.attrs.setdefault("class", "form-control mq-input")


class CustomerForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "code",
            "company",
            "name",
            "email",
            "phone",
            "gstin",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "notes",
            "is_active",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "name": "Contact name",
            "company": "Company name",
            "code": "Client code",
            "gstin": "GSTIN",
        }
        help_texts = {
            "code": "Stable unique key (e.g. CLI-ACME). Prefer not to change after quotes exist.",
            "notes": "Internal notes — not shown on customer PDF.",
        }


class QuoteForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Quote
        fields = ["customer", "plant", "valid_until", "notes"]
        labels = {
            "customer": "Client",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plant"].queryset = Plant.objects.filter(is_active=True)
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True).order_by(
            "code"
        )
        self.fields["customer"].required = True
        self.fields["customer"].empty_label = "Select a client…"


WIZARD_CLIENT_FIELDS = (
    "code",
    "company",
    "name",
    "email",
    "phone",
    "gstin",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "postal_code",
    "country",
)


def _auto_client_code(company: str = "", name: str = "") -> str:
    base = (company or name or "CLIENT").strip().upper()
    slug = re.sub(r"[^A-Z0-9]+", "-", base).strip("-")[:16] or "CLIENT"
    return f"CLI-{slug}-{uuid.uuid4().hex[:4].upper()}"


class WizardQuoteDetailsForm(BootstrapFormMixin, forms.Form):
    """
    Quote details + inline client: pick existing via code/company typeahead, or create on save.
    """

    customer_id = forms.IntegerField(required=False, widget=forms.HiddenInput)

    code = forms.CharField(
        label="Client code",
        max_length=50,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control mq-input",
                "autocomplete": "off",
                "placeholder": "Search or enter code…",
            }
        ),
    )
    company = forms.CharField(
        label="Company name",
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control mq-input",
                "autocomplete": "off",
                "placeholder": "Search or enter company…",
            }
        ),
    )
    name = forms.CharField(label="Contact name", max_length=200, required=False)
    email = forms.EmailField(label="Email", required=False)
    phone = forms.CharField(label="Phone", max_length=30, required=False)
    gstin = forms.CharField(label="GSTIN", max_length=20, required=False)
    address_line1 = forms.CharField(label="Address line 1", max_length=255, required=False)
    address_line2 = forms.CharField(label="Address line 2", max_length=255, required=False)
    city = forms.CharField(label="City", max_length=100, required=False)
    state = forms.CharField(label="State", max_length=100, required=False)
    postal_code = forms.CharField(label="Postal code", max_length=30, required=False)
    country = forms.CharField(label="Country", max_length=100, required=False, initial="India")

    plant = forms.ModelChoiceField(
        label="Plant",
        queryset=Plant.objects.none(),
        empty_label=None,
    )
    valid_until = forms.DateField(
        label="Valid until",
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control mq-input"}),
    )
    notes = forms.CharField(
        label="Notes",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control mq-input"}),
    )

    def __init__(self, *args, quote=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.quote = quote
        self.fields["plant"].queryset = Plant.objects.filter(is_active=True).order_by("name")
        if not self.is_bound:
            if quote and quote.plant_id:
                plant = quote.plant
            else:
                plant = Plant.objects.filter(is_active=True).order_by("id").first()
            if plant:
                self.fields["plant"].initial = plant.pk
            if quote:
                self.fields["valid_until"].initial = quote.valid_until
                self.fields["notes"].initial = quote.notes or ""
                cust = quote.customer
                if cust:
                    self.fields["customer_id"].initial = cust.pk
                    for f in WIZARD_CLIENT_FIELDS:
                        self.fields[f].initial = getattr(cust, f, "") or ""
                        self.fields[f].widget.attrs["readonly"] = True
                        self.fields[f].widget.attrs["class"] = (
                            self.fields[f].widget.attrs.get("class", "") + " is-locked"
                        ).strip()
        elif self.data.get("customer_id"):
            for f in WIZARD_CLIENT_FIELDS:
                self.fields[f].widget.attrs["readonly"] = True
                cls = self.fields[f].widget.attrs.get("class", "")
                if "is-locked" not in cls:
                    self.fields[f].widget.attrs["class"] = (cls + " is-locked").strip()

    def clean_customer_id(self):
        cid = self.cleaned_data.get("customer_id")
        if cid in (None, ""):
            return None
        return cid

    def clean(self):
        cleaned = super().clean()
        cid = cleaned.get("customer_id")
        if cid:
            try:
                cleaned["customer"] = Customer.objects.get(pk=cid, is_active=True)
            except Customer.DoesNotExist:
                self.add_error(
                    "code",
                    "Selected client was not found. Search again or enter a new client.",
                )
                cleaned["customer"] = None
        else:
            cleaned["customer"] = None
            company = (cleaned.get("company") or "").strip()
            name = (cleaned.get("name") or "").strip()
            code = (cleaned.get("code") or "").strip()
            if not company and not name and not code:
                self.add_error(
                    "company",
                    "Enter a company name or client code, or pick an existing client from suggestions.",
                )
            if code and Customer.objects.filter(code__iexact=code).exists():
                self.add_error(
                    "code",
                    "This client code already exists. Pick it from suggestions or use another code.",
                )
            if not cleaned.get("country"):
                cleaned["country"] = "India"
        return cleaned

    def resolve_customer(self) -> Customer:
        """Return existing customer or create one from the form fields."""
        existing = self.cleaned_data.get("customer")
        if existing is not None:
            return existing
        code = (self.cleaned_data.get("code") or "").strip() or _auto_client_code(
            self.cleaned_data.get("company") or "",
            self.cleaned_data.get("name") or "",
        )
        base = code
        n = 0
        while Customer.objects.filter(code__iexact=code).exists():
            n += 1
            code = f"{base}-{n}"
        name = (self.cleaned_data.get("name") or "").strip()
        company = (self.cleaned_data.get("company") or "").strip()
        if not name:
            name = company or code or "Client"
        return Customer.objects.create(
            code=code,
            company=company,
            name=name,
            email=(self.cleaned_data.get("email") or "").strip(),
            phone=(self.cleaned_data.get("phone") or "").strip(),
            gstin=(self.cleaned_data.get("gstin") or "").strip(),
            address_line1=(self.cleaned_data.get("address_line1") or "").strip(),
            address_line2=(self.cleaned_data.get("address_line2") or "").strip(),
            city=(self.cleaned_data.get("city") or "").strip(),
            state=(self.cleaned_data.get("state") or "").strip(),
            postal_code=(self.cleaned_data.get("postal_code") or "").strip(),
            country=(self.cleaned_data.get("country") or "India").strip() or "India",
            is_active=True,
        )

    def save_quote(self, *, user, quote=None) -> Quote:
        customer = self.resolve_customer()
        plant = self.cleaned_data["plant"]
        if quote is None:
            quote = Quote(
                created_by=user,
                status=Quote.Status.DRAFT,
            )
        elif quote.status == Quote.Status.ISSUED:
            raise forms.ValidationError("Issued quotes are locked.")
        else:
            quote.status = Quote.Status.DRAFT
        quote.customer = customer
        quote.plant = plant
        quote.currency = plant.currency
        quote.valid_until = self.cleaned_data.get("valid_until")
        quote.notes = self.cleaned_data.get("notes") or ""
        quote.save()
        return quote


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
