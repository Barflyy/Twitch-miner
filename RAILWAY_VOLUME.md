# 💾 Configurer un Volume Persistant sur Railway

Pour éviter de devoir se reconnecter à chaque déploiement, on va sauvegarder les cookies Twitch dans un volume Railway persistant.

---

## 🔧 Configuration Railway

### 1. Créer un Volume

Dans Railway :
1. Allez dans votre projet Twitch Miner
2. Cliquez sur **Settings**
3. Allez dans **Volumes**
4. Cliquez sur **+ New Volume**

**Configuration :**
```
Volume Name: twitch-cookies
Mount Path: /cookies
```

Cliquez sur **Add**

### 2. Variables d'environnement (déjà configurées)

Vérifiez que vous avez :
```
TWITCH_USERNAME = votre_username
TWITCH_AUTH_TOKEN = (votre token - peut rester vide)
```

---

## 🎯 Comment ça fonctionne

### Premier déploiement
1. Le miner démarre
2. Il demande le code TV (une seule fois)
3. Les cookies sont sauvegardés dans `/cookies/`
4. Railway persiste ce volume

### Déploiements suivants
1. Le miner démarre
2. Il trouve les cookies dans `/cookies/`
3. **Pas besoin de code !** ✅
4. Connexion automatique

---

## 📝 Vérification

Après avoir configuré le volume et redéployé :

**Logs Railway (premier démarrage) :**
```
🔐 Authenticating with Twitch...
📱 Open https://www.twitch.tv/activate
📱 Enter code: ABCD1234
✅ Authentication successful
💾 Cookies saved to /cookies/
```

**Logs Railway (démarrage suivant) :**
```
🔐 Authenticating with Twitch...
💾 Found cookies in /cookies/
✅ Authentication successful (using saved cookies)
```

---

## ⚙️ Alternative : Token OAuth Direct

Si vous voulez éviter complètement le code TV, vous pouvez utiliser un token OAuth directement.

### Obtenir un token OAuth Twitch

1. **Aller sur** : https://twitchtokengenerator.com/
2. **Sélectionner** : Custom Scope Token Generator
3. **Scopes nécessaires** :
   - `chat:read`
   - `channel:read:redemptions`
   - `user:read:email`
4. **Generate Token**
5. **Copier le Access Token**

### Mettre le token dans Railway

Railway → Settings → Variables → Edit `TWITCH_AUTH_TOKEN`
```
TWITCH_AUTH_TOKEN = <votre_token_oauth>
```

**Avantage :** Pas de code TV du tout
**Inconvénient :** Le token expire (mais rarement, généralement après plusieurs mois)

---

## 🚀 Recommandation

**Utilisez le Volume Railway** :
- Plus stable long terme
- Pas besoin de gérer les tokens
- Une seule authentification nécessaire

---

## 🐛 Dépannage

### Le bot demande encore le code après config du volume

- Vérifiez que le Mount Path est bien `/cookies`
- Vérifiez que le volume est attaché au service
- Redéployez après avoir créé le volume

### Les cookies ne sont pas sauvegardés

- Vérifiez les permissions du volume (lecture/écriture)
- Vérifiez les logs : cherchez "Cookies saved"

---

**Une fois configuré, vous n'aurez plus jamais besoin du code !** 🎉

