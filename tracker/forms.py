from django import forms
from .models import Document, MonthlyBoard
import datetime
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


class MonthlyBoardForm(forms.ModelForm):
    # Create choices for the last 5 years and next 2 years
    YEAR_CHOICES = [(y, y) for y in range(datetime.date.today().year - 5, datetime.date.today().year + 2)]
    
    # Use dropdowns for month and year for easier selection
    month = forms.ChoiceField(choices=[(i, f'{i:02d}') for i in range(1, 13)])
    year = forms.ChoiceField(choices=YEAR_CHOICES)

    class Meta:
        model = MonthlyBoard
        fields = ['name', 'board_id', 'month', 'year']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full bg-gray-700 text-white border-gray-600 rounded-md p-2', 'placeholder': 'e.g., August 2025 Labeling'}),
            'board_id': forms.TextInput(attrs={'class': 'w-full bg-gray-700 text-white border-gray-600 rounded-md p-2', 'placeholder': 'e.g., 9694731762'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply styling to the choice fields
        self.fields['month'].widget.attrs.update({'class': 'w-full bg-gray-700 text-white border-gray-600 rounded-md p-2'})
        self.fields['year'].widget.attrs.update({'class': 'w-full bg-gray-700 text-white border-gray-600 rounded-md p-2'})