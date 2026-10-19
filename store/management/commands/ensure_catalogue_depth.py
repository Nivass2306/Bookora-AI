import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from store.models import Book, Category


FIXTURE = Path(__file__).resolve().parents[2] / 'fixtures' / 'catalogue_books.json'


def valid_isbn13(value):
    return (
        len(value) == 13
        and value.isdigit()
        and (sum(int(char) * (1 if index % 2 == 0 else 3)
                 for index, char in enumerate(value[:12])) + int(value[-1])) % 10 == 0
    )


class Command(BaseCommand):
    help = ('Add verified Open Library catalogue entries until each existing Bookora '
            'category has the target number of source-backed books. Existing records are never changed or deleted.')

    def add_arguments(self, parser):
        parser.add_argument('--target', type=int, default=30,
                            help='Minimum number of source-backed books per existing category (default: 30).')
        parser.add_argument('--price', default='299.00',
                            help='Local demo checkout price in INR for new entries (default: 299.00).')
        parser.add_argument('--stock', type=int, default=10,
                            help='Print copies in stock for new entries (default: 10). Existing books are never changed.')

    @transaction.atomic
    def handle(self, *args, **options):
        target = options['target']
        if target < 1:
            raise CommandError('--target must be at least 1.')
        stock = options['stock']
        if stock < 0 or stock > 9999:
            raise CommandError('--stock must be between 0 and 9999.')
        try:
            price = Decimal(options['price'])
        except (InvalidOperation, TypeError):
            raise CommandError('--price must be a valid non-negative amount.')
        if not price.is_finite() or price < 0 or price.as_tuple().exponent < -2:
            raise CommandError('--price must be a valid non-negative amount with at most two decimals.')

        try:
            catalogue = json.loads(FIXTURE.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f'Unable to read catalogue fixture: {exc}')

        added_total = 0
        for slug, entries in catalogue.items():
            category = Category.objects.filter(slug=slug).first()
            if category is None:
                self.stdout.write(f'Skipped {slug}: category does not exist.')
                continue

            initial_count = Book.objects.filter(category=category).count()
            fixture_isbns = [entry.get('isbn') for entry in entries]
            initial_source_count = Book.objects.filter(
                category=category, isbn__in=fixture_isbns,
            ).count()
            source_count = initial_source_count
            added = 0
            for entry in entries:
                if source_count >= target:
                    break
                isbn = entry.get('isbn', '')
                title = entry.get('title', '').strip()
                author = entry.get('author', '').strip()
                description = entry.get('description', '').strip()
                cover_image = entry.get('cover_image', '')
                if not (valid_isbn13(isbn) and title and author and description
                        and cover_image.startswith('https://covers.openlibrary.org/')):
                    raise CommandError(f'Invalid source record in {slug}: {title or "(untitled)"}')
                if Book.objects.filter(isbn=isbn).exists():
                    continue
                if Book.objects.filter(title__iexact=title, author__iexact=author).exists():
                    continue

                Book.objects.create(
                    title=title,
                    author=author,
                    category=category,
                    description=description,
                    price=price,
                    stock=stock,
                    cover_image=cover_image,
                    isbn=isbn,
                )
                added += 1
                added_total += 1
                source_count += 1

            final_count = Book.objects.filter(category=category).count()
            if source_count < target:
                raise CommandError(
                    f'{category.name} has {source_count} source-backed books; '
                    f'fixture could not reach target {target}.'
                )
            self.stdout.write(
                f'{category.name}: {initial_count} -> {final_count} total; '
                f'{source_count} source-backed ({added} added).'
            )

        self.stdout.write(self.style.SUCCESS(
            f'Catalogue depth ensured. Added {added_total} source-backed books. '
            f'New entries use a local demo price and {stock} print copies in stock.'
        ))
