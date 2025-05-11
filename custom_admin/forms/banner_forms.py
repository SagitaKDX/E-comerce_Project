from django import forms
from store.models import PromoBanner
from django.utils import timezone

class PromoBannerForm(forms.ModelForm):
    class Meta:
        model = PromoBanner
        fields = [
            'title', 
            'subtitle', 
            'image', 
            'button_text', 
            'link_type', 
            'button_link', 
            'text_color', 
            'button_style', 
            'caption_position', 
            'overlay_opacity',
            'active', 
            'start_date', 
            'end_date', 
            'order'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'subtitle': forms.TextInput(attrs={'class': 'form-control'}),
            'button_text': forms.TextInput(attrs={'class': 'form-control'}),
            'link_type': forms.Select(attrs={'class': 'form-control'}),
            'button_link': forms.TextInput(attrs={'class': 'form-control'}),
            'text_color': forms.Select(attrs={'class': 'form-control'}),
            'button_style': forms.Select(attrs={'class': 'form-control'}),
            'caption_position': forms.Select(attrs={'class': 'form-control'}),
            'overlay_opacity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0', 'max': '1'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance.pk and self.instance.image:
            self.fields['image'].required = False
            
        self.fields['button_link'].required = False
        
        self.fields['start_date'].required = False
        self.fields['end_date'].required = False
        self.fields['order'].required = False
        self.fields['button_text'].required = False
        
        self.fields['title'].help_text = "Main heading displayed on the banner"
        self.fields['subtitle'].help_text = "Subheading or description text"
        self.fields['image'].help_text = "Recommended size: 1200 x 500 pixels"
        self.fields['link_type'].help_text = "Where should this banner link to?"
        self.fields['button_link'].help_text = "Required if link type is Custom URL"
        self.fields['start_date'].help_text = "Optional start date (banner will be hidden before this date)"
        self.fields['end_date'].help_text = "Optional end date (banner will be hidden after this date)"
        self.fields['order'].help_text = "Lower numbers appear first (default order is by creation date)"
        self.fields['button_text'].help_text = "Text to display on the call-to-action button (defaults to 'Shop Now')"
    
    def clean(self):
        cleaned_data = super().clean()
        link_type = cleaned_data.get('link_type')
        button_link = cleaned_data.get('button_link')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if link_type == 'custom' and not button_link:
            self.add_error('button_link', 'Button link is required when link type is Custom URL')
        
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'End date cannot be before start date')
        
        return cleaned_data 