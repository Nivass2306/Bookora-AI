from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .models import StoreActivity


def _record_auth_event(action, user):
    if user and user.is_authenticated:
        StoreActivity.objects.create(
            actor=user,
            actor_label=user.get_username(),
            subject=user,
            subject_label=user.get_username(),
            action=action,
            target=user.get_username(),
        )


@receiver(user_logged_in, dispatch_uid='bookora_store_user_logged_in')
def record_login(sender, request, user, **kwargs):
    _record_auth_event('login', user)


@receiver(user_logged_out, dispatch_uid='bookora_store_user_logged_out')
def record_logout(sender, request, user, **kwargs):
    _record_auth_event('logout', user)