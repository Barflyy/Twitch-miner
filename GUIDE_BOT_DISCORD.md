# 🤖 Guide du Bot Discord

## Vue d'ensemble

Le bot Discord permet d'avoir des **fiches éditables** pour chaque streamer qui se mettent à jour automatiquement toutes les 30 secondes.

Au lieu de recevoir plein de messages séparés, vous avez **1 message par streamer** qui affiche :
- 🟢 Statut (en ligne / hors ligne)
- 💎 Solde total de points
- 💰 Gains de la session
- 🎲 Statistiques des paris
- ⏱️ Durée en ligne

---

## 📋 Étape 1 : Créer le Bot Discord

### 1.1 Aller sur le portail Discord

https://discord.com/developers/applications

### 1.2 Créer une nouvelle application

1. Cliquez sur **"New Application"**
2. Donnez un nom : `Twitch Miner Bot`
3. Cliquez sur **"Create"**

### 1.3 Créer le bot

1. Dans le menu de gauche, cliquez sur **"Bot"**
2. Cliquez sur **"Add Bot"** puis **"Yes, do it!"**
3. Sous **TOKEN**, cliquez sur **"Reset Token"** puis **"Copy"**
4. **Sauvegardez ce token** (vous en aurez besoin)

### 1.4 Activer les intents

Dans la section **"Privileged Gateway Intents"** :
- ✅ Activez **MESSAGE CONTENT INTENT**
- ✅ Activez **SERVER MEMBERS INTENT** (optionnel)

Cliquez sur **"Save Changes"**

### 1.5 Inviter le bot sur votre serveur

1. Dans le menu de gauche, cliquez sur **"OAuth2"** → **"URL Generator"**
2. Dans **SCOPES**, cochez :
   - ✅ `bot`
3. Dans **BOT PERMISSIONS**, cochez :
   - ✅ `Send Messages`
   - ✅ `Embed Links`
   - ✅ `Read Message History`
   - ✅ `Use Slash Commands` (optionnel)
4. Copiez l'URL générée en bas
5. Ouvrez l'URL dans votre navigateur
6. Sélectionnez votre serveur Discord
7. Cliquez sur **"Autoriser"**

---

## 🔧 Étape 2 : Configuration

### 2.1 Obtenir l'ID du canal Discord

Dans Discord :
1. Activez le **Mode Développeur** : Paramètres → Avancés → Mode développeur
2. Faites clic droit sur le canal où vous voulez les fiches
3. Cliquez sur **"Copier l'identifiant du salon"**

### 2.2 Variables d'environnement

Ajoutez ces variables :

```bash
# Token du bot Discord
export DISCORD_BOT_TOKEN="votre_token_ici"

# ID du canal Discord (pour les fiches auto)
export DISCORD_CHANNEL_ID="123456789012345678"

# Activer le mode bot (true/false)
export USE_DISCORD_BOT="true"

# Webhook Discord (optionnel, pour logs supplémentaires)
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

**Note:** Vous pouvez garder le webhook ET le bot. Le webhook enverra des logs séparés pendant que le bot gère les fiches.

---

## 🚀 Étape 3 : Installation et Démarrage

### 3.1 Installer les dépendances

```bash
pip install discord.py
```

### 3.2 Démarrer le bot Discord

**Dans un terminal séparé** :

```bash
python discord_bot.py
```

Vous devriez voir :
```
✅ Bot connecté: Twitch Miner Bot
📋 ID: 123456789...
🔄 Mise à jour automatique activée
```

### 3.3 Démarrer le miner

**Dans un autre terminal** :

```bash
python run.py
```

---

## 🎮 Utilisation

### Commandes disponibles

Dans Discord, tapez :

#### `!refresh`
Force la mise à jour des fiches immédiatement

#### `!reset`
Réinitialise les fiches (supprime les anciens messages et en crée de nouveaux)

#### `!status`
Affiche le statut du bot (nombre de streamers, fiches actives, etc.)

#### `!help`
Affiche la liste des commandes

---

## 📊 Exemple de Fiche

```
🟢 JLTOMY

Statut: En ligne

💎 Solde Total
382 700 points

💰 Gains Session        🎲 Paris
+450 points             Placés: 3
└ Watch: +300           ✅ Gagnés: 2
└ Bonus: +150           ❌ Perdus: 1
                        📊 Taux: 67%

⏱️ Durée
2h 15m

Twitch Channel Points Miner • Mise à jour auto
```

Cette fiche se met à jour **automatiquement toutes les 30 secondes** !

---

## 🔄 Flux de données

```
Twitch Miner
    ↓
bot_data.json (fichier partagé)
    ↓
Bot Discord
    ↓
Fiches éditables sur Discord
```

Le miner écrit les événements dans `bot_data.json`.
Le bot Discord lit ce fichier et met à jour les fiches.

---

## ⚙️ Configuration avancée

### Changer la fréquence de mise à jour

Dans `discord_bot.py`, ligne 88 :

```python
@tasks.loop(seconds=30)  # ← Modifier ici (30 secondes par défaut)
async def update_cards():
```

### Désactiver les logs webhook

Si vous voulez SEULEMENT les fiches (pas de logs) :

```bash
export USE_DISCORD_BOT="true"
unset DISCORD_WEBHOOK_URL  # Désactive le webhook
```

### Mode hybride (recommandé)

Gardez les deux pour avoir :
- ✅ Fiches éditables (bot)
- ✅ Logs détaillés dans un autre canal (webhook)

---

## 🐛 Dépannage

### Le bot ne se connecte pas

- Vérifiez que `DISCORD_BOT_TOKEN` est correct
- Vérifiez que le bot a bien été invité sur votre serveur
- Vérifiez que les intents sont activés

### Les fiches ne s'affichent pas

- Vérifiez que `DISCORD_CHANNEL_ID` est correct
- Vérifiez que le bot a les permissions d'écrire dans le canal
- Tapez `!refresh` pour forcer la création des fiches

### Les fiches ne se mettent pas à jour

- Vérifiez que `USE_DISCORD_BOT="true"` dans le miner
- Vérifiez que le fichier `bot_data.json` est créé
- Vérifiez les logs du bot Discord

### Erreur "Message too old to edit"

C'est normal après un redémarrage. Tapez `!reset` puis `!refresh`.

---

## 📝 Fichiers importants

- `discord_bot.py` - Le bot Discord
- `bot_data.json` - Données partagées entre miner et bot
- `streamer_cards.json` - IDs des messages des fiches
- `TwitchChannelPointsMiner/classes/Discord.py` - Classe Discord modifiée

---

## 🎯 Avantages vs Webhook simple

| Feature | Webhook | Bot Discord |
|---------|---------|-------------|
| Notification événements | ✅ | ✅ |
| Embeds colorés | ✅ | ✅ |
| Fiches éditables | ❌ | ✅ |
| Vue d'ensemble claire | ❌ | ✅ |
| Commandes interactives | ❌ | ✅ |
| Pas de spam | ❌ | ✅ |
| Setup | Simple | Moyen |

---

## 🚀 Prochaines étapes

Fonctionnalités possibles à ajouter :
- `/add <streamer>` - Ajouter un streamer
- `/remove <streamer>` - Retirer un streamer
- `/restart` - Redémarrer le miner
- Graphiques de progression
- Alertes personnalisées

---

**Besoin d'aide ?** Vérifiez les logs des deux processus (bot et miner).

