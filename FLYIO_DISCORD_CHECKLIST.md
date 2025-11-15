# ✅ Checklist Bot Discord sur Fly.io

## 🔍 Vérifications à faire après migration Railway → Fly.io

### 1. 📋 Variables d'environnement Fly.io

Vérifiez que toutes ces variables sont configurées dans **Fly.io Secrets** :

#### Variables OBLIGATOIRES :
```bash
✅ DISCORD_BOT_TOKEN          # Token du bot Discord
✅ DISCORD_CHANNEL_ID        # ID du canal Discord pour les commandes
✅ TWITCH_USERNAME           # Votre username Twitch
✅ TWITCH_AUTH_TOKEN         # Token OAuth Twitch
```

#### Variables OPTIONNELLES (mais recommandées) :
```bash
✅ DISCORD_CATEGORY_ID       # ID de la catégorie pour créer les salons streamers
✅ USE_DISCORD_BOT           # "true" pour activer le bot Discord
```

#### Comment vérifier sur Fly.io :
```bash
# Via CLI
fly secrets list -a twitch-miner

# Via Dashboard
# https://fly.io/apps/twitch-miner → Secrets
```

---

### 2. 🚀 Commande de démarrage

Vérifiez que Fly.io lance bien `launcher.py` (qui démarre les 2 bots) :

#### Dans `fly.toml` :
```toml
[build]

[processes]
  app = "python -u launcher.py"
```

**OU** via le Procfile (si Fly.io le détecte) :
```
worker: python -u launcher.py
```

#### Vérification :
```bash
# Voir les logs au démarrage
fly logs -a twitch-miner

# Vous devriez voir :
🚀 LAUNCHER - Twitch Miner + Bot Discord
🤖 Démarrage du Bot Discord...
⛏️  Démarrage du Miner...
```

---

### 3. 📁 Fichiers persistants

Le bot Discord utilise `bot_data.json` pour stocker les données. Sur Fly.io, ce fichier est sauvegardé dans le répertoire du projet (persiste entre déploiements).

**Vérifiez que le fichier existe** :
```bash
fly ssh console -a twitch-miner
ls -la bot_data.json
```

---

### 4. 🔐 Permissions Discord Bot

Vérifiez que votre bot Discord a les bonnes permissions :

#### Intents requis (dans Discord Developer Portal) :
- ✅ **MESSAGE CONTENT INTENT** (obligatoire)
- ✅ **SERVER MEMBERS INTENT** (optionnel mais recommandé)

#### Permissions du bot dans votre serveur :
- ✅ Send Messages
- ✅ Embed Links
- ✅ Read Message History
- ✅ Manage Channels (si vous utilisez la création automatique de salons)

---

### 5. 🐛 Diagnostic des erreurs courantes

#### ❌ "DISCORD_BOT_TOKEN manquant"
**Solution** : Ajoutez le secret dans Fly.io
```bash
fly secrets set DISCORD_BOT_TOKEN=votre_token -a twitch-miner
```

#### ❌ "Bot connecté mais pas de messages"
**Vérifiez** :
1. Le bot est bien invité sur votre serveur Discord
2. `DISCORD_CHANNEL_ID` est correct
3. Le bot a la permission "Send Messages" dans le canal

#### ❌ "Le bot se connecte mais ne met pas à jour les fiches"
**Vérifiez** :
1. `USE_DISCORD_BOT=true` est défini
2. Le miner Twitch fonctionne (vérifiez les logs `[MINER]`)
3. Le fichier `bot_data.json` est créé et mis à jour

#### ❌ "Le bot ne démarre pas"
**Vérifiez les logs** :
```bash
fly logs -a twitch-miner | grep -i "bot\|discord\|error"
```

---

### 6. 📊 Vérification du fonctionnement

#### Au démarrage, vous devriez voir :
```
✅ Bot connecté: NomDuBot
📋 ID: 123456789
🔄 Mise à jour automatique activée (30 secondes)
```

#### Dans les logs du miner :
```
✅ Mode Bot Discord activé (fiches éditables, pas de spam webhook)
```

#### Testez une commande Discord :
```
!status
```
→ Le bot devrait répondre avec les statistiques

---

### 7. 🔄 Redémarrage après configuration

Après avoir ajouté/modifié des secrets :
```bash
fly apps restart twitch-miner
```

Puis surveillez les logs :
```bash
fly logs -a twitch-miner
```

---

## 📝 Checklist rapide

- [ ] `DISCORD_BOT_TOKEN` configuré dans Fly.io Secrets
- [ ] `DISCORD_CHANNEL_ID` configuré
- [ ] `TWITCH_USERNAME` configuré
- [ ] `TWITCH_AUTH_TOKEN` configuré
- [ ] `USE_DISCORD_BOT=true` (optionnel, true par défaut)
- [ ] Bot Discord invité sur le serveur avec les bonnes permissions
- [ ] Intents activés dans Discord Developer Portal
- [ ] `launcher.py` est bien la commande de démarrage
- [ ] Les logs montrent "Bot connecté" au démarrage
- [ ] La commande `!status` fonctionne dans Discord

---

## 🆘 Besoin d'aide ?

1. **Vérifiez les logs** : `fly logs -a twitch-miner`
2. **Vérifiez les secrets** : `fly secrets list -a twitch-miner`
3. **Testez en console** : `fly ssh console -a twitch-miner`
4. **Vérifiez que les deux processus tournent** : Les logs doivent montrer `[BOT]` et `[MINER]`

