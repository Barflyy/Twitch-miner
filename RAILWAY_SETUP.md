# 🚂 Configuration Railway avec Bot Discord

## 📋 Ce qui a changé

Avant, Railway lançait seulement `run.py`.

Maintenant, Railway lance `launcher.py` qui démarre **les 2 bots en même temps** :
- 🤖 Bot Discord (fiches éditables)
- ⛏️ Miner Twitch (mine les points)

---

## ⚙️ Configuration dans Railway

### 1. Aller dans votre projet Railway

https://railway.app → Votre projet Twitch Miner

### 2. Configurer les Variables d'Environnement

Cliquez sur **Settings** → **Variables**

#### Variables existantes (à garder) :
```
TWITCH_USERNAME = votre_username
TWITCH_AUTH_TOKEN = votre_token_twitch
```

#### Nouvelles variables à ajouter :

**Pour le Bot Discord :**
```
DISCORD_BOT_TOKEN = votre_token_discord_bot
DISCORD_CHANNEL_ID = votre_channel_id
USE_DISCORD_BOT = true
```

> **Vos vraies valeurs :** Elles sont dans vos scripts locaux `start_bot.sh` / `start_miner.sh`

**Optionnel (webhook pour logs séparés) :**
```
DISCORD_WEBHOOK_URL = https://discord.com/api/webhooks/...
```

---

## 🚀 Déploiement

### Option 1 : Push automatique (recommandé)

Si votre Railway est lié à GitHub :

```bash
git add .
git commit -m "Activer bot Discord sur Railway"
git push origin master
```

→ Railway redéploiera automatiquement

### Option 2 : Redéploiement manuel

Dans Railway :
1. Cliquez sur **Deployments**
2. Cliquez sur **Deploy** (ou attendez le déploiement auto)

---

## 📊 Vérifier que ça fonctionne

### 1. Voir les logs Railway

Dans Railway, cliquez sur **View Logs**

Vous devriez voir :
```
🚀 LAUNCHER - Twitch Miner + Bot Discord
✅ Toutes les variables sont configurées
✅ Bot Discord: Canal 1438596868526313612
✅ Twitch: votre_username
✅ Mode Bot Discord: true

🤖 Démarrage du Bot Discord...
⛏️  Démarrage du Miner...
🔄 Les deux bots sont lancés en parallèle

✅ Bot connecté: Twitch Miner Bot
🔄 Mise à jour automatique activée

🎮 Twitch Points Miner
✅ Mode Bot Discord activé (fiches éditables)
🚀 Démarrage du mining...
```

### 2. Vérifier dans Discord

Dans votre canal Discord :
- Tapez `!status` pour vérifier que le bot répond
- Attendez que JLTomy passe en ligne
- Une fiche devrait apparaître automatiquement

---

## 🔧 Architecture sur Railway

```
Railway Worker Process
        ↓
    launcher.py
        ↓
   ┌────┴────┐
   ↓         ↓
discord_bot  run.py
   ↓         ↓
   └────┬────┘
        ↓
  bot_data.json
        ↓
   Discord API
```

---

## 📝 Fichiers importants

| Fichier | Rôle |
|---------|------|
| `launcher.py` | Lance les 2 bots ensemble |
| `procfile` | Dit à Railway de lancer launcher.py |
| `discord_bot.py` | Bot Discord (fiches) |
| `run.py` | Miner Twitch |
| `bot_data.json` | Communication entre les 2 (auto-créé) |

---

## 🐛 Dépannage Railway

### Le bot ne démarre pas

**Vérifier les logs :**
```
Railway → Deployments → View Logs
```

**Erreurs communes :**

❌ `discord.py not found`
→ Vérifiez que `requirements.txt` contient `discord.py>=2.0.0`

❌ `DISCORD_BOT_TOKEN not found`
→ Ajoutez la variable dans Settings → Variables

❌ `Invalid token`
→ Regénérez le token sur Discord Developer Portal

### Le bot Discord se connecte mais pas de fiches

1. Vérifiez que `DISCORD_CHANNEL_ID` est correct
2. Vérifiez les permissions du bot (Send Messages, Embed Links)
3. Dans Discord, tapez `!refresh` pour forcer la création

### Le miner fonctionne mais pas le bot Discord

Vérifiez les logs Railway :
```
❌ Erreur Bot Discord: [le message d'erreur]
```

Puis corrigez selon l'erreur.

---

## 💡 Avantages Railway + Bot Discord

✅ **Tout hébergé** sur Railway (pas besoin de serveur local)
✅ **Always-on** (tourne 24/7)
✅ **Fiches Discord** propres et éditables
✅ **Un seul déploiement** pour les 2 bots
✅ **Variables sécurisées** (dans Railway, pas dans le code)

---

## 🔄 Pour tester localement avant Railway

Si vous voulez tester en local d'abord :

```bash
# Configurer les variables
export DISCORD_BOT_TOKEN="votre_token"
export DISCORD_CHANNEL_ID="votre_channel_id"
export TWITCH_USERNAME="votre_username"
export TWITCH_AUTH_TOKEN="votre_token"
export USE_DISCORD_BOT="true"

# Lancer le launcher
python launcher.py
```

Vous verrez les 2 bots démarrer dans le même terminal.

---

## 🎯 Récapitulatif

**Ce qu'il faut faire :**

1. ✅ Ajouter les 3 variables dans Railway (BOT_TOKEN, CHANNEL_ID, USE_DISCORD_BOT)
2. ✅ Push le code sur GitHub (ou attendre le redéploiement)
3. ✅ Vérifier les logs Railway
4. ✅ Dans Discord, tapez `!status` pour tester

**Ce qui se passe automatiquement :**

- Railway lance `launcher.py`
- Le launcher démarre les 2 bots
- Les bots communiquent via `bot_data.json`
- Les fiches Discord se mettent à jour toutes les 30s

---

C'est tout ! Railway gère tout automatiquement. 🚀

**Besoin d'aide ?** Regardez les logs Railway pour voir ce qui se passe.

