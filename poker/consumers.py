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
        logger.info(f"Nowe połączenie WebSocket dla stołu {self.table_name} (channel: {self.channel_name})")
        logger.info(f"Stan połączenia: nick={getattr(self, 'nickname', None)}, role={getattr(self, 'role', None)}, krupier={getattr(self, 'is_croupier', None)}")

    async def disconnect(self, close_code):
        # Usuń z grupy pokera
        await self.channel_layer.group_discard(
            self.table_group_name,
            self.channel_name
        )
        logger.info(f"Rozłączono WebSocket dla stołu {self.table_name} (nick: {getattr(self, 'nickname', None)}, channel: {self.channel_name})")

        # Usuń gracza z cache jeśli znamy jego nick
        nickname = getattr(self, 'nickname', None)
        if nickname:
            table_data = await self.get_table_data()
            if table_data:
                players_data = table_data.get('players', [])
                players_data = [p for p in players_data if p['nickname'] != nickname]
                table_data['players'] = players_data
                await self.save_table_data(table_data)
                logger.info(f"Gracz {nickname} został usunięty po rozłączeniu ze stołu {self.table_name}")
                await self.channel_layer.group_send(
                    self.table_group_name,
                    {
                        'type': 'player_removed',
                        'players': players_data,
                        'all_voted': all(player['has_voted'] for player in players_data)
                    }
                )

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
        role = data.get('role', 'participant')
        is_croupier = data.get('is_croupier', False)
        logger.info(f"handle_join: próba dołączenia nick={nickname}, role={role}, krupier={is_croupier}")
        if not nickname:
            return

        self.nickname = nickname  # Zapamiętaj nick gracza
        self.role = role         # Zapamiętaj rolę gracza
        self.is_croupier = str(is_croupier).lower() in ['1', 'true']

        # Pobierz lub stwórz stół
        table_data = await self.get_or_create_table()
        players_data = table_data.get('players', [])
        
        # Sprawdź czy gracz już istnieje
        if any(p['nickname'] == nickname for p in players_data):
            # Nick już zajęty
            await self.send(text_data=json.dumps({
                'type': 'nickname_taken',
                'message': f'Nick "{nickname}" jest już zajęty przy tym stole. Wybierz inny.'
            }))
            await self.close()
            return

        players_data.append({
            'nickname': nickname,
            'has_voted': False,
            'vote': None,
            'role': role,
            'is_croupier': self.is_croupier
        })
        table_data['players'] = players_data
        await self.save_table_data(table_data)
        logger.info(f"Gracz {nickname} dołączył do stołu {self.table_name} jako {role} (krupier: {self.is_croupier})")

        # Wyślij aktualny stan stołu
        await self.channel_layer.group_send(
            self.table_group_name,
            {
                'type': 'player_joined',
                'players': players_data,
                'all_voted': all(player['has_voted'] for player in players_data if player.get('role', 'participant') == 'participant')
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
        # Wysyłaj jawne głosy tylko do obserwatora
        players = event['players']
        all_voted = event['all_voted']
        role = getattr(self, 'role', 'participant')
        players_to_send = []
        for p in players:
            p_copy = p.copy()
            if role == 'observer':
                # Obserwator widzi głosy zawsze
                pass
            else:
                # Uczestnik widzi głosy tylko jeśli wszyscy zagłosowali
                if not all_voted and p['vote'] is not None:
                    p_copy['vote'] = None
            players_to_send.append(p_copy)
        await self.send(text_data=json.dumps({
            'type': event['type'],
            'players': players_to_send,
            'all_voted': all_voted
        }))

    async def vote_cast(self, event):
        # Wysyłaj jawne głosy tylko do obserwatora
        players = event['players']
        all_voted = event['all_voted']
        role = getattr(self, 'role', 'participant')
        players_to_send = []
        for p in players:
            p_copy = p.copy()
            if role == 'observer':
                pass
            else:
                if not all_voted and p['vote'] is not None:
                    p_copy['vote'] = None
            players_to_send.append(p_copy)
        await self.send(text_data=json.dumps({
            'type': event['type'],
            'players': players_to_send,
            'all_voted': all_voted
        }))

    async def table_reset(self, event):
        logger.warning(f"table_reset event dla kanału {self.channel_name}, nick={getattr(self, 'nickname', None)}, role={getattr(self, 'role', None)}, krupier={getattr(self, 'is_croupier', None)}")
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