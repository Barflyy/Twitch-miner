# 🔧 Diagnostic WebSocket - SmartBetTiming

## 🎯 Problème Identifié

Tu n'as **jamais eu de problème** avec 465 streamers auparavant, mais maintenant tu as des erreurs massives de WebSocket.

### Cause Racine : **SmartBetTiming**

Le système **SmartBetTiming** que tu as ajouté récemment crée **un thread daemon par prédiction active** (ligne 193-199 de `SmartBetTiming.py`).

#### Scénario Problématique

1. **465 streamers** surveillés
2. Plusieurs streamers lancent des prédictions **simultanément**
3. **SmartBetTiming** crée un thread pour **chaque prédiction**
4. Chaque thread fait des requêtes **toutes les 3-10 secondes** (check_interval)
5. Avec 20-30 prédictions actives simultanément = **20-30 threads** qui bombardent les WebSockets
6. Les WebSockets ne peuvent pas gérer la charge → **Ping/Pong failures**

### Preuve

```python
# SmartBetTiming.py, ligne 193-199
monitor_thread = threading.Thread(
    target=self._monitoring_loop,
    args=(event_id,),
    daemon=True,
    name=f"SmartBetV2-{event_id[:8]}"
)
monitor_thread.start()
```

Chaque thread exécute une boucle qui :
- Vérifie les données toutes les 3-10 secondes
- Accède aux WebSocket data
- Peut créer des race conditions sur les connexions

## ✅ Solution Temporaire (Appliquée)

J'ai **désactivé SmartBetTiming** dans `WebSocketsPool.py` (ligne 46-62).

Le bot utilisera maintenant le **système classique de Timer** qui :
- Crée un seul Timer par prédiction
- N'accède aux données qu'**une seule fois** au moment du bet
- **Beaucoup moins de charge** sur les WebSockets

### Test

1. **Redémarre le bot**
2. **Surveille les logs** pour vérifier :
   - ✅ Message : `⚠️ SmartBetTiming DÉSACTIVÉ (diagnostic WebSocket)`
   - ✅ Moins d'erreurs WebSocket
   - ✅ Connexions stables

## 🛠️ Solutions Permanentes

### Option 1 : Optimiser SmartBetTiming (RECOMMANDÉ)

Au lieu de créer un thread par prédiction, utiliser **un seul thread global** qui gère toutes les prédictions :

```python
class SmartBetTiming:
    def __init__(self):
        self.active_predictions = {}
        self.lock = threading.Lock()
        
        # UN SEUL thread pour TOUTES les prédictions
        self.monitor_thread = threading.Thread(
            target=self._global_monitoring_loop,
            daemon=True
        )
        self.monitor_thread.start()
    
    def _global_monitoring_loop(self):
        """Boucle unique qui surveille TOUTES les prédictions"""
        while True:
            with self.lock:
                predictions_to_check = list(self.active_predictions.items())
            
            for event_id, pred_data in predictions_to_check:
                # Vérifie cette prédiction
                self._check_prediction(event_id, pred_data)
            
            time.sleep(2)  # Vérifier toutes les 2 secondes
```

**Avantages** :
- ✅ Un seul thread au lieu de 20-30
- ✅ Charge prévisible sur les WebSockets
- ✅ Garde toute la logique intelligente de SmartBetTiming

### Option 2 : Limiter le Nombre de Threads Actifs

Ajouter un pool de threads avec limite :

```python
from concurrent.futures import ThreadPoolExecutor

class SmartBetTiming:
    def __init__(self):
        # Max 5 threads simultanés
        self.executor = ThreadPoolExecutor(max_workers=5)
        
    def start_monitoring(self, event_prediction, bet_callback):
        # Utilise le pool au lieu de créer un nouveau thread
        self.executor.submit(
            self._monitoring_loop,
            event_prediction.event_id
        )
```

**Avantages** :
- ✅ Limite stricte du nombre de threads
- ✅ Gestion automatique de la queue
- ⚠️ Peut retarder certaines prédictions si pool saturé

### Option 3 : Désactiver Définitivement SmartBetTiming

Si tu préfères la simplicité, garde le système classique de Timer.

**Avantages** :
- ✅ Très stable
- ✅ Faible charge
- ❌ Perd l'intelligence adaptative

## 📊 Comparaison

| Système | Threads | Charge WebSocket | Intelligence |
|---------|---------|------------------|--------------|
| **Timer Classique** | 0 (juste des timers) | Très faible | Basique |
| **SmartBetTiming Actuel** | 1 par prédiction (20-30+) | **TRÈS ÉLEVÉE** ⚠️ | Très haute |
| **SmartBetTiming Optimisé** | 1 global | Faible | Très haute |
| **SmartBetTiming avec Pool** | 5 max | Moyenne | Très haute |

## 🎯 Recommandation

1. **Court terme** : Garde SmartBetTiming désactivé et vérifie que les WebSockets sont stables
2. **Moyen terme** : Implémente l'**Option 1** (thread global unique)
3. **Long terme** : Ajoute des métriques de monitoring pour détecter ce genre de problème

## 📝 Prochaines Étapes

1. ✅ **Redémarre le bot** avec SmartBetTiming désactivé
2. ⏳ **Surveille pendant 1-2 heures** pour confirmer la stabilité
3. 💬 **Dis-moi si les erreurs WebSocket ont disparu**
4. 🔧 Si confirmé, je peux implémenter l'Option 1 (thread global unique)

---

**Note** : C'est un excellent exemple de pourquoi le monitoring et les tests de charge sont importants. SmartBetTiming fonctionne parfaitement avec 1-5 streamers, mais avec 465 streamers et des prédictions simultanées, ça crée un problème d'échelle !
