# 📢 Guide des Notifications Discord

## ✅ Ce qui a été modifié

Le bot a été mis à jour pour utiliser le **système de notifications Discord intégré** de TwitchChannelPointsMiner. Cela signifie que vous recevrez maintenant des notifications structurées pour tous les événements importants.

### Changements dans `run.py`

1. **Ajout de la configuration Discord officielle** via `LoggerSettings`
2. **Suppression du DiscordLogHandler personnalisé** (qui manquait des événements)
3. **Activation de tous les événements importants**

## 📋 Événements notifiés sur Discord

Votre bot vous enverra maintenant des notifications pour :

### 🟢 Connexions aux streams
- **STREAMER_ONLINE** : Quand un streamer passe en ligne
- **STREAMER_OFFLINE** : Quand un streamer se déconnecte

### 💰 Gains de points
- **GAIN_FOR_WATCH** : Points gagnés en regardant (watch)
- **GAIN_FOR_WATCH_STREAK** : Bonus de streak de visionnage
- **GAIN_FOR_RAID** : Points gagnés lors d'un raid
- **GAIN_FOR_CLAIM** : Points réclamés
- **BONUS_CLAIM** : Bonus réclamés
- **MOMENT_CLAIM** : Moments réclamés

### 🎲 Prédictions (Paris)
- **BET_START** : Nouvelle prédiction placée
- **BET_WIN** : Prédiction gagnée 🎉
- **BET_LOSE** : Prédiction perdue 😢
- **BET_REFUND** : Prédiction remboursée

### 🎁 Autres événements
- **DROP_CLAIM** : Drop réclamé
- **JOIN_RAID** : Participation à un raid
- **CHAT_MENTION** : Mention dans le chat

## 🎨 Format des notifications

Les notifications Discord seront envoyées sous forme de **messages texte simples** avec :
- Un username : "Twitch Channel Points Miner"
- Une icône avatar personnalisée
- Le message de l'événement

### Exemples de messages

```
🟢 [streamer_name] goes ONLINE!
💰 +10 → [streamer_name] - Reason: WATCH.
🎁 Claimed 50 points bonus from [streamer_name]!
🎉 You won 250 points from prediction on [streamer_name]!
```

## ⚙️ Personnaliser les notifications

### Modifier les événements reçus

Si vous voulez recevoir **seulement certains événements**, modifiez la liste dans `run.py` (lignes 136-152) :

```python
discord_config = Discord(
    webhook_api=WEBHOOK,
    events=[
        Events.STREAMER_ONLINE,    # Gardez seulement ceux que vous voulez
        Events.STREAMER_OFFLINE,
        Events.BET_WIN,            # Par exemple, seulement les paris gagnés
        Events.BET_LOSE,
        # Commentez ou supprimez les lignes pour les événements non désirés
    ]
)
```

### Désactiver complètement Discord

Pour désactiver les notifications Discord, supprimez simplement la variable d'environnement `DISCORD_WEBHOOK_URL`.

## 🔍 Vérification

Pour vérifier que tout fonctionne :

1. ✅ Votre `DISCORD_WEBHOOK_URL` doit être configuré
2. ✅ Au démarrage, vous devriez voir : `✅ Notifications Discord activées pour tous les événements`
3. ✅ Quand un streamer passe en ligne, vous recevrez une notification
4. ✅ Quand vous gagnez des points, vous recevrez une notification

## 🚨 Dépannage

### Je ne reçois aucune notification
- Vérifiez que `DISCORD_WEBHOOK_URL` est bien défini
- Vérifiez que l'URL du webhook est valide (testez-la avec curl)
- Regardez les logs du bot pour des erreurs

### Je reçois trop de notifications
- Réduisez la liste des événements dans la configuration (voir ci-dessus)
- Augmentez le niveau de log à `logging.WARNING` pour moins de verbosité

### Les notifications sont en doublon
- Le nouveau système remplace l'ancien `DiscordLogHandler`
- Assurez-vous de ne pas avoir d'autres scripts qui lisent les logs et envoient sur Discord

## 📝 Note technique

Le système fonctionne via le **logger** de TwitchChannelPointsMiner. Quand un événement se produit dans le code du miner, il est loggé avec un attribut `event`. Le `GlobalFormatter` dans `logger.py` détecte ces événements et envoie automatiquement les notifications Discord configurées.

C'est beaucoup plus fiable que parser les messages de log, car on utilise directement le système d'événements du bot ! 🎉

