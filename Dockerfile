FROM python:3.10-bullseye

WORKDIR /usr/src/app

# Copier requirements
COPY requirements.txt ./

# Mettre à jour pip
RUN pip install --upgrade pip

# Installer les dépendances système
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -qq -y --fix-missing --no-install-recommends \
    gcc \
    libffi-dev \
    rustc \
    zlib1g-dev \
    libjpeg-dev \
    libssl-dev \
    libblas-dev \
    liblapack-dev \
    make \
    cmake \
    automake \
    ninja-build \
    g++ \
    subversion \
    python3-dev

# Installer les dépendances Python
RUN pip install -r requirements.txt && pip cache purge

# Nettoyer
RUN apt-get remove -y gcc rustc && \
    apt-get autoremove -y && \
    apt-get autoclean -y && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /usr/share/doc/*

# ⭐ IMPORTANT : Copier TOUS les fichiers du projet
COPY . .

# Commande de démarrage
CMD ["python", "run.py"]
