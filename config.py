# config.py
import os

# Configuration du serveur
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080

# Dossiers de stockage
PUBLIC_DIR = 'public_uploads'
PRIVATE_DIR = 'private_uploads'
USERS_DB_FILE = 'users_database.json'
FILES_DB_FILE = 'files_database.json'

# Sécurité
SESSION_TIMEOUT = 3600  # 1 heure en secondes
MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB (pas de limite pratique)
ALLOWED_EXTENSIONS = []  # Vide = tous les types autorisés

# Seuil de compression WIP (2 Go)
WIP_THRESHOLD = 2 * 1024 * 1024 * 1024  # 2 GB

# Créer les dossiers nécessaires
def init_directories():
    """Crée les dossiers nécessaires"""
    for directory in [PUBLIC_DIR, PRIVATE_DIR]:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"📁 Dossier créé: {directory}")

# Messages
MESSAGES = {
    'login_success': '✅ Connexion réussie !',
    'login_failed': '❌ Nom d\'utilisateur ou mot de passe incorrect',
    'register_success': '✅ Compte créé avec succès ! Connectez-vous',
    'register_failed': '❌ Ce nom d\'utilisateur existe déjà',
    'upload_success': '✅ Fichier uploadé avec succès',
    'upload_failed': '❌ Erreur lors de l\'upload',
    'unauthorized': '❌ Non autorisé. Veuillez vous connecter',
    'file_too_large': '❌ Fichier trop volumineux (max 10GB)',
    'invalid_format': '❌ Format de fichier non autorisé'
}









# # config.py
# import os

# # Configuration du serveur
# SERVER_HOST = '0.0.0.0'
# SERVER_PORT = 8080

# # Dossiers de stockage
# PUBLIC_DIR = 'public_uploads'
# PRIVATE_DIR = 'private_uploads'
# USERS_DB_FILE = 'users_database.json'
# FILES_DB_FILE = 'files_database.json'

# # Sécurité
# SESSION_TIMEOUT = 3600  # 1 heure en secondes
# MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
# ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.txt', '.mp4', '.mp3', '.zip']

# # Créer les dossiers nécessaires
# def init_directories():
#     """Crée les dossiers nécessaires"""
#     for directory in [PUBLIC_DIR, PRIVATE_DIR]:
#         if not os.path.exists(directory):
#             os.makedirs(directory)
#             print(f"📁 Dossier créé: {directory}")

# # Messages
# MESSAGES = {
#     'login_success': '✅ Connexion réussie !',
#     'login_failed': '❌ Nom d\'utilisateur ou mot de passe incorrect',
#     'register_success': '✅ Compte créé avec succès ! Connectez-vous',
#     'register_failed': '❌ Ce nom d\'utilisateur existe déjà',
#     'upload_success': '✅ Fichier uploadé avec succès',
#     'upload_failed': '❌ Erreur lors de l\'upload',
#     'unauthorized': '❌ Non autorisé. Veuillez vous connecter',
#     'file_too_large': '❌ Fichier trop volumineux (max 100MB)',
#     'invalid_format': '❌ Format de fichier non autorisé'
# }