from django.db import models

# Create your models here.

class Table(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Player(models.Model):
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='players')
    nickname = models.CharField(max_length=100)
    joined_at = models.DateTimeField(auto_now_add=True)
    current_vote = models.IntegerField(null=True, blank=True)
    has_voted = models.BooleanField(default=False)

    class Meta:
        unique_together = ('table', 'nickname')

    def __str__(self):
        return f"{self.nickname} at {self.table.name}"
