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
        
        if self.enabled:
            print("✅ Discord Log Watcher activé")
            print(f"🔗 Webhook: {self.webhook_url[:50]}...")
        else:
            print("⚠️  DISCORD_WEBHOOK_URL non configuré")
    
    def send_discord(self, title, description, color, fields=None):
        """Envoie un message sur Discord"""
        if not self.enabled:
            print(f"⚠️  Webhook désactivé, message ignoré: {title}")
            return
        
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
            print(f"📤 Envoi Discord: {title}")
            response = requests.post(
                self.webhook_url,
                json={"embeds": [embed]},
                timeout=10
            )
            if response.status_code == 204:
                print(f"✅ Discord envoyé: {title}")
            else:
                print(f"⚠️  Discord status: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Erreur Discord: {e}")
    
    def start(self):
        """Démarre le monitoring en arrière-plan"""
        self.running = True
        
        # Afficher info de démarrage
        print("🔍 Recherche des fichiers de logs...")
        print(f"📂 Dossier actuel: {os.getcwd()}")
        print(f"📁 Contenu: {os.listdir('.')}")
        
        # Thread pour les logs
        log_thread = Thread(target=self._watch_logs, daemon=True)
        log_thread.start()
        
        print("🔔 Log watcher démarré")
    
    def stop(self):
        self.running = False
    
    def _watch_logs(self):
        """Monitore les fichiers de logs"""
        log_dirs = [
            Path("logs"),
            Path("analytics"),
            Path("."),
            Path("/app/logs"),
            Path("/usr/src/app/logs"),
        ]
        
        found_logs = False
        
        while self.running:
            try:
                for log_dir in log_dirs:
                    if log_dir.exists():
                        log_files = list(log_dir.glob("*.log")) + list(log_dir.glob("*.txt"))
                        
                        if log_files and not found_logs:
                            print(f"📋 Logs trouvés dans {log_dir}: {[f.name for f in log_files]}")
                            found_logs = True
                        
                        for log_file in log_files:
                            self._process_log_file(log_file)
                
                if not found_logs:
                    # Première fois, afficher ce qu'on trouve
                    print(f"🔍 Vérification des dossiers...")
                    for log_dir in log_dirs:
                        print(f"  - {log_dir}: {'✅ existe' if log_dir.exists() else '❌ introuvable'}")
                        if log_dir.exists():
                            contents = list(log_dir.iterdir())[:5]
                            print(f"    Contenu: {[f.name for f in contents]}")
                    found_logs = True  # Pour ne pas répéter
                
                time.sleep(5)  # Vérifier toutes les 5 secondes
            except Exception as e:
                print(f"❌ Erreur watch logs: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(10)
    
    def _process_log_file(self, log_file):
        """Traite un fichier de log ligne par ligne"""
        try:
            file_key = str(log_file)
            
            # Obtenir la taille actuelle
            current_size = log_file.stat().st_size
            last_pos = self.last_positions.get(file_key, 0)
            
            # Si le fichier a été tronqué, recommencer à 0
            if current_size < last_pos:
                last_pos = 0
                print(f"🔄 Fichier tronqué détecté: {log_file.name}")
            
            # Si nouveau contenu
            if current_size > last_pos:
                # Lire uniquement les nouvelles lignes
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(last_pos)
                    lines = f.readlines()
                    new_pos = f.tell()
                
                if lines:
                    print(f"📄 {log_file.name}: {len(lines)} nouvelles lignes")
                    self.last_positions[file_key] = new_pos
                
                # Parser chaque nouvelle ligne
                for line in lines:
                    self._parse_log_line(line)
                    
        except Exception as e:
            print(f"❌ Erreur lecture {log_file.name}: {e}")
    
    def _parse_log_line(self, line):
        """Parse une ligne de log et déclenche les notifications"""
        
        # Supprimer les codes couleur ANSI
        clean_line = re.sub(r'\x1b\[[0-9;]*m', '', line)
        
        # Afficher TOUTES les lignes pour debug
        print(f"[LOG] {clean_line.strip()}")
        
        # 🟢 Streamer ONLINE
        online_patterns = [
            r'(\w+)\s+(?:is|goes|status:?)\s+online',
            r'\[([^\]]+)\].*?online',
            r'streaming.*?(\w+)',
        ]
        
        for pattern in online_patterns:
            match = re.search(pattern, clean_line, re.IGNORECASE)
            if match:
                streamer = match.group(1).strip()
                if streamer and len(streamer) > 2 and streamer not in self.online_streamers:
                    self.online_streamers.add(streamer)
                    
                    game = "En direct"
                    game_match = re.search(r'(?:game|playing):\s*([^|\n]+)', clean_line, re.IGNORECASE)
                    if game_match:
                        game = game_match.group(1).strip()
                    
                    print(f"🟢 DÉTECTÉ: {streamer} ONLINE ({game})")
                    self.send_discord(
                        "🟢 Streamer En Ligne",
                        f"**{streamer}** vient de passer en ligne !",
                        0x00FF00,
                        [
                            {"name": "🎮 Jeu", "value": game, "inline": True},
                            {"name": "📺 Streamer", "value": streamer, "inline": True}
                        ]
                    )
                    break
        
        # 🔴 Streamer OFFLINE
        offline_patterns = [
            r'(\w+)\s+(?:is|goes|status:?)\s+offline',
            r'\[([^\]]+)\].*?offline',
        ]
        
        for pattern in offline_patterns:
            match = re.search(pattern, clean_line, re.IGNORECASE)
            if match:
                streamer = match.group(1).strip()
                if streamer and streamer in self.online_streamers:
                    self.online_streamers.discard(streamer)
                    
                    print(f"🔴 DÉTECTÉ: {streamer} OFFLINE")
                    self.send_discord(
                        "🔴 Streamer Hors Ligne",
                        f"**{streamer}** a terminé son stream",
                        0xFF0000,
                        [{"name": "📺 Streamer", "value": streamer, "inline": True}]
                    )
                    break
        
        # 💰 Points (pattern très large)
        if "point" in clean_line.lower():
            print(f"💡 Ligne avec 'point': {clean_line.strip()}")
            
            # Tous les patterns possibles
            points_patterns = [
                r'\+(\d+)\s*points?',  # +10 points
                r'earned?\s+(\d+)',     # earned 10
                r'gained?\s+(\d+)',     # gained 10
                r'claim.*?(\d+)',       # claim 10
            ]
            
            for pattern in points_patterns:
                match = re.search(pattern, clean_line, re.IGNORECASE)
                if match:
                    points = int(match.group(1))
                    
                    # Trouver le streamer
                    streamer = "Unknown"
                    streamer_match = re.search(r'(?:for|from|on|watching)\s+(\w+)', clean_line, re.IGNORECASE)
                    if streamer_match:
                        streamer = streamer_match.group(1)
                    
                    # Raison
                    reason = "Watch"
                    if "bonus" in clean_line.lower():
                        reason = "Bonus"
                    elif "raid" in clean_line.lower():
                        reason = "Raid"
                    
                    self.points_tracker[streamer] += points
                    
                    print(f"💰 DÉTECTÉ: +{points} points pour {streamer} ({reason})")
                    self.send_discord(
                        "💰 Points Gagnés",
                        f"**+{points}** points sur **{streamer}**",
                        0xFFD700,
                        [
                            {"name": "📝 Raison", "value": reason, "inline": True},
                            {"name": "💎 Total", "value": f"{self.points_tracker[streamer]} pts", "inline": True}
                        ]
                    )
                    break