from django.core.management.base import BaseCommand
from django.core.management import call_command
from store.models import Audiobook, Book


class Command(BaseCommand):
    help = 'Add clearly labelled audiobook sample listings without claiming an unverified recording is playable.'

    def handle(self, *args, **options):
        if not Book.objects.filter(isbn__startswith='DEMO-').exists():
            call_command('seed_books', verbosity=0)
        created = 0
        books = Book.objects.filter(isbn__startswith='DEMO-').order_by('isbn')[:12]
        for book in books:
            _, was_created = Audiobook.objects.get_or_create(
                book=book,
                defaults={
                    'description':'Demonstration audiobook listing. No recording is configured for playback.',
                    'source_note':'Sample catalogue metadata only; a licensed recording has not been verified.',
                    'active':False,
                },
            )
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(
            f'Audiobook listings ready: {created} created, {Audiobook.objects.count()} total. '
            'Listings without authorized audio remain unavailable for playback.'
        ))
