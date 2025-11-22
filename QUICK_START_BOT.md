# 🚀 Quick Start - Bot Discord

## Installation rapide

```bash
# 1. Installer discord.py
pip install discord.py

# 2. Configurer les variables
export DISCORD_BOT_TOKEN="votre_token"
export DISCORD_CHANNEL_ID="123456789"
export USE_DISCORD_BOT="true"

# 3. Lancer le bot Discord (terminal 1)
python discord_bot.py

# 4. Lancer le miner (terminal 2)
python run.py
```

## Obtenir le token

1. https://discord.com/developers/applications
2. New Application → Bot → Reset Token → Copy
3. OAuth2 → URL Generator → bot → Send Messages + Embed Links
4. Inviter le bot sur votre serveur

## Obtenir l'ID du canal

1. Discord → Paramètres → Avancés → Mode développeur ✅
2. Clic droit sur un canal → Copier l'identifiant

## Résultat

Vous aurez des **fiches qui se mettent à jour automatiquement** :

```
🟢 JLTOMY
━━━━━━━━━
💎 382 700 points
💰 +450 cette session
🎲 2/3 paris gagnés
```

## Commandes

- `!refresh` - Mettre à jour maintenant
- `!status` - Statut du bot
- `!reset` - Réinitialiser les fiches
- `!help` - Aide

---

**Guide complet:** Voir `GUIDE_BOT_DISCORD.md`

