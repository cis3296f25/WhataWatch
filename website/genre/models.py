from django.db import models

class Genre(models.Model):
    name = models.CharField(unique=True, max_length=50)

    def __str__(self):
        return f'{self.name}'
