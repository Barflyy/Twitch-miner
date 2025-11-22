# 🔐 Configuration Push Automatique GitHub sur Fly.io

## 📋 Prérequis

Pour activer le push automatique des followers vers GitHub, tu dois configurer un **Personal Access Token (PAT)** GitHub.

## 🔑 Créer un Token GitHub

1. **Va sur GitHub** → Settings → Developer settings → Personal access tokens → Tokens (classic)
   - URL: https://github.com/settings/tokens

2. **Clique sur "Generate new token (classic)"**

3. **Configure le token :**
   - **Note** : `Fly.io Bot - Twitch Miner`
   - **Expiration** : `No expiration` (ou 1 an selon tes préférences)
   - **Scopes** : Coche uniquement :
     - ✅ `repo` (Full control of private repositories)
       - Cela donne les permissions nécessaires pour push

4. **Génère le token** et **copie-le immédiatement** (tu ne pourras plus le voir après)

## 🚀 Configurer sur Fly.io

### Option 1 : Via Fly CLI

```bash
# Définir le secret (token GitHub)
fly secrets set GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optionnel : Définir l'URL du repo (si différent)
fly secrets set GITHUB_REPO=https://github.com/Barflyy/Twitch-miner
```

### Option 2 : Via Fly.io Dashboard

1. Va sur https://fly.io/apps/twitch-miner
2. Clique sur **Secrets** dans le menu de gauche
3. Ajoute les secrets :
   - **Name** : `GITHUB_TOKEN`
   - **Value** : `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` (ton token)
   
   - **Name** : `GITHUB_REPO` (optionnel)
   - **Value** : `https://github.com/Barflyy/Twitch-miner`

## ✅ Vérification

Après avoir configuré le token, redémarre l'application :

```bash
fly apps restart twitch-miner
```

Les logs devraient maintenant afficher :
```
📂 Auto-commit réalisé : 465 followers
📂 Push GitHub réussi
```

Au lieu de :
```
⚠️ Push GitHub échoué (token manquant)
```

## 🔒 Sécurité

- ⚠️ **Ne jamais** commiter le token dans le code
- ✅ Utilise **toujours** les secrets Fly.io pour stocker le token
- ✅ Le token est stocké de manière sécurisée et n'est jamais exposé dans les logs

## 🐛 Dépannage

### Le push échoue toujours

1. **Vérifie que le token a les bonnes permissions** :
   - Le scope `repo` est nécessaire
   - Le token doit être actif (pas expiré)

2. **Vérifie les logs Fly.io** :
   ```bash
   fly logs -a twitch-miner
   ```

3. **Teste manuellement** :
   ```bash
   fly ssh console -a twitch-miner
   # Dans le shell
   echo $GITHUB_TOKEN  # Doit afficher le token
   ```

### Le remote origin n'est pas configuré

Le code configure automatiquement le remote si `GITHUB_REPO` est défini. Sinon, il utilise le remote existant du repo cloné.

## 📝 Notes

- Le push est **non bloquant** : si le push échoue, le commit local est toujours fait
- Le cache fonctionne même sans push (sauvegarde locale)
- Le push automatique se fait uniquement sur Fly.io (pas en local pour éviter les conflits)

---

**Une fois configuré, les followers seront automatiquement poussés vers GitHub à chaque mise à jour !** 🚀

