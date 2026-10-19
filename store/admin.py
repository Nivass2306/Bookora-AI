from django.contrib import admin
from django import forms
from django.utils import timezone
from datetime import timedelta
from .models import (Audiobook, Book, Category, ContactMessage, NewsletterSubscriber, Order,
                     OrderItem, ReadingProgress, Subscription, SubscriptionPlan, SubscriptionPayment,
                     SubscriptionBookEntitlement, ReadingAccessRevocation, SubscriptionRefundRequest,
                     SubscriptionAuditLog, PhysicalOrderRefundRequest, StoreActivity, WishlistItem)


class BookAdminForm(forms.ModelForm):
    audit_reason=forms.CharField(max_length=1000,required=False,label='Reason for subscription collection change')
    class Meta:
        model=Book
        fields='__all__'
    def clean(self):
        cleaned=super().clean()
        if cleaned.get('subscription_included') != self.instance.subscription_included and not cleaned.get('audit_reason','').strip():
            self.add_error('audit_reason','Explain why the book is being added to or removed from the subscription collection.')
        digital_file=cleaned.get('digital_file')
        has_content=bool(cleaned.get('digital_sections')) or bool(digital_file and getattr(digital_file,'name',''))
        if cleaned.get('reading_access') == Book.ReadingAccess.FREE and not has_content:
            self.add_error('digital_sections','Add authorized digital content before marking this title free to read.')
        if cleaned.get('subscription_included') and not has_content:
            self.add_error('digital_sections','Add authorized digital content before including this title in the subscription library.')
        return cleaned


class SubscriptionPlanAdminForm(forms.ModelForm):
    audit_reason=forms.CharField(max_length=1000,required=False,label='Reason for plan or price change')
    class Meta:
        model=SubscriptionPlan
        fields='__all__'
    def clean(self):
        cleaned=super().clean()
        changed=(self.instance.pk is None or cleaned.get('price') != self.instance.price or cleaned.get('currency') != self.instance.currency)
        if changed and not cleaned.get('audit_reason','').strip():
            self.add_error('audit_reason','Explain why this subscription plan or price is changing.')
        return cleaned

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug'); search_fields = ('name',); prepopulated_fields = {'slug': ('name',)}

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    form=BookAdminForm
    list_display = ('title', 'author', 'category', 'price', 'stock', 'reading_access', 'subscription_included', 'featured', 'created_at')
    list_filter = ('category', 'reading_access', 'subscription_included', 'featured', 'created_at'); search_fields = ('title', 'author', 'isbn'); date_hierarchy = 'created_at'
    readonly_fields = ('summary_cache', 'summary_cached_at', 'summary_source_hash')
    def get_fields(self, request, obj=None):
        return [*super().get_fields(request,obj), 'audit_reason']
    def save_model(self, request, obj, form, change):
        previous = Book.objects.filter(pk=obj.pk).values('subscription_included').first() if change else None
        super().save_model(request, obj, form, change)
        old_value = previous['subscription_included'] if previous else False
        if old_value != obj.subscription_included:
            action = 'book_added_to_subscription' if obj.subscription_included else 'book_removed_from_subscription'
            SubscriptionAuditLog.objects.create(actor=request.user,action=action,target=f'{obj.title} (book #{obj.pk})',reason=form.cleaned_data.get('audit_reason','').strip())
        if obj.subscription_included and obj.reading_access == Book.ReadingAccess.PREMIUM and obj.has_readable_content:
            now=timezone.now()
            eligible=Subscription.objects.filter(status=Subscription.Status.ACTIVE,payment__status=SubscriptionPayment.Status.SUCCEEDED,started_at__lte=now,ends_at__gte=now-timedelta(days=3))
            for subscription in eligible:
                SubscriptionBookEntitlement.objects.get_or_create(subscription=subscription,book=obj)

@admin.register(NewsletterSubscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'active', 'created_at'); list_filter = ('active',); search_fields = ('email',); date_hierarchy = 'created_at'

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'name', 'email', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('created_at',)

