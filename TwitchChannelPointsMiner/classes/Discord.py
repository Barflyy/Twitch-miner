from textwrap import dedent
from datetime import datetime
import re
import requests
import json
from pathlib import Path

from TwitchChannelPointsMiner.classes.Settings import Events


class Discord(object):
    __slots__ = ["webhook_api", "events", "use_bot"]

    def __init__(self, webhook_api: str, events: list, use_bot: bool = False):
        self.webhook_api = webhook_api
        self.events = [str(e) for e in events]
        self.use_bot = use_bot  # True = bot Discord, False = webhook simple

    def send(self, message: str, event: Events) -> None:
        if str(event) not in self.events:
            return
        
        # Mode bot Discord uniquement (pas de webhook)
        if self.use_bot:
            self._update_bot_data(message, event)
    
    def _update_bot_data(self, message: str, event: Events) -> None:
        """Met à jour le fichier JSON pour le bot Discord"""
        try:
            import os
            # Utiliser DATA_DIR si défini
            data_dir = os.getenv("DATA_DIR")
            base_path = Path(data_dir) if data_dir else Path()
            data_file = base_path / "bot_data.json"
            
            # Charger les données existantes
            if data_file.exists():
                try:
                    with open(data_file, 'r') as f:
                        data = json.load(f)
                except Exception:
                    # Fichier corrompu, on réinitialise
                    data = {'streamers': {}}
            else:
                data = {'streamers': {}}
            
            # Extraire les infos du message
            streamer_match = re.search(r'username=(\w+)', message)
            points_match = re.search(r'channel_points=([\d.]+)([mk]?)', message)
            
            if not streamer_match:
                return
            
            streamer = streamer_match.group(1).lower()
            
            # Initialiser le streamer si nécessaire
            if streamer not in data['streamers']:
                # Nouveau streamer - initialiser avec le solde actuel comme baseline
                current_balance = 0
                if points_match:
                    points_value = float(points_match.group(1))
                    points_unit = points_match.group(2).lower()
                    if points_unit == 'k':
                        points_value *= 1000
                    elif points_unit == 'm':
                        points_value *= 1000000
                    current_balance = int(points_value)
                
                data['streamers'][streamer] = {
                    'online': False,
                    'balance': current_balance,
                    'starting_balance': current_balance,  # Solde au démarrage
                    'total_earned': 0,  # Points gagnés depuis le début
                    'session_points': 0,
                    'watch_points': 0,
                    'bonus_points': 0,
                    'bets_placed': 0,
                    'bets_won': 0,
                    'bets_lost': 0
                }
            
            streamer_data = data['streamers'][streamer]
            
            # Mettre à jour le solde
            if points_match:
                points_value = float(points_match.group(1))
                points_unit = points_match.group(2).lower()
                
                if points_unit == 'k':
                    points_value *= 1000
                elif points_unit == 'm':
                    points_value *= 1000000
                
                streamer_data['balance'] = int(points_value)
            
            # Traiter selon l'événement
            if event == Events.STREAMER_ONLINE:
                streamer_data['online'] = True
                streamer_data['online_since'] = datetime.utcnow().isoformat()
                # Reset session
                streamer_data['session_points'] = 0
                streamer_data['watch_points'] = 0
                streamer_data['bonus_points'] = 0
            
            elif event == Events.STREAMER_OFFLINE:
                streamer_data['online'] = False
                if 'online_since' in streamer_data:
                    del streamer_data['online_since']
            
            elif "GAIN_FOR" in str(event):
                gain_match = re.search(r'\+(\d+)', message)
                if gain_match:
                    points_gained = int(gain_match.group(1))
                    streamer_data['session_points'] = streamer_data.get('session_points', 0) + points_gained
                    streamer_data['total_earned'] = streamer_data.get('total_earned', 0) + points_gained  # Total depuis le début
                    
                    reason_match = re.search(r'Reason: (\w+)', message)
                    if reason_match:
                        reason = reason_match.group(1)
                        if reason in ['WATCH', 'WATCH_STREAK']:
                            streamer_data['watch_points'] = streamer_data.get('watch_points', 0) + points_gained
            
            elif event == Events.BONUS_CLAIM:
                gain_match = re.search(r'\+(\d+)', message)
                if gain_match:
                    points_gained = int(gain_match.group(1))
                    streamer_data['session_points'] = streamer_data.get('session_points', 0) + points_gained
                    streamer_data['bonus_points'] = streamer_data.get('bonus_points', 0) + points_gained
                    streamer_data['total_earned'] = streamer_data.get('total_earned', 0) + points_gained  # Total depuis le début
            
            elif event == Events.BET_START:
                streamer_data['bets_placed'] = streamer_data.get('bets_placed', 0) + 1
                # Essayer d'extraire le montant misé
                bet_amount_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:K|k|M|m)?\s*(?:channel\s*)?points', message, re.IGNORECASE)
                if bet_amount_match:
                    amount_str = bet_amount_match.group(0).lower()
                    amount = float(bet_amount_match.group(1))
                    if 'k' in amount_str:
                        amount *= 1000
                    elif 'm' in amount_str:
                        amount *= 1000000
                    streamer_data['last_bet_amount'] = int(amount)
            
            elif event == Events.BET_WIN:
                streamer_data['bets_won'] = streamer_data.get('bets_won', 0) + 1
                # Extraire le gain du pari
                # Format réel: "WIN, Gained: +2.5K" ou "WIN, Gained: +500"
                # On cherche le pattern après "Gained:" ou un simple "+X"
                win_match = re.search(r'(?:Gained|Won|Result):\s*\+?([\d,.]+)\s*(K|k|M|m)?', message, re.IGNORECASE)
                if not win_match:
                    # Fallback: chercher juste un "+X"
                    win_match = re.search(r'\+\s*([\d,.]+)\s*(K|k|M|m)?', message, re.IGNORECASE)
                
                if win_match:
                    # Nettoyer le nombre (enlever les virgules)
                    win_amount = float(win_match.group(1).replace(',', ''))
                    unit = win_match.group(2)
                    if unit and unit.lower() == 'k':
                        win_amount *= 1000
                    elif unit and unit.lower() == 'm':
                        win_amount *= 1000000
                    win_amount = int(win_amount)
                    streamer_data['bet_profits'] = streamer_data.get('bet_profits', 0) + win_amount
                    streamer_data['total_earned'] = streamer_data.get('total_earned', 0) + win_amount
            
            elif event == Events.BET_LOSE:
                streamer_data['bets_lost'] = streamer_data.get('bets_lost', 0) + 1
                # Extraire la perte du pari
                # Format réel: "LOSE, Lost: -2.5K" ou "LOSE, Lost: -500"
                loss_match = re.search(r'(?:Lost|Result):\s*-?([\d,.]+)\s*(K|k|M|m)?', message, re.IGNORECASE)
                if not loss_match:
                    # Fallback: chercher juste un "-X"
                    loss_match = re.search(r'-\s*([\d,.]+)\s*(K|k|M|m)?', message, re.IGNORECASE)
                
                if loss_match:
                    # Nettoyer le nombre (enlever les virgules)
                    loss_amount = float(loss_match.group(1).replace(',', ''))
                    unit = loss_match.group(2)
                    if unit and unit.lower() == 'k':
                        loss_amount *= 1000
                    elif unit and unit.lower() == 'm':
                        loss_amount *= 1000000
                    loss_amount = int(loss_amount)
                    streamer_data['bet_losses'] = streamer_data.get('bet_losses', 0) + loss_amount
                    # Les pertes sont négatives dans le total
                    streamer_data['total_earned'] = streamer_data.get('total_earned', 0) - loss_amount
            
            # Sauvegarder
            data['last_update'] = datetime.utcnow().isoformat()
            
            with open(data_file, 'w') as f:
                json.dump(data, f, indent=2)
        
        except Exception as e:
            # Ignore silencieusement les erreurs pour ne pas casser le miner
            pass
