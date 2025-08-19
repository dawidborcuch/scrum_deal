import json
import random
import time
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.cache import cache
from django.contrib.auth.models import AnonymousUser
from .models import VotingHistory, VotingResult

# Logger dla debug informacji
logger = logging.getLogger(__name__)

class PokerConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.table_name = self.scope['url_route']['kwargs']['table_name']
        self.table_group_name = f'poker_{self.table_name}'
        
        # Dołącz do grupy pokera
        await self.channel_layer.group_add(
            self.table_group_name,
            self.channel_name
        )
        
        await self.accept()

    async def disconnect(self, close_code):
        # Usuń z grupy
        await self.channel_layer.group_discard(
            self.table_group_name,
            self.channel_name
        )

        # Usuń gracza z cache jeśli znamy jego nick
        if hasattr(self, 'nickname') and self.nickname:
            table_data = await self.get_table_data()
            if table_data and 'players' in table_data:
                players_data = table_data['players']
                was_croupier = False
                
                # Znajdź i usuń gracza
                for i, player in enumerate(players_data):
                    if player['nickname'] == self.nickname:
                        was_croupier = player.get('is_croupier', False)
                        del players_data[i]
                        break
                
                # Jeśli odchodził krupier i są jeszcze inni gracze, przekaż rolę losowemu graczowi
                if was_croupier and players_data:
                    new_croupier = random.choice(players_data)
                    for p in players_data:
                        p['is_croupier'] = (p['nickname'] == new_croupier['nickname'])
                
                table_data['players'] = players_data
                await self.save_table_data(table_data)
                
                # Aktualizuj ACTIVE_TABLES
                active_tables = await self.get_active_tables()
                if self.table_name in active_tables:
                    if players_data:  # Jeśli są jeszcze gracze
                        active_tables[self.table_name]['players'] = players_data
                        active_tables[self.table_name]['last_updated'] = time.time()
                    else:  # Jeśli nie ma graczy, usuń stół
                        del active_tables[self.table_name]
                    await self.save_active_tables(active_tables)
                
                # Wyślij aktualizację do pozostałych graczy
                await self.channel_layer.group_send(
                    self.table_group_name,
                    {
                        'type': 'player_removed',
                        'nickname': self.nickname,
                        'players': players_data
                    }
                )
        
        # Wyślij aktualizację do strony głównej
        await self.channel_layer.group_send(
            'home_page',
            {
                'type': 'broadcast_table_update'
            }
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get('action')

            if action == 'join':
                await self.handle_join(data)
            elif action == 'vote':
                await self.handle_vote(data)
            elif action == 'reset':
                await self.handle_reset()
            elif action == 'remove_player':
                await self.handle_remove_player(data)
            elif action == 'assign_croupier':
                await self.handle_assign_croupier(data)
            elif action == 'become_croupier':
                await self.handle_become_croupier()
            elif action == 'ping_activity':
                await self.handle_ping_activity(data)
            elif action == 'get_voting_history':
                await self.handle_get_voting_history()
            elif action == 'switch_role':
                await self.handle_switch_role()
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    async def handle_join(self, data):
        nickname = data.get('nickname')
        role = data.get('role', 'participant')
        is_croupier = data.get('is_croupier', False)
        if not nickname:
            return

        # Pobierz lub stwórz stół
        table_data = await self.get_or_create_table()
        players_data = table_data.get('players', [])

        # Sprawdź czy już jest krupier
        croupier_exists = any(p.get('is_croupier', False) for p in players_data)
        if is_croupier in [True, 'true', 'True', 1, '1'] and croupier_exists:
            await self.send(text_data=json.dumps({
                'type': 'croupier_exists',
                'message': 'Przy tym stole jest już krupier. Nie możesz wybrać tej opcji.'
            }))
            await self.close()
            return

        # ATOMICZNA WALIDACJA NICKU - sprawdź ponownie przed dodaniem
        # Dodatkowo sprawdź w ACTIVE_TABLES dla większej pewności
        if any(p['nickname'] == nickname for p in players_data):
            # Nick już zajęty
            await self.send(text_data=json.dumps({
                'type': 'nickname_taken',
                'message': f'Nick "{nickname}" jest już zajęty przy tym stole. Wybierz inny.',
                'nickname': nickname
            }))
            return

        # Dodatkowa walidacja w ACTIVE_TABLES
        active_tables = await self.get_active_tables()
        if self.table_name in active_tables:
            active_players = active_tables[self.table_name].get('players', [])
            if any(p['nickname'] == nickname for p in active_players):
                # Nick już zajęty w ACTIVE_TABLES
                await self.send(text_data=json.dumps({
                    'type': 'nickname_taken',
                    'message': f'Nick "{nickname}" jest już zajęty przy tym stole. Wybierz inny.',
                    'nickname': nickname
                }))
                return

        self.nickname = nickname  # Zapamiętaj nick gracza
        self.role = role         # Zapamiętaj rolę gracza
        self.is_croupier = str(is_croupier).lower() in ['1', 'true']

        players_data.append({
            'nickname': nickname,
            'has_voted': False,
            'vote': None,
            'role': role,
            'is_croupier': self.is_croupier,
            'last_activity': time.time()  # Dodaj czas ostatniej aktywności
        })
        table_data['players'] = players_data
        await self.save_table_data(table_data)
        
        # Aktualizuj globalną listę aktywnych stołów w Redis
        active_tables = await self.get_active_tables()
        active_tables[self.table_name] = {
            'players': players_data,
            'last_updated': time.time(),
            'password': table_data.get('password')  # Dodaj hasło do globalnej listy
        }
        await self.save_active_tables(active_tables)
        
        logger.info(f"DEBUG: handle_join - Dodano stół {self.table_name} do ACTIVE_TABLES: {active_tables[self.table_name]}")
        
        # Sprawdź czy głosowanie było już zakończone
        voting_completed = table_data.get('voting_completed', False)
        
        # Wyślij aktualny stan stołu
        await self.channel_layer.group_send(
            self.table_group_name,
            {
                'type': 'player_joined',
                'players': players_data,
                'all_voted': all(player['has_voted'] for player in players_data if player.get('role', 'participant') == 'participant'),
                'voting_completed': voting_completed
            }
        )
        
        # Wyślij aktualizację do strony głównej
        logger.info(f"DEBUG: handle_join - wysyłam broadcast_table_update do grupy home_page")
        await self.channel_layer.group_send(
            'home_page',
            {
                'type': 'broadcast_table_update'
            }
        )

    async def handle_vote(self, data):
        nickname = data.get('nickname')
        vote = data.get('vote')
        
        if not nickname or vote is None:
            return

        table_data = await self.get_table_data()
        if not table_data:
            return

        players_data = table_data.get('players', [])
        # Sprawdź czy gracz jest uczestnikiem
        for player in players_data:
            if player['nickname'] == nickname:
                if player.get('role', 'participant') == 'observer':
                    # Obserwator nie może głosować
                    return
                player['has_voted'] = True
                player['vote'] = vote
                break

        all_voted = all(player['has_voted'] for player in players_data if player.get('role', 'participant') == 'participant')
        
        # Jeśli wszyscy zagłosowali, oznacz głosowanie jako zakończone
        if all_voted:
            table_data['voting_completed'] = True
        
        await self.save_table_data(table_data)
        
        # Aktualizuj globalną listę aktywnych stołów
        active_tables = await self.get_active_tables()
        existing_password = active_tables.get(self.table_name, {}).get('password')
        active_tables[self.table_name] = {
            'players': players_data,
            'last_updated': time.time(),
            'password': existing_password
        }
        await self.save_active_tables(active_tables)
        
        # Wyślij aktualizację do wszystkich
        await self.channel_layer.group_send(
            self.table_group_name,
            {
                'type': 'vote_cast',
                'players': players_data,
                'all_voted': all_voted,
                'voting_completed': table_data.get('voting_completed', False)
            }
        )
        
        # Wyślij aktualizację do strony głównej
        await self.channel_layer.group_send(
            'home_page',
            {
                'type': 'broadcast_table_update'
            }
        )

    async def handle_reset(self):
        # Pozwól resetować tylko krupierowi
        if not getattr(self, 'is_croupier', False):
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Tylko krupier może resetować stół!'
            }))
            return
        table_data = await self.get_table_data()
        if not table_data:
            return

        players_data = table_data.get('players', [])
        
        # Zapisz historię głosowania przed resetem
        await self.save_voting_history(players_data)
        
        for player in players_data:
            player['has_voted'] = False
            player['vote'] = None

        # Resetuj stan głosowania
        table_data['voting_completed'] = False
        
        await self.save_table_data(table_data)
        
        # Aktualizuj globalną listę aktywnych stołów
        active_tables = await self.get_active_tables()
        existing_password = active_tables.get(self.table_name, {}).get('password')
        active_tables[self.table_name] = {
            'players': players_data,
            'last_updated': time.time(),
            'password': existing_password
        }
        await self.save_active_tables(active_tables)
        
        # Wyślij aktualizację do wszystkich
        await self.channel_layer.group_send(
            self.table_group_name,
            {
                'type': 'table_reset',
                'players': players_data,
                'all_voted': False,
                'voting_completed': False
            }
        )

    async def handle_remove_player(self, data):
        nickname_to_remove = data.get('nickname_to_remove')
        if not nickname_to_remove:
            return

        table_data = await self.get_table_data()
        if not table_data:
            return

        players_data = table_data.get('players', [])
        players_data = [p for p in players_data if p['nickname'] != nickname_to_remove]
        table_data['players'] = players_data

        await self.save_table_data(table_data)
        
        # Aktualizuj globalną listę aktywnych stołów
        active_tables = await self.get_active_tables()
        if players_data:
            existing_password = active_tables.get(self.table_name, {}).get('password')
            active_tables[self.table_name] = {
                'players': players_data,
                'last_updated': time.time(),
                'password': existing_password
            }
        else:
            # Usuń stół z globalnej listy jeśli nie ma graczy
            if self.table_name in active_tables:
                del active_tables[self.table_name]
        await self.save_active_tables(active_tables)
        
        # Sprawdź czy głosowanie było już zakończone
        voting_completed = table_data.get('voting_completed', False)
        
        # Wyślij specjalny komunikat do usuniętego gracza
        await self.channel_layer.group_send(
            self.table_group_name,
            {
                'type': 'player_removed',
                'players': players_data,
                'all_voted': all(player['has_voted'] for player in players_data),
                'voting_completed': voting_completed,
                'removed_nickname': nickname_to_remove  # Dodaj informację o usuniętym graczu
            }
        )

    async def handle_assign_croupier(self, data):
        # Tylko obecny krupier może nadać rolę
        if not getattr(self, 'is_croupier', False):
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Tylko obecny krupier może przekazać rolę krupiera!'
            }))
            return
        nickname_to_assign = data.get('nickname_to_assign')
        if not nickname_to_assign:
            return
        table_data = await self.get_table_data()
        if not table_data:
            return
        players_data = table_data.get('players', [])
        for p in players_data:
            p['is_croupier'] = (p['nickname'] == nickname_to_assign)
        await self.save_table_data(table_data)
        
        # Aktualizuj globalną listę aktywnych stołów
        active_tables = await self.get_active_tables()
        existing_password = active_tables.get(self.table_name, {}).get('password')
        active_tables[self.table_name] = {
            'players': players_data,
            'last_updated': time.time(),
            'password': existing_password
        }
        await self.save_active_tables(active_tables)
        
        # Sprawdź czy głosowanie było już zakończone
        voting_completed = table_data.get('voting_completed', False)
        
        # Wyślij aktualizację do pozostałych graczy
        await self.channel_layer.group_send(
            self.table_group_name,
            {
                'type': 'player_joined',
                'players': players_data,
                'all_voted': all(player['has_voted'] for player in players_data if player.get('role', 'participant') == 'participant'),
                'voting_completed': voting_completed
            }
        )
        
        # Wyślij aktualizację do strony głównej
        await self.channel_layer.group_send(
            'home_page',
            {
                'type': 'broadcast_table_update'
            }
        )

    async def handle_become_croupier(self):
        # Sprawdź czy gracz jest już krupierem
        if getattr(self, 'is_croupier', False):
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Jesteś już krupierem!'
            }))
            return
        
        # Pobierz aktualne dane stołu
        table_data = await self.get_table_data()
        if not table_data:
            return
        
        players_data = table_data.get('players', [])
        
        # Sprawdź czy już jest krupier przy stole
        croupier_exists = any(p.get('is_croupier', False) for p in players_data)
        if croupier_exists:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Przy tym stole jest już krupier!'
            }))
            return
        
        # Znajdź gracza i nadaj mu rolę krupiera
        current_player = None
        for p in players_data:
            if p['nickname'] == getattr(self, 'nickname', None):
                p['is_croupier'] = True
                current_player = p
                break
        
        if not current_player:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Nie znaleziono gracza!'
            }))
            return
        
        # Zaktualizuj stan gracza w konsumencie
        self.is_croupier = True
        
        # Zapisz zmiany
        await self.save_table_data(table_data)
        
        # Aktualizuj globalną listę aktywnych stołów
        active_tables = await self.get_active_tables()
        existing_password = active_tables.get(self.table_name, {}).get('password')
        active_tables[self.table_name] = {
            'players': players_data,
            'last_updated': time.time(),
            'password': existing_password
        }
        await self.save_active_tables(active_tables)
        
        # Sprawdź czy głosowanie było już zakończone
        voting_completed = table_data.get('voting_completed', False)
        
        # Wyślij aktualizację do wszystkich graczy
        await self.channel_layer.group_send(
            self.table_group_name,
            {
                'type': 'player_joined',
                'players': players_data,
                'all_voted': all(player['has_voted'] for player in players_data if player.get('role', 'participant') == 'participant'),
                'voting_completed': voting_completed
            }
        )
        
        # Wyślij aktualizację do strony głównej
        await self.channel_layer.group_send(
            'home_page',
            {
                'type': 'broadcast_table_update'
            }
        )

    async def player_joined(self, event):
        # Wysyłaj jawne głosy tylko do obserwatora
        players = event['players']
        all_voted = event['all_voted']
        voting_completed = event.get('voting_completed', False)
        role = getattr(self, 'role', 'participant')
        # USTAWIENIE self.is_croupier na podstawie aktualnych danych
        current_player = next((p for p in players if p['nickname'] == getattr(self, 'nickname', None)), None)
        self.is_croupier = current_player['is_croupier'] if current_player else False
        players_to_send = []
        for p in players:
            p_copy = p.copy()
            if role == 'observer':
                # Obserwator widzi głosy zawsze
                pass
            else:
                # Uczestnik widzi głosy tylko jeśli wszyscy zagłosowali lub głosowanie jest zakończone
                if not (all_voted or voting_completed) and p['vote'] is not None:
                    p_copy['vote'] = None
            players_to_send.append(p_copy)
        await self.send(text_data=json.dumps({
            'type': event['type'],
            'players': players_to_send,
            'all_voted': all_voted,
            'voting_completed': voting_completed
        }))

    async def vote_cast(self, event):
        # Wysyłaj jawne głosy tylko do obserwatora
        players = event['players']
        all_voted = event['all_voted']
        voting_completed = event.get('voting_completed', False)
        role = getattr(self, 'role', 'participant')
        # USTAWIENIE self.is_croupier na podstawie aktualnych danych
        current_player = next((p for p in players if p['nickname'] == getattr(self, 'nickname', None)), None)
        self.is_croupier = current_player['is_croupier'] if current_player else False
        players_to_send = []
        for p in players:
            p_copy = p.copy()
            if role == 'observer':
                pass
            else:
                if not (all_voted or voting_completed) and p['vote'] is not None:
                    p_copy['vote'] = None
            players_to_send.append(p_copy)
        await self.send(text_data=json.dumps({
            'type': event['type'],
            'players': players_to_send,
            'all_voted': all_voted,
            'voting_completed': voting_completed
        }))

    async def table_reset(self, event):
        # USTAWIENIE self.is_croupier na podstawie aktualnych danych
        players = event['players']
        current_player = next((p for p in players if p['nickname'] == getattr(self, 'nickname', None)), None)
        self.is_croupier = current_player['is_croupier'] if current_player else False
        await self.send(text_data=json.dumps(event))

    async def player_removed(self, event):
        # USTAWIENIE self.is_croupier na podstawie aktualnych danych
        players = event['players']
        current_player = next((p for p in players if p['nickname'] == getattr(self, 'nickname', None)), None)
        self.is_croupier = current_player['is_croupier'] if current_player else False
        await self.send(text_data=json.dumps(event))

    async def get_or_create_table(self):
        table_data = await self.get_table_data()
        if not table_data:
            # Sprawdź czy stół istnieje w ACTIVE_TABLES
            active_tables = await self.get_active_tables()
            if self.table_name in active_tables:
                # Pobierz dane z ACTIVE_TABLES
                active_table = active_tables[self.table_name]
                table_data = {
                    'players': active_table.get('players', []),
                    'password': active_table.get('password')
                }
                # Zapisz w cache
                await self.save_table_data(table_data)
            else:
                # Stół nie istnieje - stwórz nowy
                table_data = {
                    'players': []
                }
                await self.save_table_data(table_data)
        return table_data

    @database_sync_to_async
    def get_table_data(self):
        return cache.get(f'table_{self.table_name}')

    @database_sync_to_async
    def save_table_data(self, table_data):
        cache.set(f'table_{self.table_name}', table_data)

    @database_sync_to_async
    def get_active_tables(self):
        """Pobiera aktywną listę stołów z Redis"""
        return cache.get('active_tables', {})

    @database_sync_to_async
    def save_active_tables(self, active_tables):
        """Zapisuje aktywną listę stołów do Redis"""
        cache.set('active_tables', active_tables, timeout=3600)  # 1 godzina

    async def save_voting_history(self, players_data):
        """Zapisuje historię głosowania do bazy danych"""
        # Sprawdź czy ktoś głosował
        voted_players = [p for p in players_data if p.get('has_voted') and p.get('vote') is not None]
        if not voted_players:
            return  # Nie zapisuj jeśli nikt nie głosował
        
        # Pobierz następny numer rundy
        next_round = await self.get_next_voting_round()
        
        # Zapisz historię głosowania
        await self.create_voting_history(next_round, voted_players)

    @database_sync_to_async
    def get_next_voting_round(self):
        """Pobiera następny numer rundy głosowania dla stołu"""
        last_history = VotingHistory.objects.filter(table_name=self.table_name).order_by('-voting_round').first()
        return (last_history.voting_round + 1) if last_history else 1

    @database_sync_to_async
    def create_voting_history(self, voting_round, voted_players):
        """Tworzy nowy wpis w historii głosowań"""
        history = VotingHistory.objects.create(
            table_name=self.table_name,
            voting_round=voting_round
        )
        
        # Zapisz wyniki głosowania
        for player in voted_players:
            VotingResult.objects.create(
                voting_history=history,
                player_nickname=player['nickname'],
                vote_value=player['vote']
            )

    async def handle_get_voting_history(self):
        """Obsługuje żądanie pobrania historii głosowań"""
        history = await self.get_voting_history()
        await self.send(text_data=json.dumps({
            'type': 'voting_history',
            'history': history
        }))

    @database_sync_to_async
    def get_voting_history(self):
        """Pobiera historię głosowań dla stołu"""
        histories = VotingHistory.objects.filter(table_name=self.table_name).order_by('-voting_round')[:10]
        result = []
        
        for history in histories:
            voting_data = {
                'round': history.voting_round,
                'created_at': history.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'results': []
            }
            
            for result_obj in history.results.all():
                voting_data['results'].append({
                    'player': result_obj.player_nickname,
                    'vote': result_obj.vote_value
                })
            
            result.append(voting_data)
        
        return result

    async def handle_ping_activity(self, data):
        """Obsługa pingowania aktywności użytkownika"""
        nickname = data.get('nickname')
        if not nickname:
            return
        
        # Zaktualizuj czas aktywności gracza
        table_data = await self.get_table_data()
        if table_data:
            players_data = table_data.get('players', [])
            for player in players_data:
                if player['nickname'] == nickname:
                    player['last_activity'] = time.time()
                    break
            
            await self.save_table_data(table_data)
            
            # Aktualizuj globalną listę aktywnych stołów
            active_tables = await self.get_active_tables()
            existing_password = active_tables.get(self.table_name, {}).get('password')
            active_tables[self.table_name] = {
                'players': players_data,
                'last_updated': time.time(),
                'password': existing_password
            }
            await self.save_active_tables(active_tables)
            
    async def handle_switch_role(self):
        """Obsługuje przełączanie roli między obserwatorem a uczestnikiem."""
        # Każdy gracz może przełączać swoją rolę
        if not getattr(self, 'nickname', None):
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Nie jesteś zalogowany!'
            }))
            return

        # Pobierz aktualne dane stołu
        table_data = await self.get_table_data()
        if not table_data:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Nie można pobrać danych stołu.'
            }))
            return

        players_data = table_data.get('players', [])
        current_player_nickname = getattr(self, 'nickname', None)

        if not current_player_nickname:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Nie znaleziono gracza w stanie.'
            }))
            return

        # Znajdź gracza i zmień jego rolę
        current_player_data = None
        for p in players_data:
            if p['nickname'] == current_player_nickname:
                current_player_data = p
                break

        if not current_player_data:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Nie znaleziono gracza w danych stołu.'
            }))
            return

        # Zmień rolę gracza
        current_player_data['role'] = 'participant' if current_player_data['role'] == 'observer' else 'observer'
        current_player_data['has_voted'] = False # Resetuj głos
        current_player_data['vote'] = None # Resetuj głos

        # Zaktualizuj stan gracza w konsumencie
        self.role = current_player_data['role']
        self.is_croupier = False # Ustaw krupiera na False, jeśli gracz stał się uczestnikiem

        # Zapisz zmiany
        await self.save_table_data(table_data)
        
        # Aktualizuj globalną listę aktywnych stołów
        active_tables = await self.get_active_tables()
        existing_password = active_tables.get(self.table_name, {}).get('password')
        active_tables[self.table_name] = {
            'players': players_data,
            'last_updated': time.time(),
            'password': existing_password
        }
        await self.save_active_tables(active_tables)

        # Wyślij aktualizację do wszystkich graczy
        await self.channel_layer.group_send(
            self.table_group_name,
            {
                'type': 'player_joined',
                'players': players_data,
                'all_voted': all(player['has_voted'] for player in players_data if player.get('role', 'participant') == 'participant')
            }
        )
        
        # Wyślij aktualizację do strony głównej
        await self.channel_layer.group_send(
            'home_page',
            {
                'type': 'broadcast_table_update'
            }
        )

class HomeConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        logger.info(f"DEBUG: HomeConsumer connect - rozpoczynam połączenie")
        # Dołącz do grupy strony głównej
        self.home_group_name = 'home_page'
        await self.channel_layer.group_add(
            self.home_group_name,
            self.channel_name
        )
        
        logger.info(f"DEBUG: HomeConsumer connect - dołączono do grupy {self.home_group_name}")
        await self.accept()
        logger.info(f"DEBUG: HomeConsumer connect - połączenie zaakceptowane")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            'home_page',
            self.channel_name
        )

    async def receive(self, text_data):
        logger.info(f"DEBUG: HomeConsumer receive - otrzymano: {text_data}")
        try:
            data = json.loads(text_data)
            action = data.get('action')
            logger.info(f"DEBUG: HomeConsumer receive - action: {action}")

            if action == 'get_active_tables':
                await self.handle_get_active_tables()
        except Exception as e:
            logger.info(f"DEBUG: HomeConsumer receive - błąd: {e}")
            # Obsługa błędu
            pass

    async def handle_get_active_tables(self):
        """Wysyła aktualną listę aktywnych stołów do klienta"""
        active_tables = []
        current_time = time.time()
        
        # Pobierz ACTIVE_TABLES z Redis
        redis_active_tables = await self.get_active_tables()
        logger.info(f"DEBUG: handle_get_active_tables - ACTIVE_TABLES: {redis_active_tables}")
        
        for table_name, table_info in redis_active_tables.items():
            # Sprawdź czy stół nie jest zbyt stary (więcej niż 5 minut)
            if current_time - table_info['last_updated'] <= 300:
                participants = [p for p in table_info['players'] if p['role'] != 'observer']
                observers = [p for p in table_info['players'] if p['role'] == 'observer']
                if len(participants) > 0:
                    active_tables.append({
                        'name': table_name,
                        'participants_count': len(participants),
                        'observers_count': len(observers),
                        'players': table_info['players']  # Dodaj pełne dane o graczach
                    })
        
        logger.info(f"DEBUG: Wysyłam active_tables: {active_tables}")
        await self.send(text_data=json.dumps({
            'type': 'active_tables_update',
            'active_tables': active_tables
        }))

    async def broadcast_table_update(self, event):
        """Wysyła aktualizację listy stołów do wszystkich klientów na stronie głównej"""
        logger.info(f"DEBUG: broadcast_table_update - wywołano event: {event}")
        active_tables = []
        current_time = time.time()
        
        # Pobierz ACTIVE_TABLES z Redis
        redis_active_tables = await self.get_active_tables()
        logger.info(f"DEBUG: broadcast_table_update - ACTIVE_TABLES: {redis_active_tables}")
        
        for table_name, table_info in redis_active_tables.items():
            # Sprawdź czy stół nie jest zbyt stary (więcej niż 5 minut)
            if current_time - table_info['last_updated'] <= 300:
                participants = [p for p in table_info['players'] if p['role'] != 'observer']
                observers = [p for p in table_info['players'] if p['role'] == 'observer']
                if len(participants) > 0:
                    active_tables.append({
                        'name': table_name,
                        'participants_count': len(participants),
                        'observers_count': len(observers),
                        'players': table_info['players']  # Dodaj pełne dane o graczach
                    })
        
        logger.info(f"DEBUG: broadcast_table_update - wysyłam: {active_tables}")
        await self.send(text_data=json.dumps({
            'type': 'active_tables_update',
            'active_tables': active_tables
        }))

    @database_sync_to_async
    def get_active_tables(self):
        """Pobiera aktywną listę stołów z Redis"""
        return cache.get('active_tables', {}) 