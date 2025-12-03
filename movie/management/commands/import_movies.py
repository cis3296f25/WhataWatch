import csv
from django.core.management.base import BaseCommand
from django.db import transaction

from movie.models import Movie
from director.models import Director
from genre.models import Genre


class Command(BaseCommand):
    help = 'Import movies from CSV into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to the CSV file to import'
        )

    def handle(self, *args, **options):
        csv_path = options['csv_file']

        self.stdout.write(self.style.NOTICE(f'Importing movies from: {csv_path}'))

        try:
            with open(csv_path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    if not row.get('name'):
                        continue

                    with transaction.atomic():
                        movie, created = Movie.objects.update_or_create(
                            movie_id=int(row['movie_id']),
                            defaults={
                                'name': row['name'],
                                'slug': row['slug'],
                                'ratings': float(row['ratings']) if row['ratings'] else None,
                                'year': None,  # CSV does not include year
                                'total_views': int(row['total_views']) if row['total_views'] else None,
                                'total_likes': int(row['total_likes']) if row['total_likes'] else None,
                                'in_lists': int(row['in_lists']) if row['in_lists'] else None,
                                'description': None,
                                'length': int(row['length']) if row['length'] else None,
                                'poster_url': row['poster_url'],
                            }
                        )

                        # Directors
                        directors_raw = row['directors']
                        director_names = [d.strip() for d in directors_raw.split(',')]

                        movie.directors.clear()
                        for name in director_names:
                            director, _ = Director.objects.get_or_create(name=name)
                            movie.directors.add(director)

                        # Genres
                        genres_raw = row['genres']
                        genre_names = [g.strip() for g in genres_raw.split(',')]

                        movie.genres.clear()
                        for g in genre_names:
                            genre, _ = Genre.objects.get_or_create(name=g)
                            movie.genres.add(genre)

                        action = 'Created' if created else 'Updated'
                        self.stdout.write(self.style.SUCCESS(f'{action} movie: {movie.name}'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File not found: {csv_path}'))
            return

        self.stdout.write(self.style.SUCCESS('Movie import complete!'))
