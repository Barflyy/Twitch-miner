# 🚀 Mode FOLLOWERS - Mining Automatique

Le bot mine maintenant **AUTOMATIQUEMENT tous vos follows Twitch** !

---

## 🎯 Concept

**Avant :**
- ❌ Liste manuelle de streamers
- ❌ Devoir ajouter/retirer manuellement
- ❌ Limité à quelques streamers

**Maintenant :**
- ✅ Suit TOUS vos follows Twitch automatiquement
- ✅ Nouveau follow = automatiquement miné
- ✅ Système de blacklist pour exclure
- ✅ Scalable à l'infini

---

## ⚙️ Comment ça marche ?

### Au démarrage du bot

1. **Connexion à Twitch** avec votre token OAuth
2. **Récupération automatique** de tous vos follows Twitch
3. **Filtrage** selon la blacklist (optionnelle)
4. **Mining** de tous les streamers restants

### Exemple

**Vos follows Twitch :**
- jltomy
- xqc
- shroud
- ninja
- faker

**Blacklist (optionnelle) :**
- xqc (trop de spam)
- faker (vous ne voulez pas miner)

**Résultat : Le bot mine :**
- ✅ jltomy
- ✅ shroud
- ✅ ninja
- ❌ xqc (blacklisté)
- ❌ faker (blacklisté)

---

## 🎮 Commandes Discord

### Gérer la blacklist

**`!blacklist <streamer>`**
- Ajoute un streamer à la blacklist
- Il ne sera plus miné
- Exemple : `!blacklist xqc`

**`!unblacklist <streamer>`**
- Retire un streamer de la blacklist
- Il sera à nouveau miné
- Exemple : `!unblacklist xqc`

**`!list`**
- Affiche la liste des streamers blacklistés
- Indique combien sont exclus

### Autres commandes

**`!status`**
- Affiche l'état général du bot
- Nombre de streamers suivis
- Nombre en ligne/hors ligne

**`!status <streamer>`**
- Affiche la fiche détaillée d'un streamer
- Points, paris, durée, etc.

**`!refresh`**
- Force la mise à jour des salons Discord
- Utile si vous venez de blacklister/unblacklister

**`!help`**
- Liste toutes les commandes disponibles

---

## 📋 Fichiers

### `blacklist.json`

Contient la liste des streamers exclus :

```json
[
  "xqc",
  "faker"
]
```

**Géré automatiquement** par les commandes `!blacklist` et `!unblacklist`.

Vous pouvez aussi l'éditer manuellement sur Railway (ou localement).

---

## ✨ Avantages

### 1. **Zéro maintenance**
- Vous follow un nouveau streamer sur Twitch ?
- → Le bot le mine automatiquement au prochain redémarrage !

### 2. **Scalable**
- Suivez 1 streamer ou 1000 streamers
- Le bot s'adapte automatiquement

### 3. **Flexible**
- Blacklist pour exclure qui vous voulez
- Pas besoin de refaire la liste à chaque fois

### 4. **Synchronisé**
- Vos follows Twitch = source de vérité
- Pas de décalage entre Twitch et le bot

---

## 🔧 Configuration Technique

### Variables d'environnement Railway

**Obligatoires :**
```
TWITCH_USERNAME = votre_username
TWITCH_AUTH_TOKEN = votre_token_oauth
```

**Token OAuth :**
- Généré sur https://twitchtokengenerator.com/
- **Scopes requis :**
  - `user:read:email`
  - `channel:read:redemptions`
  - `channel:read:predictions` (pour les paris)
  - `channel:manage:predictions` (pour placer des paris)
  - `chat:read`
  - `user_read`
  - `channel_read`

---

## 🚨 Résolution de problèmes

### Le bot ne mine pas tous mes follows

**Vérifiez :**
1. `TWITCH_AUTH_TOKEN` est valide
2. Le token a les bons scopes
3. La blacklist ne contient pas trop de streamers
4. Les logs Railway pour voir quels follows ont été chargés

**Commande de débogage :**
```
!status
```
→ Affiche le nombre total de streamers suivis

### "Region blocked" sur les paris

**Cause :** Token OAuth sans les scopes `predictions`.

**Solution :** Régénérez le token avec les scopes :
- `channel:read:predictions`
- `channel:manage:predictions`

### Un streamer ne devrait pas être miné

**Solution :**
```
!blacklist nom_du_streamer
```

Puis redémarrez le miner (ou attendez le prochain redémarrage automatique).

---

## 📊 Statistiques

Le bot affiche au démarrage :

```
📋 Le bot va suivre automatiquement TOUS vos follows Twitch
🚫 Blacklist: xqc, faker
Loading data for 98 streamers. Please wait...
```

**98 streamers** = 100 follows - 2 blacklistés

---

## 💡 Conseils

### Optimiser la blacklist

**Blacklistez :**
- ❌ Streamers qui ne font jamais de stream (inactifs)
- ❌ Streamers avec trop peu de points à gagner
- ❌ Streamers que vous ne regardez jamais

**Ne blacklistez PAS :**
- ✅ Streamers actifs avec points à gagner
- ✅ Streamers qui font des drops
- ✅ Streamers avec des paris intéressants

### Vérifier régulièrement

Utilisez `!status` pour voir :
- Combien de streamers sont suivis
- Combien sont en ligne
- S'il y a des problèmes

---

## 🔄 Migration depuis l'ancien système

**Ancien système (streamers_list.json) :**
```json
["jltomy", "xqc", "shroud"]
```
→ **Géré manuellement**

**Nouveau système (FOLLOWERS) :**
- Suit automatiquement tous vos follows Twitch
- Blacklist optionnelle pour exclure

**Pas d'action requise** : Le bot bascule automatiquement.

Si vous aviez une liste manuelle, vous pouvez :
1. Supprimer `streamers_list.json` (plus utilisé)
2. Créer `blacklist.json` pour exclure certains streamers

---

## 🎉 Profitez !

Vous n'avez plus à gérer manuellement la liste de streamers.

**Followez sur Twitch = Miné automatiquement !**

Simple, efficace, scalable. 🚀