class OrderItemInline(admin.TabularInline):
    model = OrderItem; extra = 0; readonly_fields = ('book', 'title', 'price', 'quantity')
    fields = ('book', 'title', 'price', 'quantity', 'digital_access_granted')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('reference', 'user', 'email', 'status', 'payment_status', 'created_at'); list_filter = ('status', 'payment_status', 'created_at'); search_fields = ('reference', 'email', 'name'); date_hierarchy = 'created_at'; inlines = [OrderItemInline]
    readonly_fields = ('payment_status','paid_at','payment_reference')

@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'created_at'); search_fields = ('user__username', 'book__title'); date_hierarchy = 'created_at'

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    form=SubscriptionPlanAdminForm
    list_display = ('name', 'price', 'currency', 'duration_days', 'active')
    list_filter = ('active',)
    search_fields = ('name', 'description')
    def get_fields(self, request, obj=None):
        return [*super().get_fields(request,obj), 'audit_reason']
    def save_model(self, request, obj, form, change):
        previous = SubscriptionPlan.objects.filter(pk=obj.pk).values('price','currency').first() if change else None
        super().save_model(request,obj,form,change)
        if not previous or previous['price'] != obj.price or previous['currency'] != obj.currency:
            SubscriptionAuditLog.objects.create(actor=request.user,action='subscription_plan_price_changed' if previous else 'subscription_plan_created',target=f'{obj.name} (plan #{obj.pk})',reason=form.cleaned_data.get('audit_reason','').strip(),details={'price':str(obj.price),'currency':obj.currency,'duration_days':obj.duration_days})

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status', 'started_at', 'ends_at', 'payment')
    list_filter = ('status', 'plan')
    search_fields = ('user__username', 'user__email', 'plan__name')
    readonly_fields = tuple(field.name for field in Subscription._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display=('user','plan','amount','currency','status','created_at','confirmed_at')
    list_filter=('status','currency','created_at'); search_fields=('user__username','provider_reference'); readonly_fields=tuple(field.name for field in SubscriptionPayment._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(SubscriptionBookEntitlement)
class SubscriptionBookEntitlementAdmin(admin.ModelAdmin):
    list_display=('subscription','book','included_at'); list_filter=('book__category','included_at'); readonly_fields=tuple(field.name for field in SubscriptionBookEntitlement._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(ReadingAccessRevocation)
class ReadingAccessRevocationAdmin(admin.ModelAdmin):
    list_display=('book','user','revoked_by','created_at','active'); readonly_fields=tuple(field.name for field in ReadingAccessRevocation._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(SubscriptionRefundRequest)
class SubscriptionRefundRequestAdmin(admin.ModelAdmin):
    list_display=('user','payment','status','created_at','reviewed_by'); list_filter=('status','created_at'); readonly_fields=tuple(field.name for field in SubscriptionRefundRequest._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(PhysicalOrderRefundRequest)
class PhysicalOrderRefundRequestAdmin(admin.ModelAdmin):
    list_display=('user','order','status','created_at','reviewed_by'); list_filter=('status','created_at'); readonly_fields=tuple(field.name for field in PhysicalOrderRefundRequest._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(SubscriptionAuditLog)
class SubscriptionAuditLogAdmin(admin.ModelAdmin):
    list_display=('action','target','actor','created_at'); list_filter=('action','created_at'); search_fields=('target','reason','actor__username'); readonly_fields=tuple(field.name for field in SubscriptionAuditLog._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(Audiobook)
class AudiobookAdmin(admin.ModelAdmin):
    list_display = ('book', 'access', 'duration_minutes', 'active', 'playable', 'created_at')
    list_filter = ('access', 'active', 'book__category')
    search_fields = ('book__title', 'book__author', 'source_note')
    readonly_fields = ('created_at',)

@admin.register(ReadingProgress)
class ReadingProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'section_index', 'updated_at')
    list_filter = ('updated_at',)
    search_fields = ('user__username', 'book__title')
    readonly_fields = ('updated_at',)


@admin.register(StoreActivity)
class StoreActivityAdmin(admin.ModelAdmin):
    list_display = ('action', 'subject_label', 'actor_label', 'target', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('subject_label', 'actor_label', 'target')
    readonly_fields = tuple(field.name for field in StoreActivity._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
