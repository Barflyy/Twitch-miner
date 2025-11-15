# 🎯 Système de Stratégie Adaptive - Guide d'utilisation

## 📋 Vue d'ensemble

Le système de stratégie adaptive apprend automatiquement les patterns de prédiction de chaque streamer et adapte la stratégie de betting en conséquence.

## 🚀 Fonctionnalités

### 1. **StreamerPredictionProfiler**
- Base de données SQLite qui enregistre toutes les prédictions
- Analyse les patterns par type de prédiction (performance, objective, event, troll)
- Calcule la précision de la foule pour chaque streamer
- Génère des recommandations de stratégie

### 2. **AdaptiveBetStrategy**
- S'adapte au profil de chaque streamer
- Trois stratégies selon le profil :
  - **follow_crowd** : Suit la majorité (quand la foule a raison >70%)
  - **contrarian** : Parie contre la foule (quand la foule se trompe <45%)
  - **sharp_only** : N'utilise que les sharp signals (50/50)

### 3. **Intégration automatique**
- Logging automatique de toutes les prédictions
- Mise à jour des stats en temps réel
- Pas de configuration nécessaire

## 📖 Comment utiliser

### Activation de la stratégie ADAPTIVE

Dans votre fichier de configuration (ex: `run.py` ou `settings.json`), changez la stratégie :

```python
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy

# Pour un streamer spécifique
streamer_settings.bet.strategy = Strategy.ADAPTIVE

# Ou globalement pour tous les streamers
Settings.streamer_settings.bet.strategy = Strategy.ADAPTIVE
```

### Base de données

La base de données `streamer_profiles.db` est créée automatiquement dans le répertoire du script.

**Structure :**
- `prediction_history` : Historique de toutes les prédictions
- `streamer_stats` : Statistiques agrégées par streamer

### Consultation des profils

```python
from TwitchChannelPointsMiner.classes.entities.StreamerPredictionProfiler import StreamerPredictionProfiler

profiler = StreamerPredictionProfiler()

# Récupérer le profil d'un streamer
profile = profiler.get_streamer_profile("streamer_id")

if profile:
    print(f"Total prédictions: {profile['stats']['total_predictions']}")
    print(f"Crowd accuracy: {profile['stats']['crowd_accuracy']:.1f}%")
    print(f"Recommandations: {profile['recommendations']}")
    
    # Patterns par type
    for pred_type, data in profile['patterns'].items():
        print(f"{pred_type}: {data['crowd_accuracy']:.1f}% accuracy")

profiler.close()
```

## 📊 Types de prédictions détectés

Le système classe automatiquement les prédictions :

- **performance** : "Gagner", "Win", "Lose", "Victoire", "Perdre"
- **objective** : Prédictions avec chiffres ("5 kills", "10 buts")
- **event** : "Boss", "Round", "Niveau", "Phase"
- **troll** : "Rage", "Tilt", "Mort", "Fail"
- **other** : Tout le reste

## 🎯 Recommandations générées

Le système génère automatiquement :

1. **Stratégie optimale** : `follow_crowd`, `contrarian`, ou `sharp_only`
2. **Types à éviter** : Liste des types de prédictions non rentables
3. **Modificateur de confiance** : Ajustement selon la fiabilité du profil
4. **Raisonnement** : Explications détaillées

## 📈 Exemple de profil

```python
{
    'stats': {
        'total_predictions': 45,
        'crowd_accuracy': 68.5,
        'total_bets_placed': 30,
        'total_bets_won': 18,
        'total_points_won': 125000,
        'total_points_lost': 90000
    },
    'patterns': {
        'performance': {
            'total': 20,
            'crowd_accuracy': 75.0,
            'avg_gap': 15.2
        },
        'objective': {
            'total': 15,
            'crowd_accuracy': 45.0,
            'avg_gap': 8.5
        }
    },
    'recommendations': {
        'optimal_strategy': 'follow_crowd',
        'skip_types': ['objective'],
        'confidence_modifier': 1.2,
        'reasoning': [
            '✅ performance: La foule a raison 75% du temps → SUIVRE le consensus',
            '⚠️ objective: La foule se trompe 55% du temps → CONTRE-courant',
            '📊 45 prédictions → Profil fiable'
        ]
    }
}
```

## 🔧 Configuration avancée

### Modifier les seuils

Dans `StreamerPredictionProfiler._generate_recommendations()` :

```python
# Seuils pour consensus
STRONG_CONSENSUS_THRESHOLD = 75  # % minimum
WEAK_CONSENSUS_THRESHOLD = 60

# Seuils pour stratégie
FOLLOW_CROWD_THRESHOLD = 70  # Si crowd accuracy > 70%
CONTRARIAN_THRESHOLD = 45     # Si crowd accuracy < 45%
```

### Base de données personnalisée

```python
profiler = StreamerPredictionProfiler(db_path="custom/path/profiles.db")
```

## 📝 Logs

Le système log automatiquement :
- Création de prédictions
- Résultats des prédictions
- Mise à jour des stats

Les erreurs sont loggées en `DEBUG` pour ne pas polluer les logs.

## 🎓 Apprentissage

Le système s'améliore avec le temps :
- **Semaine 1** : Mode apprentissage (stratégie conservative)
- **Semaine 2-3** : Profils fiables, stratégies adaptées
- **Mois 1+** : Profils très fiables, stratégies optimisées

## ⚠️ Notes importantes

1. **Première utilisation** : Le système commence en mode "apprentissage" avec stratégie conservative
2. **Minimum de données** : Besoin d'au moins 10 prédictions pour un profil fiable
3. **Performance** : La base de données SQLite est légère et rapide
4. **Compatibilité** : Fonctionne avec toutes les autres stratégies (fallback automatique)

## 🔄 Migration depuis CROWD_WISDOM

Si vous utilisez déjà `CROWD_WISDOM`, vous pouvez passer à `ADAPTIVE` :

```python
# Avant
bet.strategy = Strategy.CROWD_WISDOM

# Après
bet.strategy = Strategy.ADAPTIVE
```

L'ADAPTIVE utilise CROWD_WISDOM comme stratégie de base et l'améliore avec le profiling.

## 🐛 Dépannage

### Base de données corrompue

```python
import os
os.remove("streamer_profiles.db")  # Le système la recréera
```

### Pas de données

Vérifiez que les prédictions sont bien loggées :
- Le bot doit être actif pendant les prédictions
- Les prédictions doivent être résolues (pas seulement créées)

### Performance lente

La base de données est optimisée avec des index. Si problème :
```python
# Vérifier la taille
import os
size = os.path.getsize("streamer_profiles.db")
print(f"DB size: {size / 1024 / 1024:.2f} MB")
```

## 📚 Prochaines étapes

1. **Dashboard web** : Visualiser les stats en temps réel
2. **Notifications Discord** : Alertes pour high-value bets
3. **Scanner multi-stream** : Détecter les prédictions sur tous les streams actifs

---

**Créé le** : 2025-11-15  
**Version** : 1.0.0

