import uuid
import os
from decimal import Decimal
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from django.utils.deconstruct import deconstructible

@deconstructible
class PrivateFileStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(location=settings.BASE_DIR / 'private_uploads', base_url='/private-files/')

private_storage = PrivateFileStorage()

def validate_private_document(upload):
    if not upload: return
    extension=os.path.splitext(upload.name)[1].lower()
    if extension not in {'.pdf','.txt'} or upload.size > 30*1024*1024 or (extension=='.txt' and upload.size>2*1024*1024):
        raise ValidationError('Upload a PDF up to 30 MB or a UTF-8 TXT file up to 2 MB.')
    position=upload.tell() if hasattr(upload,'tell') else 0
    signature=upload.read(8)
    if hasattr(upload,'seek'): upload.seek(position)
    if extension=='.pdf' and not signature.startswith(b'%PDF-'):
        raise ValidationError('The uploaded PDF does not have a valid PDF signature.')
    if extension=='.txt':
        try:
            upload.read().decode('utf-8')
            if hasattr(upload,'seek'): upload.seek(position)
        except (UnicodeDecodeError, AttributeError):
            if hasattr(upload,'seek'): upload.seek(position)
            raise ValidationError('Text files must use UTF-8 encoding.')

def validate_audio(upload):
    if not upload: return
    extension=os.path.splitext(upload.name)[1].lower()
    if extension not in {'.mp3','.ogg','.wav'} or upload.size>100*1024*1024:
        raise ValidationError('Upload an MP3, OGG, or WAV file up to 100 MB.')
    position=upload.tell() if hasattr(upload,'tell') else 0
    signature=upload.read(12)
    if hasattr(upload,'seek'): upload.seek(position)
    valid=(extension=='.mp3' and (signature.startswith(b'ID3') or signature[:2] in {b'\xff\xfb',b'\xff\xf3',b'\xff\xf2'})) or (extension=='.ogg' and signature.startswith(b'OggS')) or (extension=='.wav' and signature.startswith(b'RIFF') and signature[8:12]==b'WAVE')
    if not valid: raise ValidationError('The uploaded audio file does not match its file type.')

class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    def save(self, *args, **kwargs):
        self.slug = self.slug or slugify(self.name)
        super().save(*args, **kwargs)
    def __str__(self): return self.name

class Book(models.Model):
    class ReadingAccess(models.TextChoices):
        FREE = 'free', 'Free to read'
        PURCHASE = 'purchase', 'Digital purchase required'
        PREMIUM = 'premium', 'Premium digital access'

    title = models.CharField(max_length=200)
    author = models.CharField(max_length=160)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='books')
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    cover_image = models.URLField(blank=True)
    stock = models.PositiveIntegerField(default=0)
    publication_date = models.DateField(null=True, blank=True)
    isbn = models.CharField(max_length=20, blank=True, unique=True, null=True)
    featured = models.BooleanField(default=False)
    bestseller_featured = models.BooleanField(default=False, help_text='Optional bestseller shelf override; normal rankings use completed order quantities.')
    bestseller_eligible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    summary_cache = models.TextField(blank=True)
    summary_cached_at = models.DateTimeField(null=True, blank=True)
    summary_source_hash = models.CharField(max_length=64, blank=True)
    reading_access = models.CharField(max_length=12, choices=ReadingAccess.choices, default=ReadingAccess.PURCHASE)
    subscription_included = models.BooleanField(default=False, help_text='Offer this title in the online subscription library only while authorized digital content is available.')
    detailed_overview = models.TextField(blank=True)
    topics = models.TextField(blank=True, help_text='Verified subjects, one per line.')
    learning_outcomes = models.TextField(blank=True, help_text='Verified outcomes, one per line.')
    intended_audience = models.CharField(max_length=240, blank=True)
    reading_level = models.CharField(max_length=80, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    preview_text = models.TextField(blank=True, help_text='Only add material you are authorized to show as a preview.')
    digital_sections = models.JSONField(default=list, blank=True, help_text='Authorized reader sections as a JSON list of strings.')
    digital_file = models.FileField(upload_to='books/', storage=private_storage, validators=[validate_private_document], blank=True)
    class Meta: ordering = ['title']
    def __str__(self): return self.title
    @property
    def units_sold(self):
        return sum(item.quantity for item in self.order_items.filter(order__status=Order.Status.COMPLETE, order__payment_status=Order.PaymentStatus.SUCCEEDED))

    @property
    def has_readable_content(self):
        return bool(self.digital_file and self.digital_file.storage.exists(self.digital_file.name)) or bool(isinstance(self.digital_sections, list) and self.digital_sections)

    @property
    def has_preview(self):
        return bool(self.preview_text or self.description)

    def clean(self):
        super().clean()
        if not isinstance(self.digital_sections, list) or any(not isinstance(section, str) for section in self.digital_sections):
            raise ValidationError({'digital_sections': 'Reader sections must be a JSON list of text strings.'})
        if self.subscription_included and self.reading_access != self.ReadingAccess.PREMIUM:
            raise ValidationError({'subscription_included': 'Subscription titles must use Premium digital access.'})

class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)
    def __str__(self): return self.email

class WishlistItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookora_wishlist')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['user', 'book'], name='unique_user_wishlist_book')]
    def __str__(self): return f'{self.user} — {self.book}'

class Order(models.Model):
    class Status(models.TextChoices):
        DEMO = 'demo', 'Demo order (unpaid)'
        COMPLETE = 'complete', 'Fulfilled (payment not tracked)'
    class PaymentStatus(models.TextChoices):
        DEMO = 'demo', 'No payment (demo checkout)'
        PENDING = 'pending', 'Payment pending'
        SUCCEEDED = 'succeeded', 'Payment succeeded'
        FAILED = 'failed', 'Payment failed'
        REFUNDED = 'refunded', 'Refund confirmed'
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    checkout_key = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='bookora_orders')
    name = models.CharField(max_length=160)
    email = models.EmailField()
    address = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DEMO)
    payment_status = models.CharField(max_length=12, choices=PaymentStatus.choices, default=PaymentStatus.DEMO)
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return str(self.reference)
    @property
    def total(self): return sum((item.price * item.quantity for item in self.items.all()), Decimal('0.00'))

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name='order_items')
    title = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(99)])
    digital_access_granted = models.BooleanField(
        default=False,
        help_text='Grant only after an independently verified digital entitlement. Print and demo orders do not include online reading.',
    )
    def __str__(self): return f'{self.title} × {self.quantity}'


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100, default='Bookora Premium')
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('99.00'), validators=[MinValueValidator(Decimal('0.00'))])
    currency = models.CharField(max_length=3, default='INR')
    duration_days = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1)])
    benefits = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name


class SubscriptionPayment(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCEEDED = 'succeeded', 'Succeeded'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='bookora_subscription_payments')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='payments')
    previous_subscription = models.ForeignKey('Subscription', null=True, blank=True, on_delete=models.PROTECT, related_name='renewal_payments')
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    provider_reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    return_url = models.CharField(max_length=500, blank=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    currency = models.CharField(max_length=3, default='INR')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        indexes = [models.Index(fields=['user', 'status', 'created_at'])]
    def __str__(self): return f'{self.user} {self.currency} {self.amount} ({self.status})'


class Subscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        CANCELLED = 'cancelled', 'Cancelled'
        EXPIRED = 'expired', 'Expired'
        DEMO = 'demo', 'Legacy demo (unpaid)'
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookora_subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField()
    cancelled_at = models.DateTimeField(null=True, blank=True)
    payment = models.OneToOneField(SubscriptionPayment, null=True, blank=True, on_delete=models.PROTECT, related_name='subscription')
    def __str__(self): return f'{self.user} — {self.plan}'
    @property
    def grace_ends_at(self): return self.ends_at + timezone.timedelta(days=3)
    @property
    def in_grace_period(self): return self.status == self.Status.ACTIVE and self.ends_at <= timezone.now() <= self.grace_ends_at
    @property
    def is_active(self): return self.status == self.Status.ACTIVE and self.payment_id is not None and timezone.now() < self.ends_at
    @property
    def display_status(self):
        if self.status == self.Status.DEMO: return self.Status.DEMO.label
        if self.status == self.Status.ACTIVE and timezone.now() <= self.grace_ends_at: return 'Grace period' if self.ends_at <= timezone.now() else self.Status.ACTIVE.label
        if self.status == self.Status.ACTIVE: return self.Status.EXPIRED.label
        return self.get_status_display()


class SubscriptionBookEntitlement(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='book_entitlements')
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name='subscription_entitlements')
    included_at = models.DateTimeField(default=timezone.now)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['subscription', 'book'], name='unique_subscription_book_entitlement')]
    def __str__(self): return f'{self.subscription.user}: {self.book}'


