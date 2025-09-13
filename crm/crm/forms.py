from django import forms
from .models import EmailAccount, Email, EmailFolder
from django.utils import timezone

class EmailAccountForm(forms.ModelForm):
    class Meta:
        model = EmailAccount
        fields = [
            'name', 'email_address', 'protocol',
            'incoming_host', 'incoming_port', 'incoming_use_ssl',
            'outgoing_host', 'outgoing_port', 'outgoing_use_ssl',
            'username', 'password', 'auto_sync'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Account Display Name'
            }),
            'email_address': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'your.email@example.com'
            }),
            'protocol': forms.Select(attrs={'class': 'form-control'}),
            'incoming_host': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'imap.gmail.com'
            }),
            'incoming_port': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '993'
            }),
            'incoming_use_ssl': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'outgoing_host': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'smtp.gmail.com'
            }),
            'outgoing_port': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '587'
            }),
            'outgoing_use_ssl': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Username'
            }),
            'password': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Password'
            }),
            'auto_sync': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class QuickSetupForm(forms.Form):
    """Form for quick setup of popular email providers"""
    PROVIDER_CHOICES = [
        ('gmail', 'Gmail'),
        ('outlook', 'Outlook/Hotmail'),
        ('yahoo', 'Yahoo Mail'),
        ('icloud', 'iCloud Mail'),
        ('custom', 'Custom Setup'),
    ]
    
    provider = forms.ChoiceField(
        choices=PROVIDER_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Account Display Name'
        })
    )
    email_address = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your.email@gmail.com'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password or App Password'
        })
    )

class EmailForm(forms.ModelForm):
    class Meta:
        model = Email
        fields = ['recipient', 'cc', 'bcc', 'subject', 'body']
        widgets = {
            'recipient': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'recipient@example.com'
            }),
            'cc': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'cc1@example.com, cc2@example.com'
            }),
            'bcc': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'bcc1@example.com, bcc2@example.com'
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email Subject'
            }),
            'body': forms.Textarea(attrs={
                'class': 'form-control body-textarea',
                'rows': 15,
                'placeholder': 'Write your message here...'
            }),
        }

class EmailSearchForm(forms.Form):
    query = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search emails...'
        })
    )
    sender = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'From email address'
        })
    )
    subject = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Subject contains'
        })
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    
class EmailFolderForm(forms.ModelForm):
    class Meta:
        model = EmailFolder
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Folder Name'
            })
        }
