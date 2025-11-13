# log_watcher.py
import os
import time
import re
import requests
from pathlib import Path
from threading import Thread
from datetime import datetime
from collections import defaultdict

class LogWatcher:
    def __init__(self):
        self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)
        self.running = False
        self.last_positions = {}
        self.points_tracker = defaultdict(int)
        self.online_streamers = set()
        self.last_notifications = {}  # Pour éviter les doublons
        self.min_points = 10  # Ignorer les gains < 10 points
        
        if self.enabled:
            print("✅ Discord notifications activées")
        else:
            print("⚠️  Discord désactivé")
    
    def send_discord(self, title, description, color, fields=None):
        """Envoie un message sur Discord avec anti-spam"""
        if not self.enabled:
            return
        
        # Anti-spam : ne pas envoyer le même message 2 fois en 30s
        cache_key = f"{title}:{description}"
        now = time.time()
        if cache_key in self.last_notifications:
            if now - self.last_notifications[cache_key] < 30:
                return  # Ignorer, trop récent
        
        self.last_notifications[cache_key] = now
        
        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Twitch Points Miner"}
        }
        
        if fields:
            embed["fields"] = fields
        
        try:
            response = requests.post(
                self.webhook_url,
                json={"embeds": [embed]},
                timeout=10
            )
            if response.status_code == 204:
                print(f"✅ Discord: {title}")
        except Exception as e:
            print(f"❌ Discord error: {e}")
    
    def start(self):
        """Démarre le monitoring"""
        self.running = True
        
        # Ne pas afficher trop de debug
        os.makedirs("logs", exist_ok=True)
        
        log_thread = Thread(target=self._watch_logs, daemon=True)
        log_thread.start()
        
        print("🔔 Log monitoring démarré")
    
    def stop(self):
        self.running = False
    
    def _watch_logs(self):
        """Monitore les fichiers de logs"""
        log_dirs = [
            Path("logs"),
            Path("/app/logs"),
            Path("/usr/src/app/logs"),
        ]
        
        while self.running:
            try:
                for log_dir in log_dirs:
                    if log_dir.exists():
                        for log_file in log_dir.glob("*.log"):
                            self._process_log_file(log_file)
                
                time.sleep(5)
            except Exception as e:
                print(f"❌ Log watcher error: {e}")
                time.sleep(10)
    
    def _process_log_file(self, log_file):
        """Traite un fichier de log"""
        try:
            file_key = str(log_file)
            current_size = log_file.stat().st_size
            last_pos = self.last_positions.get(file_key, 0)
            
            if current_size < last_pos:
                last_pos = 0
            
            if current_size > last_pos:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(last_pos)
                    lines = f.readlines()
                    self.last_positions[file_key] = f.tell()
                
                for line in lines:
                    self._parse_log_line(line)
                    
        except Exception as e:
            pass  # Ignorer les erreurs de lecture
    
    def _parse_log_line(self, line):
        """Parse une ligne de log - VERSION FILTRÉE"""
        
        # Nettoyer la ligne
        clean_line = re.sub(r'\x1b\[[0-9;]*m', '', line).strip()
        
        # Ignorer les lignes vides et le bruit
        if not clean_line or len(clean_line) < 10:
            return
        
        # Mots-clés à ignorer (bruit)
        noise_keywords = ['set_online', 'choix', 'TRIVIAL', 'Stream', 'Unknown', 'DEBUG', 'function']
        if any(keyword in clean_line for keyword in noise_keywords):
            return
        
        # 🟢 Streamer ONLINE - Pattern strict
        online_match = re.search(r'\[(\w+)\].*?goes\s+ONLINE.*?Game:\s*(.+?)(?:\||$)', clean_line, re.IGNORECASE)
        if online_match:
            streamer = online_match.group(1).strip()
            game = online_match.group(2).strip()
            
            # Vérifier que c'est un vrai nom de streamer (pas un mot-clé)
            if len(streamer) > 2 and streamer.lower() not in ['info', 'debug', 'error', 'warning']:
                if streamer not in self.online_streamers:
                    self.online_streamers.add(streamer)
                    
                    self.send_discord(
                        "🟢 Streamer En Ligne",
                        f"**{streamer}** a démarré son stream !",
                        0x00FF00,
                        [
                            {"name": "🎮 Jeu", "value": game[:100], "inline": True},
                            {"name": "📺 Streamer", "value": streamer, "inline": True}
                        ]
                    )
                    return
        
        # 🔴 Streamer OFFLINE - Pattern strict
        offline_match = re.search(r'\[(\w+)\].*?goes\s+OFFLINE', clean_line, re.IGNORECASE)
        if offline_match:
            streamer = offline_match.group(1).strip()
            
            if streamer in self.online_streamers:
                self.online_streamers.discard(streamer)
                
                self.send_discord(
                    "🔴 Streamer Hors Ligne",
                    f"**{streamer}** a terminé son stream",
                    0xFF0000,
                    [{"name": "📺 Streamer", "value": streamer, "inline": True}]
                )
                return
        
        # 💰 Points gagnés - Pattern strict (watch time)
        # Format attendu: "Earned X points watching Y" ou "+X points for Y"
        points_watch = re.search(r'(?:Earned|gained)\s+(\d+)\s+points?\s+(?:watching|for)\s+(\w+)', clean_line, re.IGNORECASE)
        if points_watch:
            points = int(points_watch.group(1))
            streamer = points_watch.group(2).strip()
            
            # Filtrer les petits gains et les faux positifs
            if points >= self.min_points and streamer.lower() not in ['info', 'debug', 'error']:
                self.points_tracker[streamer] += points
                
                self.send_discord(
                    "💰 Points Gagnés",
                    f"**+{points}** points sur **{streamer}**",
                    0xFFD700,
                    [
                        {"name": "📝 Raison", "value": "Watch", "inline": True},
                        {"name": "💎 Total", "value": f"{self.points_tracker[streamer]:,} pts", "inline": True}
                    ]
                )
                return
        
        # 🎁 Bonus claim - Pattern strict
        # Format: "Claimed X bonus points on Y"
        bonus_match = re.search(r'Claimed?\s+(\d+)\s+bonus\s+points?\s+(?:on|for)\s+(\w+)', clean_line, re.IGNORECASE)
        if bonus_match:
            points = int(bonus_match.group(1))
            streamer = bonus_match.group(2).strip()
            
            if points >= self.min_points and streamer.lower() not in ['info', 'debug']:
                self.points_tracker[streamer] += points
                
                self.send_discord(
                    "🎁 Bonus Réclamé",
                    f"**+{points}** points bonus !",
                    0x9B59B6,
                    [
                        {"name": "📺 Streamer", "value": streamer, "inline": True},
                        {"name": "💰 Points", "value": f"+{points:,}", "inline": True}
                    ]
                )
                return
        
        # 🎲 Prédiction placée
        # Format: "Placed X points on Y for streamer Z"
        bet_match = re.search(r'Placed\s+(\d+)\s+points?\s+on\s+(.+?)\s+for\s+(\w+)', clean_line, re.IGNORECASE)
        if bet_match:
            points = int(bet_match.group(1))
            choice = bet_match.group(2).strip()
            streamer = bet_match.group(3).strip()
            
            if points >= 10 and len(choice) > 3:
                self.send_discord(
                    "🎲 Prédiction Placée",
                    f"Pari sur **{streamer}**",
                    0x3498DB,
                    [
                        {"name": "✅ Choix", "value": choice[:50], "inline": True},
                        {"name": "💰 Mise", "value": f"{points:,} pts", "inline": True}
                    ]
                )
                return
        
        # 🎉 Prédiction gagnée
        # Format: "Won X points from prediction on Y"
        won_match = re.search(r'Won\s+(\d+)\s+points?\s+(?:from\s+)?(?:prediction\s+)?(?:on|for)\s+(\w+)', clean_line, re.IGNORECASE)
        if won_match:
            points = int(won_match.group(1))
            streamer = won_match.group(2).strip()
            
            if points >= 10:
                self.points_tracker[streamer] += points
                
                self.send_discord(
                    "🎉 Prédiction Gagnée !",
                    f"Bravo ! **+{points:,}** points gagnés",
                    0x00FF00,
                    [
                        {"name": "📺 Streamer", "value": streamer, "inline": True},
                        {"name": "🏆 Gain", "value": f"+{points:,} pts", "inline": True}
                    ]
                )
                return
        
        # 😢 Prédiction perdue
        # Format: "Lost X points on prediction for Y"
        lost_match = re.search(r'Lost\s+(\d+)\s+points?\s+(?:on\s+)?(?:prediction\s+)?(?:for|on)\s+(\w+)', clean_line, re.IGNORECASE)
        if lost_match:
            points = int(lost_match.group(1))
            streamer = lost_match.group(2).strip()
            
            if points >= 10:
                self.send_discord(
                    "😢 Prédiction Perdue",
                    f"Dommage... **-{points:,}** points",
                    0xFF0000,
                    [
                        {"name": "📺 Streamer", "value": streamer, "inline": True},
                        {"name": "💸 Perte", "value": f"-{points:,} pts", "inline": True}
                    ]
                )
                return