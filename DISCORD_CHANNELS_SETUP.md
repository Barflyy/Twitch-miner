# 📺 Configuration des Salons Discord par Streamer

Le bot crée maintenant un **salon Discord dédié** pour chaque streamer !

## 🎯 Concept

- **1 salon = 1 streamer**
- **🟢 nom-du-streamer** = En ligne
- **🔴 nom-du-streamer** = Hors ligne
- Le salon change automatiquement de nom selon le statut
- Les infos sont dans un message fixe dans chaque salon

---

## ⚙️ Configuration

### 1️⃣ Créer une Catégorie Discord

Dans votre serveur Discord :

1. **Faites un clic droit** sur le serveur
2. **Créer un salon**
3. Choisissez **"Catégorie"**
4. Nommez-la (ex: **"📊 TWITCH MINER"**)

### 2️⃣ Obtenir l'ID de la Catégorie

1. **Activer le mode développeur Discord** :
   - Paramètres Discord → Avancés → Mode développeur ✅

2. **Copier l'ID de la catégorie** :
   - Clic droit sur la catégorie créée
   - **"Copier l'identifiant"**
   - Vous obtenez un ID comme `1234567890123456789`

### 3️⃣ Ajouter la variable sur Railway

**Railway → Votre projet → Settings → Variables**

Ajoutez :
```
DISCORD_CATEGORY_ID = 1234567890123456789
```

(Remplacez par votre ID réel)

### 4️⃣ Redéployer

Railway va automatiquement redéployer avec la nouvelle variable.

---

## ✨ Résultat

Le bot va créer automatiquement :

```
📊 TWITCH MINER
  ├─ 🟢-jltomy        <- En ligne
  ├─ 🟢-xqc           <- En ligne
  ├─ 🔴-ninja         <- Hors ligne
  └─ 🔴-shroud        <- Hors ligne
```

**Chaque salon contient :**
- Une fiche avec les stats du streamer
- Mise à jour automatique toutes les 30 secondes
- Le nom change selon le statut (🟢/🔴)

---

## 🎮 Commandes

Toutes les commandes fonctionnent toujours :

- `!status` - État général
- `!status <streamer>` - Fiche d'un streamer
- `!add <streamer>` - Ajoute un streamer (crée le salon)
- `!remove <streamer>` - Retire un streamer (supprime le salon)
- `!list` - Liste tous les streamers
- `!refresh` - Force la mise à jour des salons
- `!reset` - Supprime tous les salons

---

## 💡 Avantages

✅ **Organisation** : 1 salon par streamer  
✅ **Visuel** : Statut dans le nom (🟢/🔴)  
✅ **Propre** : Plus de spam dans un seul canal  
✅ **Scalable** : Supporte 100+ streamers  
✅ **Automatique** : Création/suppression/renommage auto  

---

## ❓ Troubleshooting

### Le bot ne crée pas de salons

**Vérifiez :**
1. `DISCORD_CATEGORY_ID` est bien défini dans Railway
2. Le bot a la permission **"Gérer les salons"**
3. La catégorie existe toujours sur Discord
4. L'ID de la catégorie est correct

### Les salons ne se renomment pas

Le bot met à jour les noms toutes les 30 secondes.  
Utilisez `!refresh` pour forcer la mise à jour.

### Permissions manquantes

Le bot doit avoir ces permissions :
- ✅ Gérer les salons
- ✅ Voir les salons
- ✅ Envoyer des messages
- ✅ Gérer les messages
- ✅ Intégrer des liens

**Re-inviter le bot avec le bon lien de permissions si nécessaire.**

---

## 🔄 Migration depuis l'ancien système

L'ancien système de "fiches" dans un seul canal est remplacé par ce système de salons.

**Pas d'action requise** : Le bot gère tout automatiquement dès que `DISCORD_CATEGORY_ID` est défini.

---

**Profitez de votre nouveau système de salons streamers ! 🎉**

