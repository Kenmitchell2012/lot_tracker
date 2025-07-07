from django import forms
from .models import Document

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ('document_type', 'file') # We only need these two fields in the form
