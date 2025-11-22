#!/bin/bash

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🤖 Twitch Miner Manager${NC}"
echo "--------------------------------"

case "$1" in
  deploy)
    echo -e "${YELLOW}🚀 Déploiement en cours sur Fly.io...${NC}"
    flyctl deploy
    ;;
  
  logs)
    echo -e "${BLUE}📋 Affichage des logs en direct...${NC}"
    flyctl logs
    ;;
  
  restart)
    echo -e "${YELLOW}🔄 Redémarrage de l'application...${NC}"
    flyctl apps restart twitch-miner
    ;;
  
  status)
    echo -e "${BLUE}📊 Statut de l'application...${NC}"
    flyctl status
    ;;
    
  stop)
    echo -e "${RED}🛑 Arrêt de l'application...${NC}"
    flyctl scale count 0
    ;;
    
  start)
    echo -e "${GREEN}▶️ Démarrage de l'application...${NC}"
    flyctl scale count 1
    ;;

  *)
    echo "Usage: ./manage.sh {deploy|logs|restart|status|stop|start}"
    echo ""
    echo "  deploy  : Déploie la dernière version du code"
    echo "  logs    : Affiche les logs en direct"
    echo "  restart : Redémarre le bot sans redéployer"
    echo "  status  : Affiche l'état des machines"
    echo "  stop    : Arrête le bot (économise des crédits)"
    echo "  start   : Démarre le bot s'il est arrêté"
    exit 1
    ;;
esac
