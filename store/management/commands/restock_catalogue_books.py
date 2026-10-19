import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from store.models import Book


FIXTURE = Path(__file__).resolve().parents[2] / 'fixtures' / 'catalogue_books.json'


class Command(BaseCommand):
    help = ('Give imported Open Library catalogue books a print stock quantity. Only books from the '
            'catalogue fixture whose stock is exactly zero are changed; no other field or record is touched.')

    def add_arguments(self, parser):
        parser.add_argument('--quantity', type=int, default=10,
                            help='Print copies to set for each out-of-stock catalogue book (default: 10).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Report which books would be restocked without saving changes.')

    @transaction.atomic
    def handle(self, *args, **options):
        quantity = options['quantity']
        if quantity < 1 or quantity > 9999:
            raise CommandError('--quantity must be between 1 and 9999.')
        try:
            catalogue = json.loads(FIXTURE.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f'Unable to read catalogue fixture: {exc}')

        fixture_isbns = {entry.get('isbn') for entries in catalogue.values() for entry in entries if entry.get('isbn')}
        books = Book.objects.select_for_update().filter(isbn__in=fixture_isbns, stock=0)
        count = books.count()
        if options['dry_run']:
            self.stdout.write(f'Dry run: {count} out-of-stock catalogue books would be set to stock {quantity}. No changes saved.')
            return
        updated = books.update(stock=quantity)
        self.stdout.write(self.style.SUCCESS(
            f'Restocked {updated} catalogue books to {quantity} print copies each. '
            'Books with existing stock and non-catalogue books were left unchanged.'
        ))
