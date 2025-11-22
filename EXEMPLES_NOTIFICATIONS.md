# 📱 Exemples de Notifications Discord

Voici à quoi ressembleront vos notifications Discord avec la nouvelle configuration.

## 🟢 Streamer en ligne

```
🎉 Streamer(username=xqc, channel_id=71092938, channel_points=45.2K) is Online!
```

Ou en mode simplifié :
```
🎉 xqc (45.2K points) is Online!
```

## 🔴 Streamer hors ligne

```
😴 xqc (45.2K points) is Offline!
```

## 💰 Points gagnés (WATCH)

Quand vous gagnez des points en regardant :

```
🚀 +10 → Streamer(username=xqc, channel_id=71092938, channel_points=45.2K) - Reason: WATCH.
```

Ou en mode simplifié :
```
🚀 +10 → xqc (45.2K points) - Reason: WATCH.
```

## 💎 Points gagnés (WATCH_STREAK)

Quand vous réclamez votre bonus de streak :

```
🚀 +450 → xqc (45.6K points) - Reason: WATCH_STREAK.
```

## 🎁 Bonus réclamé

```
🚀 +50 → xqc (45.7K points) - Reason: CLAIM.
```

## 🎲 Paris (Prédictions)

### Pari placé (BET_START)
```
🎲 Placed a bet on xqc for 500 points on outcome: Blue wins
```

### Pari gagné (BET_WIN)
```
🎉 Won 1250 points on xqc! Total: 46.5K points
```

### Pari perdu (BET_LOSE)
```
😢 Lost 500 points on xqc. Better luck next time!
```

## 🎯 Drops et Raids

### Drop réclamé (DROP_CLAIM)
```
🎁 Claimed drop: Valorant Drop on xqc
```

### Raid rejoint (JOIN_RAID)
```
🎯 Joined raid from xqc to shroud for bonus points
```

## 💬 Mention dans le chat

```
📣 You were mentioned in xqc's chat!
```

---

## 🎨 Personnaliser l'affichage

Les messages incluent automatiquement :
- ✅ Des emojis pour chaque type d'événement
- ✅ Le nom du streamer
- ✅ Le nombre de points gagnés/perdus
- ✅ Votre solde actuel de points

### Mode "less" (messages simplifiés)

Pour avoir des messages plus courts, modifiez dans `run.py` :

```python
logger_settings=LoggerSettings(
    save=True,
    console_level=logging.INFO,
    file_level=logging.DEBUG,
    emoji=True,
    colored=True,
    less=True,  # ← Ajoutez cette ligne
    ...
)
```

Les messages deviendront alors :
```
🚀 +10 → xqc (45.2K points) - Reason: WATCH.
```
Au lieu de :
```
🚀 +10 → Streamer(username=xqc, channel_id=71092938, channel_points=45.2K) - Reason: WATCH.
```

---

## 📊 Fréquence des notifications

Selon votre configuration, vous recevrez :

- **Toutes les 5-15 minutes** : Points WATCH (10-50 points selon les multiplicateurs)
- **Toutes les heures** : Bonus WATCH_STREAK (si actif)
- **À chaque connexion** : STREAMER_ONLINE/OFFLINE
- **Pendant les streams** : BET_START, BET_WIN, BET_LOSE (si prédictions activées)
- **Occasionnellement** : DROP_CLAIM, JOIN_RAID, etc.

### ⚠️ Anti-spam

Si vous trouvez que c'est trop de notifications, vous pouvez :

1. **Désactiver les événements fréquents** comme `GAIN_FOR_WATCH`
2. **Garder seulement les événements importants** :

```python
events=[
    Events.STREAMER_ONLINE,
    Events.STREAMER_OFFLINE,
    Events.BET_WIN,        # Seulement les victoires
    Events.DROP_CLAIM,     # Seulement les drops
    Events.BONUS_CLAIM,    # Seulement les bonus
]
```

3. **Utiliser un canal Discord séparé** pour le bot afin de ne pas polluer vos autres canaux

---

## 🧪 Test des notifications

Pour tester que tout fonctionne, vous pouvez :

1. Démarrer le bot
2. Attendre qu'un de vos streamers passe en ligne → vous devriez recevoir une notification 🟢
3. Après quelques minutes, vous devriez recevoir des notifications de points gagnés 💰
4. Si un streamer lance une prédiction et que le bot parie, vous recevrez une notification 🎲

Si vous ne recevez rien après 10-15 minutes, consultez `NOTIFICATIONS_DISCORD.md` pour le dépannage.

