from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Book, ContactMessage, Order, SubscriptionPayment

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    class Meta:
        model = User; fields = ('username', 'email', 'password1', 'password2')

class StaffAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise ValidationError('This sign-in is for Bookora staff accounts only.', code='staff_required')

class AccountForm(forms.ModelForm):
    email = forms.EmailField(required=False)
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')

class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order; fields = ('name', 'email', 'address')
        widgets = {'address': forms.Textarea(attrs={'rows': 3})}

class NewsletterForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'id': 'newsletter-email', 'placeholder': 'Your email address', 'aria-label': 'Email address'}))

class ContactMessageForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ('name', 'email', 'subject', 'message')
        widgets = {'message': forms.Textarea(attrs={'rows': 6, 'maxlength': 10000})}

class SubscriptionRefundForm(forms.Form):
    payment = forms.ModelChoiceField(queryset=SubscriptionPayment.objects.none(), label='Subscription payment')
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 4}))
    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['payment'].queryset = SubscriptionPayment.objects.filter(user=user, status=SubscriptionPayment.Status.SUCCEEDED).order_by('-confirmed_at')


class BookManagementForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = (
            'title', 'author', 'category', 'description', 'price', 'cover_image',
            'publication_date', 'isbn', 'featured', 'bestseller_featured',
            'bestseller_eligible', 'reading_access', 'subscription_included',
            'detailed_overview', 'topics', 'learning_outcomes', 'intended_audience',
            'reading_level', 'page_count', 'preview_text', 'digital_sections', 'digital_file',
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'detailed_overview': forms.Textarea(attrs={'rows': 5}),
            'topics': forms.Textarea(attrs={'rows': 3}),
            'learning_outcomes': forms.Textarea(attrs={'rows': 3}),
            'preview_text': forms.Textarea(attrs={'rows': 5}),
        }

    def clean(self):
        cleaned = super().clean()
        file_value = cleaned.get('digital_file')
        content_available = bool(cleaned.get('digital_sections')) or bool(file_value and getattr(file_value, 'name', ''))
        if cleaned.get('reading_access') == Book.ReadingAccess.FREE and not content_available:
            self.add_error('digital_sections', 'Add authorized digital text or a digital file before marking this title free to read.')
        if cleaned.get('subscription_included') and not content_available:
            self.add_error('digital_sections', 'Add authorized digital text or a digital file before including this title in the subscription library.')
        return cleaned
