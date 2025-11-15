# 📂 Followers Data - Cache Permanent GitHub

Ce dossier contient les fichiers de cache permanent des followers Twitch.

## 🎯 Fonctionnement

- **Persistance absolue** : Survit à tous les redéploiements/crashes
- **Historique Git** : Toutes les modifications sont trackées
- **Auto-commit Railway** : Mise à jour automatique en production
- **Fallback intelligent** : Si cache local perdu, restore depuis GitHub

## 📁 Structure

```
followers_data/
├── README.md                    # Ce fichier
├── barflyy__followers.json      # Cache followers pour barflyy_
└── [username]_followers.json    # Autres utilisateurs si multi-compte
```

## 📋 Format du fichier cache

```json
{
  "timestamp": 1700000000,
  "username": "barflyy_",
  "followers": ["streamer1", "streamer2", "..."],
  "count": 465,
  "version": "3.0",
  "last_update": "2025-11-15 12:00:00 UTC"
}
```

## 🔄 Synchronisation

- **Railway → GitHub** : Auto-commit à chaque mise à jour followers
- **GitHub → Local** : Auto-restore si cache local perdu
- **Durée de vie** : 48h (GitHub) vs 24h (local)

## ✅ Avantages

1. **Zéro perte de données** - même si Railway crash
2. **Visible sur GitHub** - tu peux voir tes followers en ligne
3. **Éditable manuellement** - ajouter/retirer des streamers
4. **Multi-environnement** - sync entre local/Railway/autres
5. **Backup automatique** - commit Git à chaque changement

---
*Généré automatiquement par le Twitch Miner*