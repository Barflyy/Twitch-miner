# Configuration API Twitch Helix (Accélération chargement followers)

## Pourquoi utiliser l'API Helix ?

Le bot utilise désormais l'API officielle Twitch Helix pour charger la liste des followers, ce qui est **beaucoup plus rapide** que l'ancienne méthode GraphQL :

- **Avant (GraphQL)** : ~1.5 secondes pour 465 followers (~297 followers/sec)
- **Après (API Helix)** : ~0.3 secondes pour 465 followers (~1500 followers/sec)

**Gain de performance : 5x plus rapide ! 🚀**

## Comment activer l'API Helix ?

### 1. Créer une application Twitch

1. Va sur **https://dev.twitch.tv/console/apps**
2. Clique sur **"Register Your Application"**
3. Remplis les champs :
   - **Name** : `Twitch Points Miner` (ou autre nom)
   - **OAuth Redirect URLs** : `http://localhost` (obligatoire, mais pas utilisé)
   - **Category** : `Application Integration`
4. Clique sur **"Create"**
5. Une fois créée, clique sur **"Manage"**

### 2. Récupérer les identifiants

Sur la page de ton application, tu verras :

- **Client ID** : `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- **Client Secret** : Clique sur **"New Secret"** pour générer un secret

**⚠️ IMPORTANT** : Ne partage JAMAIS ces identifiants publiquement !

### 3. Configurer les variables d'environnement

#### Sur Railway/Fly.io (production)

Ajoute ces secrets via l'interface web :

```
TWITCH_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWITCH_CLIENT_SECRET=yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
```

#### En local (développement)

Méthode 1 : Export dans le terminal (temporaire)

```bash
export TWITCH_CLIENT_ID="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export TWITCH_CLIENT_SECRET="yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"
python run.py
```

Méthode 2 : Fichier `.env` (recommandé)

Crée un fichier `.env` à la racine du projet :

```bash
TWITCH_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWITCH_CLIENT_SECRET=yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
TWITCH_USERNAME=barflyy_
```

Puis installe `python-dotenv` et charge les variables dans `run.py` :

```python
from dotenv import load_dotenv
load_dotenv()  # Charge les variables depuis .env
```

**⚠️ N'oublie pas d'ajouter `.env` au `.gitignore` !**

### 4. Vérifier le fonctionnement

Lance le bot :

```bash
python run.py
```

Tu devrais voir dans les logs :

```
🔑 Authentification API Twitch Helix...
✅ User ID Twitch: 123456789
🚀 Chargement des followers via API Twitch Helix (rapide)...
📈 100 followers chargés (500.0/sec)...
📈 200 followers chargés (600.0/sec)...
✅ Total: 465 followers chargés via API Helix en 0.3s (1550.0/sec) 🚀
```

## Fallback automatique

Si les variables d'environnement ne sont **pas configurées** ou si l'API Helix échoue, le bot utilisera automatiquement l'ancienne méthode GraphQL (plus lente mais fiable).

Tu verras ce message dans les logs :

```
⚠️ TWITCH_CLIENT_ID et TWITCH_CLIENT_SECRET requis pour API Helix
⚠️ Fallback sur méthode GraphQL (plus lente)
📥 Chargement des followers depuis Twitch GraphQL (peut prendre plusieurs minutes)...
```

## Cache GitHub

Peu importe la méthode utilisée (Helix ou GraphQL), la liste des followers est **toujours sauvegardée dans le cache GitHub** pour éviter de recharger à chaque démarrage.

Le cache reste valide **12 heures** par défaut.

## Sécurité

- ✅ Ne commit **JAMAIS** `TWITCH_CLIENT_ID` et `TWITCH_CLIENT_SECRET` dans le code
- ✅ Utilise toujours des variables d'environnement
- ✅ Ajoute `.env` au `.gitignore`

## Résumé

| Étape | Description |
|-------|-------------|
| 1️⃣ | Créer une app sur https://dev.twitch.tv/console/apps |
| 2️⃣ | Copier `Client ID` et générer `Client Secret` |
| 3️⃣ | Ajouter les secrets sur Railway/Fly.io ou dans `.env` |
| 4️⃣ | Lancer le bot et vérifier les logs |

✅ **C'est tout ! Profite des performances améliorées 🚀**
