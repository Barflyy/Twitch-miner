# 📂 Followers Data - Cache GitHub Unique

Ce dossier contient **LA SEULE SOURCE DE VÉRITÉ** pour les followers Twitch.

## 🎯 Fonctionnement

- **Source unique** : Le fichier GitHub est la seule référence
- **Persistance absolue** : Survit à tous les redéploiements/crashes  
- **Historique Git** : Toutes les modifications sont trackées
- **Auto-commit Railway** : Mise à jour automatique en production
- **Éditable** : Tu peux modifier manuellement tes followers

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

## 🔄 Flux de données

1. **Premier lancement** : Charge depuis Twitch API → Sauvegarde GitHub
2. **Démarrages suivants** : Charge uniquement depuis GitHub  
3. **Modification manuelle** : Tu peux éditer le fichier directement
4. **Auto-commit** : Railway commit automatiquement les changements

## ✅ Avantages

1. **Source unique** - pas de confusion entre caches
2. **Éditable en ligne** - ajouter/retirer des streamers depuis GitHub
3. **Zéro perte** - même si Railway crash complètement
4. **Historique complet** - voir l'évolution de tes follows
5. **Multi-environnement** - sync automatique local/Railway

## ✏️ Modification manuelle

Pour ajouter/retirer des streamers :
1. Va sur GitHub → `followers_data/barflyy__followers.json`
2. Clique "Edit" ✏️  
3. Modifie la liste `"followers"`
4. Commit → le bot utilisera automatiquement la nouvelle liste

---
*Cache GitHub unique - Source de vérité absolue*