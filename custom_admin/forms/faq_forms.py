from django import forms
from custom_admin.models import FAQ

class FAQForm(forms.ModelForm):
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 10, 
            'id': 'markdown-editor'
        }),
        help_text='You can use Markdown or LaTeX for formatting. Please refer to Markdown syntax guide for more information.'
    )
    
    class Meta:
        model = FAQ
        fields = ['title', 'content', 'order', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        } 