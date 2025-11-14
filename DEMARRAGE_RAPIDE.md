# 🚀 Démarrage Rapide - Votre Bot Discord

## ✅ Configuration effectuée

Votre bot Discord est configuré avec :
- ✅ Token bot Discord
- ✅ ID du canal Discord
- ✅ Mode bot activé

---

## 📦 Installation

```bash
# Installer discord.py
pip install discord.py
```

---

## 🚀 Démarrage

### Option 1 : Scripts automatiques (recommandé)

**Terminal 1 - Bot Discord :**
```bash
chmod +x start_bot.sh
./start_bot.sh
```

**Terminal 2 - Miner :**
```bash
chmod +x start_miner.sh
./start_miner.sh
```

### Option 2 : Commandes manuelles

**Terminal 1 - Bot Discord :**
```bash
export DISCORD_BOT_TOKEN="VOTRE_TOKEN_ICI"
export DISCORD_CHANNEL_ID="VOTRE_CHANNEL_ID"
python3 discord_bot.py
```

**Terminal 2 - Miner :**
```bash
export DISCORD_BOT_TOKEN="VOTRE_TOKEN_ICI"
export DISCORD_CHANNEL_ID="VOTRE_CHANNEL_ID"
export USE_DISCORD_BOT="true"
python3 run.py
```

> **Note:** Vos vraies valeurs sont dans les scripts `start_bot.sh` et `start_miner.sh` (non commités sur GitHub pour sécurité)

---

## 🔍 Vérification

### Bot Discord démarré :
```
✅ Bot connecté: Twitch Miner Bot
📋 ID: 123456789...
🔄 Mise à jour automatique activée
```

### Miner démarré :
```
✅ Mode Bot Discord activé (fiches éditables)
🚀 Démarrage du mining...
```

### Dans Discord :
Vous devriez voir une fiche comme :
```
🟢 JLTOMY
━━━━━━━━━━━━
Statut: En ligne

💎 Solde Total
382 700 points

💰 Gains Session
+0 points

Twitch Channel Points Miner • Mise à jour auto
```

---

## 🎮 Commandes Discord

Dans le canal Discord, tapez :

- `!refresh` - Forcer la mise à jour
- `!status` - Statut du bot
- `!reset` - Réinitialiser les fiches
- `!help` - Aide

---

## 🐛 Dépannage

### Le bot ne se connecte pas
```bash
# Vérifier le token
echo $DISCORD_BOT_TOKEN

# Tester manuellement
python3 -c "import discord; print('discord.py OK')"
```

### Les fiches ne s'affichent pas
1. Vérifiez que les 2 processus tournent (bot + miner)
2. Dans Discord, tapez `!refresh`
3. Vérifiez que le bot a la permission d'écrire dans le canal

### Le fichier bot_data.json n'est pas créé
- Attendez qu'un événement se produise (streamer online, points gagnés)
- Vérifiez que `USE_DISCORD_BOT="true"` dans le miner

---

## 📊 Résultat attendu

Après quelques minutes, vous aurez :
- ✅ Une fiche par streamer
- ✅ Mise à jour automatique toutes les 30 secondes
- ✅ Stats en temps réel (solde, gains, paris)
- ✅ Plus de spam de notifications

---

## ⚙️ Configuration avancée

### Ajouter le webhook en plus (logs séparés)

Dans `start_miner.sh`, décommentez :
```bash
export DISCORD_WEBHOOK_URL="votre_webhook_url"
```

Vous aurez alors :
- **Bot** → Fiches éditables dans un canal
- **Webhook** → Logs détaillés dans un autre canal

### Changer la fréquence de mise à jour

Dans `discord_bot.py`, ligne 88 :
```python
@tasks.loop(seconds=30)  # ← Modifier ici
```

---

## 📝 Fichiers créés

- `bot_data.json` - Données partagées (auto-créé)
- `streamer_cards.json` - IDs des messages (auto-créé)
- `start_bot.sh` - Script de démarrage bot
- `start_miner.sh` - Script de démarrage miner

**⚠️ Ces fichiers sont dans .gitignore (ne seront pas sur GitHub)**

---

## ✨ C'est prêt !

Lancez les deux scripts et profitez de vos fiches Discord ! 🎉

**Besoin d'aide ?** Consultez `GUIDE_BOT_DISCORD.md`

