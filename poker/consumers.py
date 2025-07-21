import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Table, Player
from django.core.cache import cache

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
        logger.info(f"Nowe połączenie WebSocket dla stołu {self.table_name}")

    async def disconnect(self, close_code):
        # Usuń z grupy pokera
        await self.channel_layer.group_discard(
            self.table_group_name,
            self.channel_name
        )
        logger.info(f"Rozłączono WebSocket dla stołu {self.table_name}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get('action')
            logger.info(f"Otrzymano akcję: {action}")

            if action == 'join':
                await self.handle_join(data)
            elif action == 'vote':
                await self.handle_vote(data)
            elif action == 'reset':
                await self.handle_reset()
            elif action == 'remove_player':
                await self.handle_remove_player(data)
        except Exception as e:
            logger.error(f"Błąd podczas przetwarzania wiadomości: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    async def handle_join(self, data):
        nickname = data.get('nickname')
        if not nickname:
            return

        # Pobierz lub stwórz stół
        table_data = await self.get_or_create_table()
        players_data = table_data.get('players', [])
        
        # Sprawdź czy gracz już istnieje
        if not any(p['nickname'] == nickname for p in players_data):
            players_data.append({
                'nickname': nickname,
                'has_voted': False,
                'vote': None
            })
            table_data['players'] = players_data
            await self.save_table_data(table_data)
            logger.info(f"Gracz {nickname} dołączył do stołu {self.table_name}")

        # Wyślij aktualny stan stołu
        await self.channel_layer.group_send(
            self.table_group_name,
            {
                'type': 'player_joined',
                'players': players_data,
                'all_voted': all(player['has_voted'] for player in players_data)
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
        for player in players_data:
            if player['nickname'] == nickname:
                player['has_voted'] = True
                player['vote'] = vote
                break

        all_voted = all(player['has_voted'] for player in players_data)
        await self.save_table_data(table_data)
        logger.info(f"Gracz {nickname} zagłosował {vote} na stole {self.table_name}")

        # Wyślij aktualizację do wszystkich
        await self.channel_layer.group_send(
            self.table_group_name,
            {
                'type': 'vote_cast',
                'players': players_data,
                'all_voted': all_voted
            }
        )

    async def handle_reset(self):
        table_data = await self.get_table_data()
        if not table_data:
            return

        players_data = table_data.get('players', [])
        for player in players_data:
            player['has_voted'] = False
            player['vote'] = None

        await self.save_table_data(table_data)
        logger.info(f"Zresetowano stół {self.table_name}")

        await self.channel_layer.group_send(
            self.table_group_name,
            {
                'type': 'table_reset',
                'players': players_data,
                'all_voted': False
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
        logger.info(f"Usunięto gracza {nickname_to_remove} ze stołu {self.table_name}")

        await self.channel_layer.group_send(
            self.table_group_name,
            {
                'type': 'player_removed',
                'players': players_data,
                'all_voted': all(player['has_voted'] for player in players_data)
            }
        )

    async def player_joined(self, event):
        await self.send(text_data=json.dumps(event))

    async def vote_cast(self, event):
        await self.send(text_data=json.dumps(event))

    async def table_reset(self, event):
        await self.send(text_data=json.dumps(event))

    async def player_removed(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def get_or_create_table(self):
        table_data = cache.get(f'table_{self.table_name}')
        if not table_data:
            table_data = {
                'players': []
            }
            cache.set(f'table_{self.table_name}', table_data)
        return table_data

    @database_sync_to_async
    def get_table_data(self):
        return cache.get(f'table_{self.table_name}')

    @database_sync_to_async
    def save_table_data(self, table_data):
        cache.set(f'table_{self.table_name}', table_data) 