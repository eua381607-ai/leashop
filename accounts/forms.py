from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Address, User

BOOTSTRAP_INPUT = {"class": "form-control"}


class SignUpForm(UserCreationForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs=BOOTSTRAP_INPUT))
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs=BOOTSTRAP_INPUT))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs=BOOTSTRAP_INPUT))
    phone_number = forms.CharField(
        max_length=30, required=False, widget=forms.TextInput(attrs=BOOTSTRAP_INPUT)
    )

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "phone_number", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update(BOOTSTRAP_INPUT)
        self.fields["password2"].widget.attrs.update(BOOTSTRAP_INPUT)


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            "full_name",
            "phone_number",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "is_default",
        ]
        widgets = {
            "full_name": forms.TextInput(attrs=BOOTSTRAP_INPUT),
            "phone_number": forms.TextInput(attrs=BOOTSTRAP_INPUT),
            "address_line1": forms.TextInput(attrs=BOOTSTRAP_INPUT),
            "address_line2": forms.TextInput(attrs=BOOTSTRAP_INPUT),
            "city": forms.TextInput(attrs=BOOTSTRAP_INPUT),
            "state": forms.TextInput(attrs=BOOTSTRAP_INPUT),
            "postal_code": forms.TextInput(attrs=BOOTSTRAP_INPUT),
            "country": forms.TextInput(attrs=BOOTSTRAP_INPUT),
            "is_default": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
