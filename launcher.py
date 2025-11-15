#!/usr/bin/env python3
"""
Launcher pour Railway/Fly.io - Lance le Bot Discord et le Miner ensemble
"""

import subprocess
import sys
import time
import os
from threading import Thread

def run_discord_bot():
    """Lance le bot Discord"""
    print("🤖 Démarrage du Bot Discord...", flush=True)
    print("📍 Vérification du token...", flush=True)
    
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ DISCORD_BOT_TOKEN manquant !", flush=True)
        print("⚠️ Le bot Discord ne démarrera pas, mais le miner continuera", flush=True)
        return
    
    print(f"✅ Token présent (longueur: {len(token)})", flush=True)
    
    try:
        import sys
        import subprocess
        
        # Lancer avec sortie en temps réel
        process = subprocess.Popen(
            [sys.executable, "-u", "discord_bot.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Afficher les logs en temps réel
        try:
            for line in process.stdout:
                if line:
                    print(f"[BOT] {line.rstrip()}", flush=True)
        except Exception as e:
            print(f"[BOT] Erreur lecture stdout: {e}", flush=True)
        
        process.wait()
        if process.returncode != 0:
            print(f"[BOT] Processus terminé avec code {process.returncode}", flush=True)
        
    except KeyboardInterrupt:
        print("🛑 Bot Discord arrêté", flush=True)
    except Exception as e:
        print(f"❌ Erreur Bot Discord: {e}", flush=True)
        import traceback
        traceback.print_exc(file=sys.stdout)

def run_miner():
    """Lance le miner Twitch"""
    print("⛏️  Démarrage du Miner...", flush=True)
    time.sleep(5)  # Attendre que le bot Discord soit connecté
    
    try:
        # Lancer avec sortie en temps réel
        process = subprocess.Popen(
            [sys.executable, "-u", "run.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Afficher les logs en temps réel
        try:
            for line in process.stdout:
                if line:
                    print(f"[MINER] {line.rstrip()}", flush=True)
        except Exception as e:
            print(f"[MINER] Erreur lecture stdout: {e}", flush=True)
        
        process.wait()
        if process.returncode != 0:
            print(f"[MINER] Processus terminé avec code {process.returncode}", flush=True)
        
    except KeyboardInterrupt:
        print("🛑 Miner arrêté", flush=True)
    except Exception as e:
        print(f"❌ Erreur Miner: {e}", flush=True)
        import traceback
        traceback.print_exc(file=sys.stdout)

def main():
    # Forcer unbuffered pour Railway/Fly.io
    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except (AttributeError, OSError):
        # Fallback pour Python < 3.7 ou environnements sans reconfigure
        try:
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, line_buffering=True)
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, line_buffering=True)
        except Exception:
            pass  # Si ça échoue, on continue quand même
    
    print("=" * 50, flush=True)
    print("🚀 LAUNCHER - Twitch Miner + Bot Discord", flush=True)
    print(f"🐍 Python: {sys.version}", flush=True)
    print(f"📁 Working directory: {os.getcwd()}", flush=True)
    print("=" * 50, flush=True)
    
    # Vérifier les variables d'environnement
    required_vars = {
        "TWITCH_USERNAME": "Username Twitch",
        "TWITCH_AUTH_TOKEN": "Token d'authentification Twitch"
    }
    
    optional_vars = {
        "DISCORD_BOT_TOKEN": "Token du bot Discord",
        "DISCORD_CHANNEL_ID": "ID du canal Discord"
    }
    
    missing = []
    for var, desc in required_vars.items():
        if not os.getenv(var):
            missing.append(f"  ❌ {var} ({desc})")
    
    missing_optional = []
    for var, desc in optional_vars.items():
        if not os.getenv(var):
            missing_optional.append(f"  ⚠️  {var} ({desc}) - Optionnel")
    
    if missing:
        print("\n❌ Variables d'environnement OBLIGATOIRES manquantes:", flush=True)
        for m in missing:
            print(m, flush=True)
        platform = "Fly.io" if os.getenv("FLY_APP_NAME") else "Railway"
        print(f"\nConfigurez-les dans {platform} Settings → Variables/Secrets", flush=True)
        sys.exit(1)
    
    if missing_optional:
        print("\n⚠️  Variables d'environnement optionnelles manquantes:", flush=True)
        for m in missing_optional:
            print(m, flush=True)
        print("⚠️  Le bot Discord ne démarrera pas, mais le miner continuera", flush=True)
    
    print("\n✅ Variables obligatoires configurées", flush=True)
    print(f"✅ Twitch: {os.getenv('TWITCH_USERNAME')}", flush=True)
    
    # Lancer le bot Discord seulement si le token est présent
    discord_token = os.getenv("DISCORD_BOT_TOKEN")
    if discord_token:
        print(f"✅ Bot Discord: Canal {os.getenv('DISCORD_CHANNEL_ID', 'N/A')}", flush=True)
        print(f"✅ Mode Bot Discord: {os.getenv('USE_DISCORD_BOT', 'true')}", flush=True)
    else:
        print("⚠️  Bot Discord désactivé (token manquant)", flush=True)
    print(flush=True)
    
    # Lancer les processus
    threads = []
    
    # Bot Discord (optionnel)
    if discord_token:
        discord_thread = Thread(target=run_discord_bot, daemon=False, name="Discord-Bot")
        threads.append(discord_thread)
        discord_thread.start()
    
    # Miner (toujours lancé)
    miner_thread = Thread(target=run_miner, daemon=False, name="Twitch-Miner")
    threads.append(miner_thread)
    miner_thread.start()
    
    if discord_token:
        print("🔄 Les deux bots sont lancés en parallèle", flush=True)
    else:
        print("🔄 Le miner est lancé (bot Discord désactivé)", flush=True)
    print("📊 Surveillez les logs ci-dessous...", flush=True)
    print("=" * 50, flush=True)
    print(flush=True)
    
    # Attendre que les threads se terminent
    # Utiliser un timeout pour éviter de bloquer indéfiniment
    try:
        while any(t.is_alive() for t in threads):
            for t in threads:
                t.join(timeout=1)
    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé...", flush=True)
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ ERREUR FATALE dans launcher.py: {e}", flush=True)
        import traceback
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)

