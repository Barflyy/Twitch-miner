#!/usr/bin/env python3
"""
Script de démarrage simple pour Fly.io
Vérifie les imports et lance launcher.py
"""

import sys
import os

# Forcer unbuffered
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None
sys.stderr.reconfigure(line_buffering=True) if hasattr(sys.stderr, 'reconfigure') else None

print("=" * 50, flush=True)
print("🚀 START.PY - Script de démarrage", flush=True)
print(f"🐍 Python: {sys.version}", flush=True)
print(f"📁 Working directory: {os.getcwd()}", flush=True)
print(f"📋 Files in directory:", flush=True)

# Lister les fichiers importants
important_files = ['launcher.py', 'run.py', 'discord_bot.py', 'requirements.txt']
for f in important_files:
    exists = "✅" if os.path.exists(f) else "❌"
    print(f"  {exists} {f}", flush=True)

print("=" * 50, flush=True)

# Vérifier les imports de base
print("🔍 Vérification des imports...", flush=True)
try:
    import subprocess
    print("  ✅ subprocess", flush=True)
except ImportError as e:
    print(f"  ❌ subprocess: {e}", flush=True)
    sys.exit(1)

try:
    import threading
    print("  ✅ threading", flush=True)
except ImportError as e:
    print(f"  ❌ threading: {e}", flush=True)
    sys.exit(1)

try:
    import time
    print("  ✅ time", flush=True)
except ImportError as e:
    print(f"  ❌ time: {e}", flush=True)
    sys.exit(1)

print("✅ Tous les imports de base OK", flush=True)
print("=" * 50, flush=True)

# Lancer launcher.py
print("🚀 Lancement de launcher.py...", flush=True)
print("=" * 50, flush=True)

try:
    # Importer et exécuter launcher
    import launcher
    launcher.main()
except ImportError as e:
    print(f"❌ Erreur import launcher: {e}", flush=True)
    import traceback
    traceback.print_exc(file=sys.stdout)
    sys.exit(1)
except Exception as e:
    print(f"❌ Erreur dans launcher: {e}", flush=True)
    import traceback
    traceback.print_exc(file=sys.stdout)
    sys.exit(1)

