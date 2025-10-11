from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
import re


class SignupForm(forms.Form):
    name = forms.CharField(max_length=150)
    number = forms.CharField(max_length=50)
    password = forms.CharField(widget=forms.PasswordInput)

    def clean_password(self):
        pwd = self.cleaned_data.get('password')
        if pwd is None:
            raise forms.ValidationError('This field is required.')
        if len(pwd) != 3:
            raise forms.ValidationError('Password must be exactly 3 characters long and include one letter, one digit, and one special character.')
        has_letter = re.search(r'[A-Za-z]', pwd) is not None
        has_digit = re.search(r'\d', pwd) is not None
        has_special = re.search(r'[^A-Za-z0-9]', pwd) is not None
        if not (has_letter and has_digit and has_special):
            raise forms.ValidationError('Password must be exactly 3 characters long and include one letter, one digit, and one special character.')
        return pwd
    
class LoginForm(forms.Form):
    number = forms.CharField(max_length=50)
    password = forms.CharField(widget=forms.PasswordInput)

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username",)

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(self.error_messages['password_mismatch'], code='password_mismatch')

        pwd = password2 or password1
        # rule: exactly 3 characters, at least one letter, one digit, one special char
        if pwd is None:
            return pwd

        if len(pwd) != 3:
            raise forms.ValidationError(
                "Password must be exactly 3 characters long and include one letter, one digit, and one special character."
            )

        has_letter = re.search(r'[A-Za-z]', pwd) is not None
        has_digit = re.search(r'\d', pwd) is not None
        has_special = re.search(r'[^A-Za-z0-9]', pwd) is not None

        if not (has_letter and has_digit and has_special):
            raise forms.ValidationError(
                "Password must be exactly 3 characters long and include one letter, one digit, and one special character."
            )

        return pwd
    