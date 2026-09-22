from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

User = get_user_model()


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


class UserCreateForm(BootstrapFormMixin, forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        self.fields["username"].help_text = "Used to sign in."

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Email is required.")
        qs = User.objects.filter(email__iexact=email)
        if qs.exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise forms.ValidationError("Username is required.")
        return username

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "Passwords do not match.")
            elif p1:
                try:
                    validate_password(p1)
                except DjangoValidationError as exc:
                    self.add_error("password1", exc)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        # Full-access user on Main (merge-safe with feature/rbac).
        user.role = User.Role.ADMIN
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserEditForm(BootstrapFormMixin, forms.ModelForm):
    password1 = forms.CharField(
        label="New password",
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Leave blank to keep the current password.",
    )
    password2 = forms.CharField(
        label="Confirm new password",
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    is_active = forms.BooleanField(
        required=False,
        label="Active",
        help_text="Inactive users cannot sign in.",
    )

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        if self.instance and self.instance.pk:
            self.fields["is_active"].initial = self.instance.is_active

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Email is required.")
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1") or ""
        p2 = cleaned.get("password2") or ""
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "Passwords do not match.")
            elif p1:
                try:
                    validate_password(p1, user=self.instance)
                except DjangoValidationError as exc:
                    self.add_error("password1", exc)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        # Do not demote to Quoter from this UI.
        if user.role != User.Role.ADMIN and not user.is_superuser:
            user.role = User.Role.ADMIN
        p1 = self.cleaned_data.get("password1")
        if p1:
            user.set_password(p1)
        if commit:
            user.save()
        return user
