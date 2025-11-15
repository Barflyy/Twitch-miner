#!/bin/bash
# Script pour détruire la machine corrompue et redéployer

echo "🔧 Fix machine Fly.io corrompue"
echo "================================"
echo ""

# Machine corrompue
MACHINE_ID="2863674ae5e708"
APP_NAME="twitch-miner"

echo "1️⃣ Destruction de la machine corrompue: $MACHINE_ID"
fly machine destroy $MACHINE_ID -a $APP_NAME --force

if [ $? -eq 0 ]; then
    echo "✅ Machine détruite avec succès"
else
    echo "⚠️  Erreur lors de la destruction (peut-être déjà détruite)"
fi

echo ""
echo "2️⃣ Attente de 5 secondes..."
sleep 5

echo ""
echo "3️⃣ Redéploiement de l'application..."
fly deploy -a $APP_NAME

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Déploiement terminé !"
    echo ""
    echo "📊 Vérifiez les logs avec:"
    echo "   fly logs -a $APP_NAME"
else
    echo ""
    echo "❌ Erreur lors du déploiement"
    echo "Vérifiez les secrets avec: fly secrets list -a $APP_NAME"
fi

