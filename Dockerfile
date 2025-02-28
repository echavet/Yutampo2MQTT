ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG C.UTF-8

# Installation des dépendances Alpine
RUN apk add --no-cache python3 py3-pip py3-requests py3-beautifulsoup4 py3-voluptuous

# Création d'un environnement virtuel Python pour gérer les packages pip
WORKDIR /app
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Copie du code source
COPY . /app

# Installation des dépendances Python dans l'environnement virtuel
RUN pip install --no-cache-dir -r requirements.txt

# Exécution du script principal
CMD ["python", "/app/main.py"]
