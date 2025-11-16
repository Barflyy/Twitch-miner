# 🚀 Fonctionnalités Avancées - Guide d'utilisation

Ce guide explique comment utiliser les 3 nouveaux composants avancés du bot.

## 📋 Table des matières

1. [PredictionScanner](#prediction-scanner)
2. [LiveDashboard](#live-dashboard)
3. [SmartNotifier](#smart-notifier)

---

## 🎯 Prediction Scanner

### Description

Le `PredictionScanner` scanne tous les streams actifs pour détecter les prédictions en utilisant l'API GraphQL de Twitch. C'est un complément au système WebSocket existant.

### Utilisation

```python
from TwitchChannelPointsMiner.classes.PredictionScanner import PredictionScanner

# Dans votre code principal, après avoir initialisé le bot
scanner = PredictionScanner(
    twitch_instance=twitch_miner.twitch,
    streamers_list=twitch_miner.streamers,
    events_predictions_dict=twitch_miner.events_predictions
)

# Démarrer le scan continu (scan toutes les 30 secondes)
scanner.start_continuous_scan(interval=30)

# Ou scanner manuellement
predictions = scanner.scan_all_active_streams()
for pred in predictions:
    print(f"Nouvelle prédiction: {pred['streamer']} - {pred['prediction']['title']}")
```

### Configuration

- **Intervalle de scan** : Par défaut 30 secondes, modifiable dans `start_continuous_scan(interval=...)`
- **Intégration** : Utilise automatiquement la stratégie `AdaptiveBetStrategy` pour analyser les prédictions

### Avantages

- ✅ Détection proactive des prédictions
- ✅ Complément au système WebSocket (double sécurité)
- ✅ Analyse automatique avec stratégie adaptive
- ✅ Logging détaillé des décisions

---

## 📊 Live Dashboard

### Description

Dashboard web en temps réel pour monitorer le bot, visualiser les stats, et voir les performances par streamer.

### Installation

Les dépendances sont déjà dans `requirements.txt` :
- `flask>=2.0.2`
- `flask-socketio>=5.1.1`

### Utilisation

```python
from TwitchChannelPointsMiner.classes.LiveDashboard import LiveDashboard

# Créer le dashboard
dashboard = LiveDashboard(
    bot_instance=twitch_miner,  # Instance de TwitchChannelPointsMiner
    port=5000,                   # Port du serveur web
    host='127.0.0.1'             # Host (127.0.0.1 = local seulement)
)

# Lancer en arrière-plan (recommandé)
dashboard.run_async()

# Ou lancer en mode blocage
# dashboard.run()
```

### Accès au Dashboard

Une fois lancé, ouvrez votre navigateur :
```
http://127.0.0.1:5000
```

### Fonctionnalités

- **Stats globales** : Points totaux, streams actifs, profit du jour, win rate
- **Top Streamers** : Liste des streamers triés par rentabilité
- **Recent Bets** : Derniers bets placés avec résultats
- **WebSocket** : Mise à jour en temps réel (pas besoin de rafraîchir)

### API Endpoints

Le dashboard expose plusieurs endpoints JSON :

- `GET /api/stats` - Stats globales
- `GET /api/streamers` - Liste des streamers avec performances
- `GET /api/recent_bets` - Derniers bets
- `GET /api/predictions` - Prédictions actives

### Configuration

```python
# Changer le port
dashboard = LiveDashboard(bot_instance=bot, port=8080)

# Accès depuis l'extérieur (attention sécurité)
dashboard = LiveDashboard(bot_instance=bot, host='0.0.0.0', port=5000)
```

### Sécurité

⚠️ **Important** : Par défaut, le dashboard est accessible uniquement en local (`127.0.0.1`). Si vous exposez sur `0.0.0.0`, assurez-vous d'avoir un firewall configuré.

---

## 🔔 Smart Notifier

### Description

Système de notifications Discord intelligentes qui envoie des alertes seulement pour les événements importants, avec système de cooldown pour éviter le spam.

### Configuration Discord Webhook

1. Allez dans votre serveur Discord
2. Paramètres du serveur → Intégrations → Webhooks
3. Créer un nouveau webhook
4. Copier l'URL du webhook

### Utilisation

```python
from TwitchChannelPointsMiner.classes.SmartNotifier import SmartNotifier

# Créer le notifier
notifier = SmartNotifier(
    discord_webhook="https://discord.com/api/webhooks/..."
)

# Notifier une prédiction à forte valeur
notifier.notify_high_value_prediction(
    prediction_data={
        'streamer_id': '123456',
        'streamer_name': 'streamer_name',
        'title': 'Will I win this game?'
    },
    decision={
        'confidence': 0.85,
        'amount': 10000,
        'reason': 'Sharp signal detected'
    }
)

# Notifier un gros gain
notifier.notify_big_win(
    amount=15000,
    streamer='streamer_name',
    prediction_title='Will I win?'
)

# Envoyer un résumé quotidien
notifier.send_daily_summary({
    'watch_time': 36000,  # 10 heures en secondes
    'points_earned': 50000,
    'predictions_won': 8,
    'predictions_total': 12,
    'win_rate': 66.7,
    'roi': 15.5,
    'best_streamer': 'streamer_name'
})
```

### Intégration dans le bot

Pour intégrer automatiquement dans le système de betting :

```python
# Dans WebSocketsPool.py ou votre code de betting
from TwitchChannelPointsMiner.classes.SmartNotifier import SmartNotifier

# Initialiser une fois
notifier = SmartNotifier(discord_webhook=os.getenv('DISCORD_WEBHOOK'))

# Quand une prédiction est détectée
if decision and decision.get('confidence', 0) >= 0.75:
    notifier.notify_high_value_prediction(prediction_data, decision)

# Quand une prédiction est résolue
if event.result['type'] == 'WIN' and points['won'] >= 10000:
    notifier.notify_big_win(
        points['won'],
        event.streamer.username,
        event.title
    )
```

### Types de notifications

#### 1. High Value Prediction
- **Critères** : Confiance ≥75% ET Montant ≥5000 points
- **Cooldown** : 5 minutes par streamer

#### 2. Big Win
- **Critères** : Gain ≥10000 points
- **Cooldown** : Aucun (toujours notifié)

#### 3. Big Loss
- **Critères** : Perte ≥10000 points
- **Cooldown** : 5 minutes par streamer

#### 4. Daily Summary
- **Quand** : À envoyer manuellement (ex: via cron)
- **Contenu** : Stats complètes de la journée

#### 5. Streamer Online
- **Quand** : Optionnel, pour streamers importants
- **Cooldown** : 5 minutes par streamer

### Configuration

```python
# Modifier le cooldown (par défaut 5 minutes)
notifier.set_cooldown(seconds=600)  # 10 minutes

# Effacer le cooldown pour une clé spécifique
notifier.clear_cooldown('prediction_streamer123')

# Effacer tous les cooldowns
notifier.clear_cooldown()
```

### Variables d'environnement

Recommandé d'utiliser une variable d'environnement :

```bash
# .env ou export
export DISCORD_WEBHOOK="https://discord.com/api/webhooks/..."
```

```python
import os
notifier = SmartNotifier(discord_webhook=os.getenv('DISCORD_WEBHOOK'))
```

---

## 🔧 Intégration complète

### Exemple d'intégration dans `run.py` ou votre script principal

```python
from TwitchChannelPointsMiner.classes.PredictionScanner import PredictionScanner
from TwitchChannelPointsMiner.classes.LiveDashboard import LiveDashboard
from TwitchChannelPointsMiner.classes.SmartNotifier import SmartNotifier
import os

# ... initialisation du bot ...

# 1. Dashboard (optionnel)
if os.getenv('ENABLE_DASHBOARD', 'false').lower() == 'true':
    dashboard = LiveDashboard(
        bot_instance=twitch_miner,
        port=int(os.getenv('DASHBOARD_PORT', '5000')),
        host=os.getenv('DASHBOARD_HOST', '127.0.0.1')
    )
    dashboard.run_async()
    print("✅ Dashboard démarré")

# 2. Notifier Discord (optionnel)
discord_webhook = os.getenv('DISCORD_WEBHOOK')
if discord_webhook:
    notifier = SmartNotifier(discord_webhook=discord_webhook)
    print("✅ Notifications Discord activées")
else:
    notifier = None

# 3. Scanner (optionnel, complément au WebSocket)
if os.getenv('ENABLE_SCANNER', 'false').lower() == 'true':
    scanner = PredictionScanner(
        twitch_instance=twitch_miner.twitch,
        streamers_list=twitch_miner.streamers,
        events_predictions_dict=twitch_miner.events_predictions
    )
    scanner.start_continuous_scan(interval=30)
    print("✅ PredictionScanner démarré")

# ... lancer le bot ...
twitch_miner.mine(...)
```

### Variables d'environnement recommandées

```bash
# .env
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
ENABLE_DASHBOARD=true
DASHBOARD_PORT=5000
DASHBOARD_HOST=127.0.0.1
ENABLE_SCANNER=false  # Optionnel, WebSocket suffit généralement
```

---

## 📝 Notes importantes

### Performance

- **PredictionScanner** : Utilise l'API GraphQL, peut être lourd avec beaucoup de streamers. Recommandé seulement si nécessaire.
- **LiveDashboard** : Très léger, peut tourner en permanence.
- **SmartNotifier** : Aucun impact sur les performances, notifications asynchrones.

### Compatibilité

- Tous les composants sont **optionnels** et fonctionnent indépendamment
- Compatibles avec toutes les stratégies de betting
- Fonctionnent avec ou sans le système de profiling

### Dépannage

#### Dashboard ne démarre pas
```bash
# Vérifier que Flask est installé
pip install flask flask-socketio

# Vérifier le port
netstat -an | grep 5000
```

#### Notifications Discord ne fonctionnent pas
- Vérifier l'URL du webhook
- Vérifier que le webhook n'est pas désactivé dans Discord
- Vérifier les logs (niveau DEBUG)

#### Scanner trop lent
- Augmenter l'intervalle : `scanner.start_continuous_scan(interval=60)`
- Désactiver si le WebSocket suffit

---

## 🎓 Exemples avancés

### Dashboard avec authentification (à implémenter)

```python
from flask import request, abort

@dashboard.app.before_request
def check_auth():
    if request.path.startswith('/api'):
        token = request.headers.get('Authorization')
        if token != f"Bearer {os.getenv('DASHBOARD_TOKEN')}":
            abort(401)
```

### Notifier avec filtres personnalisés

```python
class CustomNotifier(SmartNotifier):
    def notify_high_value_prediction(self, prediction_data, decision):
        # Filtrer certains streamers
        if prediction_data['streamer_name'] in ['streamer1', 'streamer2']:
            return super().notify_high_value_prediction(prediction_data, decision)
        return False
```

### Scanner avec callback personnalisé

```python
def custom_prediction_handler(pred_data, decision):
    if decision and decision['amount'] > 20000:
        # Action personnalisée
        send_sms_alert(f"Big bet on {pred_data['streamer']}")

scanner = PredictionScanner(...)
# Modifier la méthode analyze_and_decide pour appeler le callback
```

---

**Créé le** : 2025-11-15  
**Version** : 1.0.0

