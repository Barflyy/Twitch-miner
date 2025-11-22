FROM python:3.10-slim

WORKDIR /usr/src/app

# Variables d'environnement pour Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Installer les dépendances système minimales
# git: pour certaines dépendances pip
# gcc, libc-dev: pour compiler certains paquets python si pas de wheel
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    libc-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copier requirements
COPY requirements.txt ./

# Installer les dépendances Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copier le reste du projet
COPY . .

# Créer le dossier pour le volume persistant
RUN mkdir -p /data

# Commande de démarrage
CMD ["python", "run.py"]
