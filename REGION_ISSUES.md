# 🚨 Problèmes de Région - Prédictions Twitch Bloquées

## Problème

Twitch bloque les prédictions/paris dans certaines régions, notamment :
- **Union Européenne** (UE) : Amsterdam, Paris, Francfort, etc.
- Certains pays asiatiques
- Certaines régions spécifiques selon la législation locale

## 🔧 Solution pour Fly.io

### Changer la région Fly.io

Votre configuration actuelle dans `fly.toml` :
```toml
primary_region = "ams"  # Amsterdam (bloqué)
```

### Régions recommandées pour Twitch :

1. **US - Washington DC (`iad`)** ⭐ Recommandé
   ```toml
   primary_region = "iad"
   ```

2. **US - Oregon (`pdx`)**
   ```toml
   primary_region = "pdx"
   ```

3. **Singapour (`sin`)**
   ```toml
   primary_region = "sin"
   ```

4. **Japon (`hnd`)**
   ```toml
   primary_region = "hnd"
   ```

### Commandes Fly.io

```bash
# Changer la région
fly regions set iad

# Ou éditer fly.toml et redéployer
fly deploy
```

---

## 🔧 Solution pour Railway

1. Allez dans votre projet Railway
2. Settings → Service
3. Changez la région vers :
   - **US (Washington, Oregon)** ⭐ Recommandé
   - **US East**

---

## ⚠️ Régions à ÉVITER

- ❌ `ams` (Amsterdam) - UE, bloqué
- ❌ `cdg` (Paris) - UE, bloqué  
- ❌ `fra` (Francfort) - UE, bloqué
- ❌ `lhr` (Londres) - Restrictions possibles

---

## ✅ Vérification

Après avoir changé la région, redéployez et vérifiez les logs :
- ✅ Si ça fonctionne : Plus d'erreur `REGION_LOCKED`
- ❌ Si ça ne fonctionne toujours pas : Vérifiez les scopes du token OAuth

---

## 📝 Note

Les restrictions régionales sont imposées par Twitch, pas par le code. Si vous êtes bloqué dans une région, il faut soit :
1. Changer la région du serveur (recommandé)
2. Utiliser un VPN (moins stable pour un serveur)

