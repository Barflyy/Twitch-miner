#!/usr/bin/env python3
"""
Script pour limiter le nombre de streamers à miner
Réduit la charge sur les WebSockets et évite les erreurs de connexion
"""

import json
from pathlib import Path

# Configuration
MAX_STREAMERS = 100  # Limite recommandée pour éviter les problèmes de connexion
FOLLOWERS_FILE = Path("./followers_data/barflyy__followers.json")
BACKUP_FILE = Path("./followers_data/barflyy__followers_BACKUP.json")

def limit_streamers(max_count=MAX_STREAMERS):
    """Limite le nombre de streamers dans le fichier JSON"""
    
    if not FOLLOWERS_FILE.exists():
        print(f"❌ Fichier non trouvé: {FOLLOWERS_FILE}")
        return False
    
    # Charger le fichier
    with open(FOLLOWERS_FILE, 'r') as f:
        data = json.load(f)
    
    followers = data.get('followers', [])
    original_count = len(followers)
    
    print(f"📊 Nombre actuel de streamers: {original_count}")
    
    if original_count <= max_count:
        print(f"✅ Déjà sous la limite de {max_count} streamers")
        return True
    
    # Créer une sauvegarde
    print(f"💾 Création d'une sauvegarde: {BACKUP_FILE}")
    with open(BACKUP_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Limiter à max_count streamers
    data['followers'] = followers[:max_count]
    data['last_update'] = data.get('last_update', 'Unknown')
    
    # Sauvegarder
    with open(FOLLOWERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Streamers réduits de {original_count} à {max_count}")
    print(f"📋 Premiers streamers conservés: {', '.join(followers[:5])}...")
    print(f"🚫 Streamers retirés: {original_count - max_count}")
    print(f"\n💡 Pour restaurer la liste complète:")
    print(f"   cp {BACKUP_FILE} {FOLLOWERS_FILE}")
    
    return True

if __name__ == "__main__":
    import sys
    
    # Permettre de spécifier une limite personnalisée
    if len(sys.argv) > 1:
        try:
            MAX_STREAMERS = int(sys.argv[1])
        except ValueError:
            print(f"❌ Limite invalide: {sys.argv[1]}")
            sys.exit(1)
    
    print(f"🎯 Limitation à {MAX_STREAMERS} streamers maximum")
    print(f"📂 Fichier: {FOLLOWERS_FILE}")
    print()
    
    success = limit_streamers(MAX_STREAMERS)
    
    if success:
        print("\n✅ Opération terminée avec succès!")
        print("\n🚀 Redémarrez le bot pour appliquer les changements")
    else:
        print("\n❌ Échec de l'opération")
        sys.exit(1)
