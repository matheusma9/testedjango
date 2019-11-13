from django.core.management.base import BaseCommand
from website.recommender import init_recommender


class Command(BaseCommand):
    help = 'Displays current time'

    def handle(self, *args, **kwargs):
        init_recommender()
