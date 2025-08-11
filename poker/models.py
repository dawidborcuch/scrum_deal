from django.db import models

# Create your models here.

class Table(models.Model):
    name = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=128, blank=True, null=True)  # Hasło do stołu (opcjonalne)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
    @property
    def has_password(self):
        """Sprawdza czy stół ma ustawione hasło"""
        return bool(self.password)

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

class VotingHistory(models.Model):
    table_name = models.CharField(max_length=100)
    voting_round = models.IntegerField()  # Numer rundy głosowania (1, 2, 3, ...)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('table_name', 'voting_round')
        ordering = ['-voting_round']  # Najnowsze na górze

    def __str__(self):
        return f"Stół {self.table_name} - Runda {self.voting_round}"

class VotingResult(models.Model):
    voting_history = models.ForeignKey(VotingHistory, on_delete=models.CASCADE, related_name='results')
    player_nickname = models.CharField(max_length=100)
    vote_value = models.IntegerField()
    
    class Meta:
        unique_together = ('voting_history', 'player_nickname')

    def __str__(self):
        return f"{self.player_nickname}: {self.vote_value} (Runda {self.voting_history.voting_round})"
