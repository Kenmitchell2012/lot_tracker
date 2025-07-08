from django import forms
from .models import Document
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ('document_type', 'file') # We only need these two fields in the form

class SignUpForm(UserCreationForm):
    # We define the fields here to add our custom styling
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'w-full px-4 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-md focus:ring-teal-500 focus:border-teal-500',
        'placeholder': 'Username'
    }))
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'w-full px-4 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-md focus:ring-teal-500 focus:border-teal-500',
        'placeholder': 'you@example.com'
    }))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-4 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-md focus:ring-teal-500 focus:border-teal-500',
        'placeholder': 'Enter password'
    }))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-4 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-md focus:ring-teal-500 focus:border-teal-500',
        'placeholder': 'Confirm password'
    }))

    class Meta(UserCreationForm.Meta):
        fields = ('username', 'email',)



# === ADD THIS NEW LOGIN FORM ===
class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'w-full px-4 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-md focus:ring-teal-500 focus:border-teal-500',
        'placeholder': 'Your Username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-4 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-md focus:ring-teal-500 focus:border-teal-500',
        'placeholder': 'Your Password'
    }))