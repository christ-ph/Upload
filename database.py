# database.py
import json
import os
import hashlib
import secrets
import time
from datetime import datetime

def load_users_db():
    """Charge la base des utilisateurs"""
    if os.path.exists('users_database.json'):
        try:
            with open('users_database.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {'users': {}, 'sessions': {}}
    return {'users': {}, 'sessions': {}}

def save_users_db(db):
    """Sauvegarde la base des utilisateurs"""
    with open('users_database.json', 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def load_files_db():
    """Charge la base des fichiers avec structure par défaut"""
    if os.path.exists('files_database.json'):
        try:
            with open('files_database.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Vérifier et corriger la structure si nécessaire
                if 'public' not in data:
                    data['public'] = []
                if 'private' not in data:
                    data['private'] = {}
                if 'last_id' not in data:
                    data['last_id'] = 0
                return data
        except:
            # Structure par défaut
            return {'public': [], 'private': {}, 'last_id': 0}
    # Structure par défaut
    return {'public': [], 'private': {}, 'last_id': 0}

def save_files_db(db):
    """Sauvegarde la base des fichiers"""
    with open('files_database.json', 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def hash_password(password, salt=None):
    """Hash le mot de passe avec sel"""
    if salt is None:
        salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256((password + salt).encode())
    return salt, hash_obj.hexdigest()

def verify_password(password, salt, password_hash):
    """Vérifie le mot de passe"""
    _, check_hash = hash_password(password, salt)
    return check_hash == password_hash

def create_user(username, password):
    """Crée un nouvel utilisateur"""
    db = load_users_db()
    
    if username in db['users']:
        return False, "Nom d'utilisateur déjà existant"
    
    salt, password_hash = hash_password(password)
    db['users'][username] = {
        'password_hash': password_hash,
        'salt': salt,
        'created_at': time.time(),
        'created_at_str': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'last_login': None,
        'files_count': 0,
        'total_size': 0
    }
    
    save_users_db(db)
    
    # Créer le dossier privé de l'utilisateur
    private_folder = os.path.join('private_uploads', username)
    if not os.path.exists(private_folder):
        os.makedirs(private_folder)
    
    return True, "Utilisateur créé avec succès"

def authenticate_user(username, password):
    """Authentifie un utilisateur"""
    db = load_users_db()
    
    if username not in db['users']:
        return False, None
    
    user = db['users'][username]
    if verify_password(password, user['salt'], user['password_hash']):
        # Mettre à jour la date de dernière connexion
        user['last_login'] = time.time()
        user['last_login_str'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_users_db(db)
        
        # Créer un token de session
        token = secrets.token_urlsafe(32)
        if 'sessions' not in db:
            db['sessions'] = {}
        db['sessions'][token] = {
            'username': username,
            'expires': time.time() + 3600  # 1 heure
        }
        save_users_db(db)
        
        return True, token
    
    return False, None

def validate_session(token):
    """Valide un token de session"""
    if not token:
        return None
    
    db = load_users_db()
    
    if 'sessions' in db and token in db['sessions']:
        session = db['sessions'][token]
        if session['expires'] > time.time():
            return session['username']
        else:
            # Session expirée, la supprimer
            del db['sessions'][token]
            save_users_db(db)
    
    return None

def logout_user(token):
    """Déconnecte un utilisateur"""
    db = load_users_db()
    if 'sessions' in db and token in db['sessions']:
        del db['sessions'][token]
        save_users_db(db)
        return True
    return False

def add_public_file(filename, size, uploader, file_id):
    """Ajoute un fichier public à la base"""
    db = load_files_db()
    
    # S'assurer que la clé 'public' existe
    if 'public' not in db:
        db['public'] = []
    
    db['public'].append({
        'id': file_id,
        'filename': filename,
        'size': size,
        'uploader': uploader,
        'uploader_ip': uploader,
        'timestamp': time.time(),
        'datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'type': 'public'
    })
    
    save_files_db(db)
    return True

def add_private_file(username, filename, size, file_id):
    """Ajoute un fichier privé à la base"""
    db = load_files_db()
    
    # S'assurer que la clé 'private' existe
    if 'private' not in db:
        db['private'] = {}
    
    if username not in db['private']:
        db['private'][username] = []
    
    db['private'][username].append({
        'id': file_id,
        'filename': filename,
        'size': size,
        'timestamp': time.time(),
        'datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'type': 'private'
    })
    
    # Mettre à jour les stats utilisateur
    users_db = load_users_db()
    if username in users_db['users']:
        users_db['users'][username]['files_count'] = users_db['users'][username].get('files_count', 0) + 1
        users_db['users'][username]['total_size'] = users_db['users'][username].get('total_size', 0) + size
        save_users_db(users_db)
    
    save_files_db(db)
    return True

def get_public_files():
    """Récupère la liste des fichiers publics"""
    db = load_files_db()
    # S'assurer que la clé 'public' existe
    if 'public' not in db:
        db['public'] = []
        save_files_db(db)
        return []
    
    return sorted(db['public'], key=lambda x: x.get('timestamp', 0), reverse=True)

def get_private_files(username):
    """Récupère la liste des fichiers privés d'un utilisateur"""
    db = load_files_db()
    # S'assurer que la clé 'private' existe
    if 'private' not in db:
        db['private'] = {}
        save_files_db(db)
        return []
    
    if username in db['private']:
        return sorted(db['private'][username], key=lambda x: x.get('timestamp', 0), reverse=True)
    return []

def delete_file(file_id, username=None, file_type='public'):
    """Supprime un fichier"""
    db = load_files_db()
    
    if file_type == 'public':
        if 'public' in db:
            db['public'] = [f for f in db['public'] if f.get('id') != file_id]
    else:
        if 'private' in db and username in db['private']:
            db['private'][username] = [f for f in db['private'][username] if f.get('id') != file_id]
    
    save_files_db(db)
    return True

def get_next_id():
    """Génère le prochain ID"""
    db = load_files_db()
    # S'assurer que la clé 'last_id' existe
    if 'last_id' not in db:
        db['last_id'] = 0
    db['last_id'] += 1
    save_files_db(db)
    return db['last_id']

def init_database():
    """Initialise les fichiers de base de données s'ils n'existent pas"""
    # Initialiser files_database.json
    if not os.path.exists('files_database.json'):
        default_files_db = {'public': [], 'private': {}, 'last_id': 0}
        save_files_db(default_files_db)
        print("✅ Base de données des fichiers initialisée")
    
    # Initialiser users_database.json
    if not os.path.exists('users_database.json'):
        default_users_db = {'users': {}, 'sessions': {}}
        save_users_db(default_users_db)
        print("✅ Base de données des utilisateurs initialisée")



















# # database.py
# import json
# import os
# import hashlib
# import secrets
# import time
# from datetime import datetime

# def load_users_db():
#     """Charge la base des utilisateurs"""
#     if os.path.exists('users_database.json'):
#         try:
#             with open('users_database.json', 'r', encoding='utf-8') as f:
#                 return json.load(f)
#         except:
#             return {'users': {}, 'sessions': {}}
#     return {'users': {}, 'sessions': {}}

# def save_users_db(db):
#     """Sauvegarde la base des utilisateurs"""
#     with open('users_database.json', 'w', encoding='utf-8') as f:
#         json.dump(db, f, ensure_ascii=False, indent=2)

# def load_files_db():
#     """Charge la base des fichiers avec structure par défaut"""
#     if os.path.exists('files_database.json'):
#         try:
#             with open('files_database.json', 'r', encoding='utf-8') as f:
#                 data = json.load(f)
#                 # Vérifier et corriger la structure si nécessaire
#                 if 'public' not in data:
#                     data['public'] = []
#                 if 'private' not in data:
#                     data['private'] = {}
#                 if 'last_id' not in data:
#                     data['last_id'] = 0
#                 return data
#         except:
#             # Structure par défaut
#             return {'public': [], 'private': {}, 'last_id': 0}
#     # Structure par défaut
#     return {'public': [], 'private': {}, 'last_id': 0}

# def save_files_db(db):
#     """Sauvegarde la base des fichiers"""
#     with open('files_database.json', 'w', encoding='utf-8') as f:
#         json.dump(db, f, ensure_ascii=False, indent=2)

# def hash_password(password, salt=None):
#     """Hash le mot de passe avec sel"""
#     if salt is None:
#         salt = secrets.token_hex(16)
#     hash_obj = hashlib.sha256((password + salt).encode())
#     return salt, hash_obj.hexdigest()

# def verify_password(password, salt, password_hash):
#     """Vérifie le mot de passe"""
#     _, check_hash = hash_password(password, salt)
#     return check_hash == password_hash

# def create_user(username, password):
#     """Crée un nouvel utilisateur"""
#     db = load_users_db()
    
#     if username in db['users']:
#         return False, "Nom d'utilisateur déjà existant"
    
#     salt, password_hash = hash_password(password)
#     db['users'][username] = {
#         'password_hash': password_hash,
#         'salt': salt,
#         'created_at': time.time(),
#         'created_at_str': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#         'last_login': None,
#         'files_count': 0,
#         'total_size': 0
#     }
    
#     save_users_db(db)
    
#     # Créer le dossier privé de l'utilisateur
#     private_folder = os.path.join('private_uploads', username)
#     if not os.path.exists(private_folder):
#         os.makedirs(private_folder)
    
#     return True, "Utilisateur créé avec succès"

# def authenticate_user(username, password):
#     """Authentifie un utilisateur"""
#     db = load_users_db()
    
#     if username not in db['users']:
#         return False, None
    
#     user = db['users'][username]
#     if verify_password(password, user['salt'], user['password_hash']):
#         # Mettre à jour la date de dernière connexion
#         user['last_login'] = time.time()
#         user['last_login_str'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         save_users_db(db)
        
#         # Créer un token de session
#         token = secrets.token_urlsafe(32)
#         if 'sessions' not in db:
#             db['sessions'] = {}
#         db['sessions'][token] = {
#             'username': username,
#             'expires': time.time() + 3600  # 1 heure
#         }
#         save_users_db(db)
        
#         return True, token
    
#     return False, None

# def validate_session(token):
#     """Valide un token de session"""
#     if not token:
#         return None
    
#     db = load_users_db()
    
#     if 'sessions' in db and token in db['sessions']:
#         session = db['sessions'][token]
#         if session['expires'] > time.time():
#             return session['username']
#         else:
#             # Session expirée, la supprimer
#             del db['sessions'][token]
#             save_users_db(db)
    
#     return None

# def logout_user(token):
#     """Déconnecte un utilisateur"""
#     db = load_users_db()
#     if 'sessions' in db and token in db['sessions']:
#         del db['sessions'][token]
#         save_users_db(db)
#         return True
#     return False

# def add_public_file(filename, size, uploader, file_id):
#     """Ajoute un fichier public à la base"""
#     db = load_files_db()
    
#     # S'assurer que la clé 'public' existe
#     if 'public' not in db:
#         db['public'] = []
    
#     db['public'].append({
#         'id': file_id,
#         'filename': filename,
#         'size': size,
#         'uploader': uploader,
#         'uploader_ip': uploader,
#         'timestamp': time.time(),
#         'datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#         'type': 'public'
#     })
    
#     save_files_db(db)
#     return True

# def add_private_file(username, filename, size, file_id):
#     """Ajoute un fichier privé à la base"""
#     db = load_files_db()
    
#     # S'assurer que la clé 'private' existe
#     if 'private' not in db:
#         db['private'] = {}
    
#     if username not in db['private']:
#         db['private'][username] = []
    
#     db['private'][username].append({
#         'id': file_id,
#         'filename': filename,
#         'size': size,
#         'timestamp': time.time(),
#         'datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#         'type': 'private'
#     })
    
#     # Mettre à jour les stats utilisateur
#     users_db = load_users_db()
#     if username in users_db['users']:
#         users_db['users'][username]['files_count'] = users_db['users'][username].get('files_count', 0) + 1
#         users_db['users'][username]['total_size'] = users_db['users'][username].get('total_size', 0) + size
#         save_users_db(users_db)
    
#     save_files_db(db)
#     return True

# def get_public_files():
#     """Récupère la liste des fichiers publics"""
#     db = load_files_db()
#     # S'assurer que la clé 'public' existe
#     if 'public' not in db:
#         db['public'] = []
#         save_files_db(db)
#         return []
    
#     return sorted(db['public'], key=lambda x: x.get('timestamp', 0), reverse=True)

# def get_private_files(username):
#     """Récupère la liste des fichiers privés d'un utilisateur"""
#     db = load_files_db()
#     # S'assurer que la clé 'private' existe
#     if 'private' not in db:
#         db['private'] = {}
#         save_files_db(db)
#         return []
    
#     if username in db['private']:
#         return sorted(db['private'][username], key=lambda x: x.get('timestamp', 0), reverse=True)
#     return []

# def delete_file(file_id, username=None, file_type='public'):
#     """Supprime un fichier"""
#     db = load_files_db()
    
#     if file_type == 'public':
#         if 'public' in db:
#             db['public'] = [f for f in db['public'] if f.get('id') != file_id]
#     else:
#         if 'private' in db and username in db['private']:
#             db['private'][username] = [f for f in db['private'][username] if f.get('id') != file_id]
    
#     save_files_db(db)
#     return True

# def get_next_id():
#     """Génère le prochain ID"""
#     db = load_files_db()
#     # S'assurer que la clé 'last_id' existe
#     if 'last_id' not in db:
#         db['last_id'] = 0
#     db['last_id'] += 1
#     save_files_db(db)
#     return db['last_id']

# def init_database():
#     """Initialise les fichiers de base de données s'ils n'existent pas"""
#     # Initialiser files_database.json
#     if not os.path.exists('files_database.json'):
#         default_files_db = {'public': [], 'private': {}, 'last_id': 0}
#         save_files_db(default_files_db)
#         print("✅ Base de données des fichiers initialisée")
    
#     # Initialiser users_database.json
#     if not os.path.exists('users_database.json'):
#         default_users_db = {'users': {}, 'sessions': {}}
#         save_users_db(default_users_db)
#         print("✅ Base de données des utilisateurs initialisée")