# Configuration API Twitch Helix (Accélération chargement followers)

## Pourquoi utiliser l'API Helix ?

Le bot utilise désormais l'API officielle Twitch Helix pour charger la liste des followers, ce qui est **beaucoup plus rapide** que l'ancienne méthode GraphQL :

- **Avant (GraphQL)** : ~1.5 secondes pour 465 followers (~297 followers/sec)
- **Après (API Helix)** : ~0.3 secondes pour 465 followers (~1500 followers/sec)

**Gain de performance : 5x plus rapide ! 🚀**

## Comment ça fonctionne ?

### Mode automatique (aucune configuration requise) ✅

L'API Helix utilise le **User Access Token OAuth** que le bot obtient automatiquement lors de l'authentification via le **TV Login** (code d'activation Twitch).

**Aucune configuration supplémentaire n'est requise !** Le bot utilisera automatiquement l'API Helix si :
- Le bot est correctement authentifié (cookies valides)
- L'API Helix est accessible

### Fallback automatique sur GraphQL

Si l'API Helix échoue pour une raison quelconque, le bot basculera automatiquement sur l'ancienne méthode GraphQL (plus lente mais fiable).

Tu verras ce message dans les logs :

```
⚠️ Fallback sur méthode GraphQL (plus lente)
📥 Chargement des followers depuis Twitch GraphQL (peut prendre plusieurs minutes)...
```

## Logs de fonctionnement

### Avec API Helix (rapide)

```
🔑 Utilisation API Twitch Helix avec User Access Token
✅ User ID Twitch: 439920856
🚀 Chargement des followers via API Twitch Helix (rapide)...
📈 100 followers chargés (500.0/sec)...
📈 200 followers chargés (600.0/sec)...
✅ Total: 465 followers chargés via API Helix en 0.3s (1550.0/sec) 🚀
📂 Followers sauvegardés sur GitHub : 465 followers
```

### Avec GraphQL (fallback)

```
⚠️ Fallback sur méthode GraphQL (plus lente)
📥 Chargement des followers depuis Twitch GraphQL (peut prendre plusieurs minutes)...
🚀 Chargement optimisé des followers (chunks de 100)...
📈 500 followers chargés (297.3/sec)
✅ Total: 465 followers chargés en 1.6s
```

## Cache GitHub

Peu importe la méthode utilisée (Helix ou GraphQL), la liste des followers est **toujours sauvegardée dans le cache GitHub** pour éviter de recharger à chaque démarrage.

Le cache reste valide **12 heures** par défaut.

## Sécurité

- ✅ Utilise le **User Access Token OAuth** déjà authentifié (pas de configuration supplémentaire)
- ✅ Pas besoin de créer une application Twitch
- ✅ Pas besoin de variables d'environnement supplémentaires

## Résumé

| Méthode | Vitesse | Configuration |
|---------|---------|---------------|
| **API Helix** (défaut) | 🚀 Ultra rapide (~1500/sec) | ✅ Aucune (automatique) |
| **GraphQL** (fallback) | 🐌 Lent (~297/sec) | ✅ Aucune (fallback auto) |

✅ **C'est tout ! Le bot utilise automatiquement la méthode la plus rapide 🚀**

## Ancienne méthode (Client Credentials) - Obsolète

~~L'ancienne version nécessitait de créer une application Twitch et de configurer `TWITCH_CLIENT_ID` et `TWITCH_CLIENT_SECRET`. Cette méthode n'est plus nécessaire car elle créait un **App Access Token** qui n'a pas les permissions pour lire les followers.~~

La nouvelle version utilise le **User Access Token** déjà authentifié par le bot, ce qui est plus simple et plus sécurisé.

