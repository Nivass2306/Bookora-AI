import getpass
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ('Create the local Bookora development superuser once. An existing account is never changed '
            'unless --reset-password is given, which updates only the password of an existing superuser.')

    def add_arguments(self, parser):
        parser.add_argument('--username', default='admin')
        parser.add_argument('--email', default='')
        parser.add_argument('--reset-password', action='store_true',
                            help='Development only: set a new password for an existing superuser. No other field is changed.')
        parser.add_argument('--allow-weak-password', action='store_true',
                            help='Development only: accept a password that fails Django password validation.')

    def _password(self, user):
        password = os.environ.get('BOOKORA_INITIAL_ADMIN_PASSWORD') or getpass.getpass('Set a password for the local Bookora administrator: ')
        if not password:
            raise CommandError('A non-empty password is required.')
        try:
            validate_password(password, user)
        except ValidationError as exc:
            if not self.allow_weak_password:
                raise CommandError('Password failed validation: ' + ' '.join(exc.messages) + ' Use --allow-weak-password only for local development.')
            self.stdout.write(self.style.WARNING('Accepting a password that fails validation (' + ' '.join(exc.messages) + '). Development use only.'))
        return password

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('This development credential command is disabled when DEBUG is false.')
        self.allow_weak_password = options['allow_weak_password']
        User = get_user_model()
        username = options['username']
        existing = User.objects.filter(username=username).first()
        if existing:
            if not (existing.is_superuser and existing.is_staff):
                raise CommandError(f'An account named {username} already exists and is not a superuser. It was left unchanged; choose another username or review it manually.')
            if not options['reset_password']:
                self.stdout.write(self.style.WARNING(f'{username} already has a superuser account; no password or permissions were changed. Use --reset-password to update the password.'))
                return
            existing.set_password(self._password(existing))
            existing.save(update_fields=['password'])
            self.stdout.write(self.style.SUCCESS(f'Password for existing superuser {username} was updated. No other account details were changed; change it before deployment.'))
            return
        password = self._password(User(username=username, email=options['email']))
        User.objects.create_superuser(username=username, email=options['email'], password=password)
        self.stdout.write(self.style.SUCCESS(f'Local superuser {username} created. Password is stored using Django hashing; change it before deployment.'))
