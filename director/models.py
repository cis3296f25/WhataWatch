from django.db import models

class Director(models.Model):
    name = models.CharField(unique=True, max_length=100)

    def __str__(self):
        return f'{self.name}'
