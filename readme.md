# 📁 Plateforme de Partage de Fichiers

Application web de partage de fichiers sécurisée avec espaces public et privé, développée en Python pur et déployée via Docker.

---

## 🚀 Lancement rapide

```bash
# Avec Docker
docker build -t file-sharing-app .
docker run -d -p 8080:8080 file-sharing-app

# Sans Docker
python server.py
```

Accéder à l'application : [http://localhost:8080](http://localhost:8080)

---

## ✨ Fonctionnalités

- 🔐 Inscription / Connexion avec sessions sécurisées (cookie HttpOnly, TTL 1h)
- 🌍 **Espace public** — fichiers accessibles à tous les utilisateurs connectés
- 🔒 **Espace privé** — fichiers visibles uniquement par leur propriétaire
- 📤 Upload en streaming par chunks de 8 Mo (supporte jusqu'à 10 Go)
- 📥 Téléchargement en streaming
- 🗑️ Suppression de fichiers

---

## 🛠️ Technologies

| Technologie | Usage |
|-------------|-------|
| Python 3 (stdlib) | Serveur HTTP, logique métier |
| http.server | Serveur HTTP natif |
| hashlib + secrets | SHA-256 + sel, tokens de session |
| JSON | Persistance des données |
| HTML / CSS / JS | Interface utilisateur |
| Docker | Conteneurisation et déploiement |

---

## 📂 Structure

```
projet/
├── server.py           # Serveur HTTP principal (routing, upload/download)
├── auth.py             # Authentification (login, register, logout)
├── database.py         # Persistance JSON (utilisateurs, sessions, fichiers)
├── config.py           # Configuration centralisée
├── index.html          # Page d'accueil
├── login.html          # Connexion / Inscription
├── dashboard.html      # Interface utilisateur connecté
├── Dockerfile          # Configuration Docker
├── public_uploads/     # Stockage fichiers publics
└── private_uploads/    # Stockage fichiers privés (un dossier par user)
```

---

## ⚙️ Configuration

Modifier `config.py` pour ajuster les paramètres :

```python
SERVER_PORT = 8080          # Port d'écoute
MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024  # Taille max (10 Go)
SESSION_TIMEOUT = 3600      # Durée de session (secondes)
ALLOWED_EXTENSIONS = []     # [] = tous les types autorisés
```

---

## 🔒 Sécurité

- Mots de passe hashés avec **SHA-256 + sel aléatoire**
- Sessions via **token URL-safe** (32 bytes) stocké en cookie HttpOnly
- Isolation des fichiers privés par utilisateur
- Expiration automatique des sessions

---

## 📋 Prérequis

- Python 3.7+
- Docker (optionnel)