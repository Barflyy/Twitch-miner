# 🔧 Dépannage Fly.io - Machine en boucle de redémarrage

## 🚨 Problème : "This machine has exhausted its maximum restart attempts (10)"

Si votre machine Fly.io crash immédiatement et redémarre en boucle, suivez ces étapes :

---

## 1️⃣ Vérifier les logs

```bash
fly logs -a twitch-miner
```

Cherchez les erreurs dans les dernières lignes avant le crash.

---

## 2️⃣ Recréer la machine (Solution rapide)

Si la machine est dans un état corrompu, recréez-la :

```bash
# Supprimer la machine actuelle
fly machine destroy 2863674ae5e708 -a twitch-miner --force

# Redéployer (créera une nouvelle machine)
fly deploy -a twitch-miner
```

---

## 3️⃣ Vérifier les secrets/variables

Assurez-vous que tous les secrets sont configurés :

```bash
# Lister les secrets
fly secrets list -a twitch-miner

# Vérifier les secrets requis
# - TWITCH_USERNAME
# - TWITCH_AUTH_TOKEN
# - DISCORD_BOT_TOKEN (optionnel)
# - DISCORD_CHANNEL_ID (optionnel)
```

---

## 4️⃣ Tester localement d'abord

Avant de déployer, testez localement :

```bash
# Simuler l'environnement Fly.io
export FLY_APP_NAME=twitch-miner
export TWITCH_USERNAME=votre_username
export TWITCH_AUTH_TOKEN=votre_token

# Tester le script de démarrage
python -u start.py
```

---

## 5️⃣ Vérifier les fichiers

Le script `start.py` vérifie automatiquement :
- ✅ Existence de `launcher.py`
- ✅ Existence de `run.py`
- ✅ Existence de `discord_bot.py`
- ✅ Imports Python de base

Si un fichier manque, le script l'affichera dans les logs.

---

## 6️⃣ Problèmes courants

### ❌ "ModuleNotFoundError"
**Cause** : Dépendances non installées  
**Solution** : Vérifiez que `requirements.txt` est bien installé dans le build

### ❌ "FileNotFoundError"
**Cause** : Fichier manquant dans l'image  
**Solution** : Vérifiez que tous les fichiers sont bien copiés (pas de .dockerignore trop restrictif)

### ❌ "Permission denied"
**Cause** : Scripts non exécutables  
**Solution** : Les scripts doivent avoir `chmod +x` (déjà fait pour start.py)

### ❌ Crash silencieux
**Cause** : Exception non capturée  
**Solution** : Le script `start.py` capture maintenant toutes les exceptions

---

## 7️⃣ Commandes utiles

```bash
# Voir les logs en temps réel
fly logs -a twitch-miner

# Se connecter en SSH à la machine
fly ssh console -a twitch-miner

# Voir l'état de la machine
fly status -a twitch-miner

# Redémarrer l'app
fly apps restart twitch-miner

# Voir les machines
fly machine list -a twitch-miner
```

---

## 8️⃣ Diagnostic complet

Si le problème persiste, exécutez ce diagnostic :

```bash
# 1. Voir les logs
fly logs -a twitch-miner --limit 100

# 2. Vérifier les secrets
fly secrets list -a twitch-miner

# 3. Vérifier la configuration
fly config show -a twitch-miner

# 4. Tester en SSH
fly ssh console -a twitch-miner
# Puis dans le shell :
python -u start.py
```

---

## 9️⃣ Solution de dernier recours

Si rien ne fonctionne, recréez complètement l'app :

```bash
# ⚠️ ATTENTION : Cela supprime tout !
fly apps destroy twitch-miner

# Recréer l'app
fly apps create twitch-miner

# Configurer les secrets
fly secrets set TWITCH_USERNAME=votre_username -a twitch-miner
fly secrets set TWITCH_AUTH_TOKEN=votre_token -a twitch-miner
fly secrets set DISCORD_BOT_TOKEN=votre_token_discord -a twitch-miner
fly secrets set DISCORD_CHANNEL_ID=votre_channel_id -a twitch-miner

# Déployer
fly deploy -a twitch-miner
```

---

## 📝 Logs attendus au démarrage

Avec le nouveau script `start.py`, vous devriez voir :

```
==================================================
🚀 START.PY - Script de démarrage
🐍 Python: 3.10.x
📁 Working directory: /app
📋 Files in directory:
  ✅ launcher.py
  ✅ run.py
  ✅ discord_bot.py
  ✅ requirements.txt
==================================================
🔍 Vérification des imports...
  ✅ subprocess
  ✅ threading
  ✅ time
✅ Tous les imports de base OK
==================================================
🚀 Lancement de launcher.py...
==================================================
```

Si vous ne voyez pas ces logs, le problème est avant même le démarrage de Python.

---

## 🆘 Besoin d'aide ?

Partagez :
1. Les dernières lignes des logs : `fly logs -a twitch-miner --limit 50`
2. La liste des secrets : `fly secrets list -a twitch-miner`
3. L'erreur exacte si visible

