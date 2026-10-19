from datetime import date
from django.core.management.base import BaseCommand
from store.models import Book, Category, SubscriptionPlan

SAMPLE_BOOKS = [
    ('FIC-01', 'The Glass Orchard', 'Mira Sen', 'Fiction', 'A quiet literary novel about memory, family recipes, and the garden that brings three generations together.', '₹499', 18, date(2023, 4, 18), True),
    ('FIC-02', 'Letters from the Monsoon', 'Dev Malhotra', 'Fiction', 'An epistolary story of two old friends reconnecting through letters written during a rain-soaked summer.', '₹399', 24, date(2024, 6, 2), True),
    ('FIC-03', 'A Map of Small Hours', 'Leela Roy', 'Fiction', 'A thoughtful coming-of-age story set in a coastal town, following one student through a year of change.', '₹549', 12, date(2025, 1, 15), False),
    ('NF-01', 'The Art of Paying Attention', 'Rohan Mehta', 'Non-fiction', 'Practical reflections and exercises for noticing everyday details and making room for focused thought.', '₹625', 15, date(2022, 9, 10), True),
    ('NF-02', 'A Brief History of Ordinary Things', 'Anika Das', 'Non-fiction', 'Short essays tracing how familiar objects shape routines, communities, and the way we live.', '₹475', 20, date(2024, 2, 11), False),
    ('NF-03', 'Walking the Long Way Home', 'Kabir Nair', 'Non-fiction', 'A personal travel journal about walking routes, local conversations, and learning to travel slowly.', '₹575', 9, date(2023, 11, 7), False),
    ('EDU-01', 'Mathematics, Made Clear', 'Nisha Kapoor', 'Education', 'An approachable guide to foundational mathematics, with worked examples and practice problems.', '₹699', 30, date(2021, 7, 1), True),
    ('EDU-02', 'The Curious Learner', 'Aarav Iyer', 'Education', 'A study skills workbook covering note-taking, revision planning, and asking better questions.', '₹425', 22, date(2024, 8, 20), False),
    ('EDU-03', 'Writing with Confidence', 'Farah Qureshi', 'Education', 'A practical introduction to clear academic writing, from shaping a claim to revising a draft.', '₹525', 16, date(2022, 3, 14), False),
    ('TECH-01', 'Python Projects for Everyone', 'Ishan Verma', 'Technology', 'A hands-on introduction to Python through small projects, with explanations for new programmers.', '₹799', 14, date(2025, 2, 5), True),
    ('TECH-02', 'Designing for the Web', 'Tara Menon', 'Technology', 'A practical overview of accessible web interfaces, responsive layouts, and user-focused design decisions.', '₹850', 11, date(2023, 5, 25), False),
    ('TECH-03', 'Data, Patterns, and People', 'Neel Shah', 'Technology', 'An introductory guide to working with data responsibly, from asking useful questions to explaining results.', '₹725', 13, date(2024, 10, 9), False),
]

CATEGORY_DESCRIPTIONS = {
    'Fiction': 'Novels and stories for every kind of curious reader.',
    'Non-fiction': 'Ideas, essays, and real-world perspectives.',
    'Education': 'Helpful guides for learning and teaching.',
    'Technology': 'Books about software, design, data, and digital life.',
}

class Command(BaseCommand):
    help = 'Create or update a small, repeatable sample Bookora catalogue.'

    def handle(self, *args, **options):
        categories = {}
        for name, description in CATEGORY_DESCRIPTIONS.items():
            category, _ = Category.objects.get_or_create(name=name, defaults={'description': description})
            categories[name] = category
        SubscriptionPlan.objects.get_or_create(
            name='Bookora Premium',
            defaults={
                'description':'A demonstration plan for selected online reading.',
                'price':'2.99', 'duration_days':30,
                'benefits':['Read selected premium digital books online','Browse the Premium Reads collection','Premium status shown in your account'],
            },
        )
        for code, title, author, category_name, description, price, stock, published, featured in SAMPLE_BOOKS:
            Book.objects.get_or_create(
                isbn=f'DEMO-{code}',
                defaults={
                    'title': title,
                    'author': author,
                    'category': categories[category_name],
                    'description': description,
                    'price': price.replace('₹', ''),
                    'stock': stock,
                    'publication_date': published,
                    'featured': featured,
                    'bestseller_eligible': True,
                    'cover_image': '',
                    'reading_access': ('free' if code in {'FIC-01','FIC-02','FIC-03','NF-01','NF-02','EDU-01','TECH-01'} else 'premium' if code in {'NF-03','EDU-02'} else 'purchase'),
                },
            )
        self.stdout.write(self.style.SUCCESS(f'Catalogue ready: {len(SAMPLE_BOOKS)} sample books in {len(categories)} categories. Safe to run again.'))
