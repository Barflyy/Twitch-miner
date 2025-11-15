# -*- coding: utf-8 -*-
"""
Cache permanent GitHub pour followers Twitch
Sauvegarde et synchronise les followers via Git commits
"""
import json
import os
import subprocess
import time
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class GitHubCache:
    """Cache permanent des followers via commits Git"""
    
    def __init__(self, username: str):
        self.username = username
        # Chemin du fichier : followers_data/username_followers.json
        # Le fichier doit être présent dans le repo (copié par Dockerfile)
        self.cache_file = Path(f"followers_data/{username}_followers.json")
        self.cache_file.parent.mkdir(exist_ok=True)
        
        # Log pour debug
        logger.debug(f"📂 Chemin cache : {self.cache_file.absolute()}")
        logger.debug(f"📂 Fichier existe : {self.cache_file.exists()}")
        
    def load_followers(self) -> List[str]:
        """Charge les followers depuis le fichier Git"""
        try:
            if self.cache_file.exists():
                logger.debug(f"📂 Fichier trouvé : {self.cache_file}")
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Vérifier la validité
                if self._is_cache_valid(data):
                    followers = data.get('followers', [])
                    hours_old = (time.time() - data['timestamp']) / 3600
                    logger.info(
                        f"📂 Cache GitHub chargé : {len(followers)} followers (mis à jour il y a {hours_old:.1f}h)",
                        extra={"emoji": ":file_folder:"}
                    )
                    return followers
                else:
                    # Log plus détaillé pour comprendre pourquoi le cache est invalide
                    cache_age = time.time() - data.get('timestamp', 0)
                    logger.warning(f"⚠️ Cache GitHub invalide ou expiré (âge: {cache_age/3600:.1f}h)")
            else:
                logger.warning(f"⚠️ Fichier JSON introuvable : {self.cache_file.absolute()}")
                logger.info("📂 Aucun cache GitHub trouvé, première synchronisation...")
        except Exception as e:
            logger.error(f"❌ Erreur lecture cache GitHub : {e}", exc_info=True)
        
        return []
    
    def save_followers(self, followers: List[str]) -> bool:
        """Sauvegarde et commit les followers sur GitHub avec écriture atomique"""
        try:
            # Préparer les données avec métadonnées enrichies
            cache_data = {
                'timestamp': time.time(),
                'username': self.username,
                'followers': followers,
                'count': len(followers),
                'version': '3.1',  # Version bump pour la nouvelle logique
                'last_update': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
                'cache_ttl_hours': 12  # Durée de validité du cache
            }

            # Écriture atomique (évite corruption si crash pendant écriture)
            temp_file = self.cache_file.with_suffix('.tmp')
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, indent=2, ensure_ascii=False)

                # Remplacement atomique (opération système garantie atomique)
                temp_file.replace(self.cache_file)

            finally:
                # Cleanup du fichier temporaire en cas d'erreur
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except:
                        pass

            # Auto-commit si on est sur Fly.io (pas en local pour éviter les conflits)
            if os.getenv("FLY_APP_NAME") and self._should_auto_commit():
                self._git_commit_followers(len(followers))

            logger.info(
                f"📂 Cache GitHub sauvegardé : {len(followers)} followers → {self.cache_file}",
                extra={"emoji": ":file_folder:"}
            )
            return True

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde cache GitHub : {e}")
            return False
    
    def _is_cache_valid(self, data: Dict[str, Any]) -> bool:
        """Vérifie si le cache est valide et récent"""
        try:
            # Vérifier la structure
            required_keys = ['timestamp', 'username', 'followers', 'count']
            if not all(key in data for key in required_keys):
                logger.warning("⚠️ Cache invalide : structure incomplète")
                return False

            # Vérifier l'utilisateur (sécurité : chaque user a son propre cache)
            if data['username'] != self.username:
                logger.warning(f"⚠️ Cache invalide : appartient à {data['username']}, pas {self.username}")
                return False

            # Vérifier l'âge (12h max pour refresh régulier, équilibre perf/fraîcheur)
            cache_age = time.time() - data['timestamp']
            max_age = 12 * 3600  # 12 heures (au lieu de 7 jours)

            if cache_age >= max_age:
                logger.info(f"⚠️ Cache expiré : {cache_age/3600:.1f}h > 12h")
                return False

            return True

        except Exception as e:
            logger.warning(f"⚠️ Erreur validation cache : {e}")
            return False
    
    def _should_auto_commit(self) -> bool:
        """Vérifie si on doit faire un auto-commit"""
        try:
            # Vérifier si Git est disponible
            subprocess.run(['git', '--version'], capture_output=True, check=True)
            
            # Vérifier si le fichier a changé
            result = subprocess.run(
                ['git', 'diff', '--quiet', str(self.cache_file)],
                capture_output=True
            )
            
            # Si git diff retourne 1, il y a des changements
            return result.returncode == 1
            
        except:
            return False
    
    def _git_commit_followers(self, count: int):
        """Commit automatique des followers"""
        try:
            # Configurer Git si nécessaire (Fly.io)
            subprocess.run([
                'git', 'config', '--global', 'user.email', 'flyio@bot.com'
            ], capture_output=True, check=False)
            subprocess.run([
                'git', 'config', '--global', 'user.name', 'Fly.io Bot'
            ], capture_output=True, check=False)
            
            # Configurer le remote origin si pas déjà configuré
            try:
                result = subprocess.run(
                    ['git', 'remote', 'get-url', 'origin'],
                    capture_output=True,
                    check=False
                )
                if result.returncode != 0:
                    # Remote origin n'existe pas, le créer
                    github_repo = os.getenv('GITHUB_REPO')
                    if github_repo:
                        subprocess.run([
                            'git', 'remote', 'add', 'origin', github_repo
                        ], capture_output=True, check=False)
                        logger.debug("📂 Remote origin configuré")
            except:
                pass
            
            # Add et commit
            subprocess.run(['git', 'add', str(self.cache_file)], check=True, capture_output=True)
            
            commit_msg = f"📊 Update followers cache: {count} followers ({self.username})"
            subprocess.run([
                'git', 'commit', '-m', commit_msg
            ], check=True, capture_output=True)
            
            logger.info(f"📂 Auto-commit réalisé : {count} followers")
            
            # Push vers GitHub avec token si disponible
            github_token = os.getenv('GITHUB_TOKEN')
            if github_token:
                # Utiliser le token pour le push
                try:
                    # Récupérer l'URL du remote
                    result = subprocess.run(
                        ['git', 'remote', 'get-url', 'origin'],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    remote_url = result.stdout.strip()
                    
                    # Injecter le token dans l'URL
                    if remote_url.startswith('https://'):
                        # Format: https://token@github.com/user/repo.git
                        if '@' not in remote_url:
                            # Extraire le repo de l'URL
                            if remote_url.startswith('https://github.com/'):
                                repo_path = remote_url.replace('https://github.com/', '')
                                auth_url = f"https://{github_token}@github.com/{repo_path}"
                                
                                # Configurer temporairement l'URL avec le token
                                subprocess.run([
                                    'git', 'remote', 'set-url', 'origin', auth_url
                                ], capture_output=True, check=True)
                        
                        # Push avec le token
                        subprocess.run(
                            ['git', 'push', 'origin', 'master'],
                            timeout=30,
                            check=True,
                            capture_output=True
                        )
                        logger.info("📂 Push GitHub réussi")
                    else:
                        # SSH, utiliser directement
                        subprocess.run(
                            ['git', 'push', 'origin', 'master'],
                            timeout=30,
                            check=True,
                            capture_output=True
                        )
                        logger.info("📂 Push GitHub réussi (SSH)")
                        
                except subprocess.TimeoutExpired:
                    logger.warning("⚠️ Push GitHub timeout (non bloquant)")
                except Exception as e:
                    logger.warning(f"⚠️ Push GitHub échoué : {e} (non bloquant)")
            else:
                # Essayer sans token (peut fonctionner si déjà authentifié)
                try:
                    subprocess.run(
                        ['git', 'push', 'origin', 'master'],
                        timeout=30,
                        check=True,
                        capture_output=True
                    )
                    logger.info("📂 Push GitHub réussi (sans token)")
                except Exception as e:
                    logger.warning(f"⚠️ Push GitHub échoué (token manquant) : {e}")
                    logger.info("💡 Configurez GITHUB_TOKEN pour activer le push automatique")
                
        except Exception as e:
            logger.warning(f"⚠️ Auto-commit échoué : {e}")


    def invalidate_cache(self) -> bool:
        """Force l'invalidation du cache (force un refresh à la prochaine lecture)"""
        try:
            if self.cache_file.exists():
                # Supprimer le fichier de cache
                self.cache_file.unlink()
                logger.info(f"🗑️ Cache invalidé : {self.cache_file}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Erreur invalidation cache : {e}")
            return False

    def get_cache_age(self) -> float:
        """Retourne l'âge du cache en heures (ou -1 si pas de cache)"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    cache_age = (time.time() - data['timestamp']) / 3600
                    return cache_age
        except:
            pass
        return -1.0


def get_github_cache(username: str) -> GitHubCache:
    """Factory pour créer une instance de cache GitHub"""
    return GitHubCache(username)