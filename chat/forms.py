from django import forms
from .models import ChatUser
import phonenumbers
import re

class SignupForm(forms.ModelForm):
    class Meta:
        model = ChatUser
        fields = ['country_code', 'number', 'name', 'image']

    def clean(self):
        cleaned_data = super().clean()
        country_code = cleaned_data.get('country_code')
        number = cleaned_data.get('number')

        if not country_code or not number:
            raise forms.ValidationError("Please enter both country code and phone number.")

        full_number = f"{country_code}{number}"

        try:
            parsed = phonenumbers.parse(full_number, None)
        except phonenumbers.phonenumberutil.NumberParseException:
            raise forms.ValidationError("Invalid phone number format. Please recheck.")

        if not phonenumbers.is_possible_number(parsed):
            raise forms.ValidationError("Phone number length is invalid for this country.")

        if not phonenumbers.is_valid_number(parsed):
            raise forms.ValidationError("This phone number is not valid for the selected country.")

        # Store normalized international format
        cleaned_data['number'] = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        cleaned_data['country_code'] = country_code

        return cleaned_data

class PhoneNumberForm(forms.Form):
    number = forms.CharField(max_length=15)

    def clean_number(self):
        number = self.cleaned_data['number'].strip()
        # Check digits only
        if not re.fullmatch(r'\d{10}', number):
            raise forms.ValidationError("Please enter a valid 10-digit phone number.")
        return number

class OTPForm(forms.Form):
    otp = forms.CharField(max_length=6, label="Enter OTP")
