# 🔄 Recréer la machine Fly.io

Votre machine Fly.io est dans un état corrompu et crash immédiatement. Il faut la détruire et en créer une nouvelle.

## 🚀 Solution rapide

Exécutez ces commandes dans l'ordre :

```bash
# 1. Détruire la machine corrompue
fly machine destroy 2863674ae5e708 -a twitch-miner --force

# 2. Redéployer (créera une nouvelle machine automatiquement)
fly deploy -a twitch-miner
```

## 📋 Alternative : Via le dashboard Fly.io

1. Allez sur https://fly.io/apps/twitch-miner
2. Cliquez sur **Machines**
3. Trouvez la machine `2863674ae5e708`
4. Cliquez sur **Destroy** (ou les 3 points → Destroy)
5. Confirmez la destruction
6. Cliquez sur **Deploy** pour redéployer

## ✅ Vérification après redéploiement

Après le redéploiement, vérifiez les logs :

```bash
fly logs -a twitch-miner
```

Vous devriez voir :
```
==================================================
🚀 START.PY - Script de démarrage
🐍 Python: 3.10.x
📁 Working directory: /app
...
```

## 🔍 Si ça crash encore

Vérifiez les secrets :
```bash
fly secrets list -a twitch-miner
```

Les secrets requis :
- ✅ `TWITCH_USERNAME`
- ✅ `TWITCH_AUTH_TOKEN`
- ⚠️ `DISCORD_BOT_TOKEN` (optionnel)
- ⚠️ `DISCORD_CHANNEL_ID` (optionnel)

Si un secret manque, ajoutez-le :
```bash
fly secrets set NOM_SECRET=valeur -a twitch-miner
```