class ReadingAccessRevocation(models.Model):
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name='access_revocations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='reading_revocations')
    reason = models.CharField(max_length=1000)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='issued_reading_revocations')
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)
    class Meta:
        indexes = [models.Index(fields=['book', 'user', 'active'])]
    def __str__(self): return f'{self.book}: {self.reason[:60]}'


class SubscriptionRefundRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending review'
        APPROVED = 'approved', 'Approved, refund not confirmed'
        REJECTED = 'rejected', 'Rejected'
        COMPLETED = 'completed', 'Refund confirmed'
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='subscription_refund_requests')
    payment = models.ForeignKey(SubscriptionPayment, on_delete=models.PROTECT, related_name='refund_requests')
    request_reason = models.TextField(max_length=2000)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    decision_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='reviewed_subscription_refunds')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    provider_refund_reference = models.CharField(max_length=200, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['payment'], name='unique_subscription_refund_per_payment')]
    def __str__(self): return f'Refund {self.payment_id} ({self.status})'


class PhysicalOrderRefundRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending review'
        APPROVED = 'approved', 'Approved, refund not confirmed'
        REJECTED = 'rejected', 'Rejected'
        COMPLETED = 'completed', 'Refund confirmed'
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name='refund_request')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='physical_refund_requests')
    request_reason = models.TextField(max_length=2000)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    decision_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='reviewed_physical_refunds')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    provider_refund_reference = models.CharField(max_length=200, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f'Print order refund {self.order.reference} ({self.status})'


class SubscriptionAuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='bookora_subscription_audits')
    action = models.CharField(max_length=60)
    target = models.CharField(max_length=240)
    reason = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['action', 'created_at'])]
    def __str__(self): return f'{self.action}: {self.target}'


class ReadingProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookora_reading_progress')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reading_progress')
    section_index = models.PositiveIntegerField(default=0)
    bookmark_section_index = models.PositiveIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'book'], name='unique_user_book_reading_progress')]
    def __str__(self): return f'{self.user} — {self.book}'


class ContactMessage(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'New'
        READ = 'read', 'Read'
        REPLIED = 'replied', 'Replied'
    name = models.CharField(max_length=150)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField(max_length=10000)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']
    def __str__(self): return f'{self.subject} — {self.email}'


class Audiobook(models.Model):
    class Access(models.TextChoices):
        FREE = 'free', 'Free sample'
        PURCHASE = 'purchase', 'Purchase'
        PREMIUM = 'premium', 'Premium'
    book = models.OneToOneField(Book, on_delete=models.CASCADE, related_name='audiobook')
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    access = models.CharField(max_length=12, choices=Access.choices, default=Access.PREMIUM)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])
    audio_file = models.FileField(upload_to='audio/', storage=private_storage, validators=[validate_audio], blank=True)
    sample_file = models.FileField(upload_to='audio/samples/', storage=private_storage, validators=[validate_audio], blank=True)
    sample_seconds = models.PositiveIntegerField(null=True, blank=True)
    source_note = models.CharField(max_length=240, blank=True, help_text='Recording source and license information where applicable.')
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f'{self.book.title} — audiobook'
    @property
    def playable(self):
        return self.active and bool(self.audio_file and self.audio_file.storage.exists(self.audio_file.name))
    @property
    def has_sample(self):
        return bool(self.sample_file and self.sample_file.storage.exists(self.sample_file.name))


class StoreActivity(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bookora_activity_as_actor')
    actor_label = models.CharField(max_length=150, blank=True)
    subject = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bookora_activity_as_subject')
    subject_label = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=60)
    target = models.CharField(max_length=240, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['action', 'created_at']), models.Index(fields=['subject', 'created_at'])]

    def __str__(self):
        return f'{self.action}: {self.target}'
