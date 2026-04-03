# auth.py
import http.server
import json
import os
from urllib.parse import urlparse, parse_qs
import database as db
import config

class AuthHandler:
    """Gestionnaire d'authentification pour le serveur"""
    
    def get_session_from_cookie(self, headers):
        """Récupère la session depuis le cookie"""
        cookies = headers.get('Cookie', '')
        if 'session_token=' in cookies:
            token = cookies.split('session_token=')[1].split(';')[0]
            return db.validate_session(token)
        return None
    
    def require_auth(self, handler, callback):
        """Vérifie l'authentification avant d'exécuter une action"""
        username = self.get_session_from_cookie(handler.headers)
        
        if username:
            return callback(username)
        else:
            handler.send_response(401)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(json.dumps({
                'success': False,
                'message': config.MESSAGES['unauthorized'],
                'redirect': '/login'
            }).encode())
            return False
    
    def handle_login(self, handler):
        """Gère la connexion"""
        content_length = int(handler.headers.get('Content-Length', 0))
        post_data = handler.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode())
            username = data.get('username')
            password = data.get('password')
            
            success, token = db.authenticate_user(username, password)
            
            if success:
                handler.send_response(200)
                handler.send_header('Content-type', 'application/json')
                handler.send_header('Set-Cookie', f'session_token={token}; Path=/; HttpOnly')
                handler.end_headers()
                handler.wfile.write(json.dumps({
                    'success': True,
                    'message': config.MESSAGES['login_success'],
                    'redirect': '/dashboard'
                }).encode())
            else:
                handler.send_response(401)
                handler.send_header('Content-type', 'application/json')
                handler.end_headers()
                handler.wfile.write(json.dumps({
                    'success': False,
                    'message': config.MESSAGES['login_failed']
                }).encode())
        except:
            handler.send_response(400)
            handler.end_headers()
    
    def handle_register(self, handler):
        """Gère l'inscription"""
        content_length = int(handler.headers.get('Content-Length', 0))
        post_data = handler.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode())
            username = data.get('username')
            password = data.get('password')
            
            if len(username) < 3:
                handler.send_response(400)
                handler.end_headers()
                handler.wfile.write(json.dumps({
                    'success': False,
                    'message': 'Nom d\'utilisateur trop court (min 3 caractères)'
                }).encode())
                return
            
            if len(password) < 4:
                handler.send_response(400)
                handler.end_headers()
                handler.wfile.write(json.dumps({
                    'success': False,
                    'message': 'Mot de passe trop court (min 4 caractères)'
                }).encode())
                return
            
            success, message = db.create_user(username, password)
            
            if success:
                handler.send_response(200)
                handler.send_header('Content-type', 'application/json')
                handler.end_headers()
                handler.wfile.write(json.dumps({
                    'success': True,
                    'message': message
                }).encode())
            else:
                handler.send_response(400)
                handler.end_headers()
                handler.wfile.write(json.dumps({
                    'success': False,
                    'message': message
                }).encode())
        except:
            handler.send_response(400)
            handler.end_headers()
    
    def handle_logout(self, handler):
        """Gère la déconnexion"""
        cookies = handler.headers.get('Cookie', '')
        if 'session_token=' in cookies:
            token = cookies.split('session_token=')[1].split(';')[0]
            db.logout_user(token)
        
        handler.send_response(200)
        handler.send_header('Set-Cookie', 'session_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT')
        handler.send_header('Content-type', 'application/json')
        handler.end_headers()
        handler.wfile.write(json.dumps({
            'success': True,
            'message': 'Déconnecté avec succès',
            'redirect': '/login'
        }).encode())







# # auth.py
# import http.server
# import json
# import os
# from urllib.parse import urlparse, parse_qs
# import database as db
# import config

# class AuthHandler:
#     """Gestionnaire d'authentification pour le serveur"""
    
#     def get_session_from_cookie(self, headers):
#         """Récupère la session depuis le cookie"""
#         cookies = headers.get('Cookie', '')
#         if 'session_token=' in cookies:
#             token = cookies.split('session_token=')[1].split(';')[0]
#             return db.validate_session(token)
#         return None
    
#     def require_auth(self, handler, callback):
#         """Vérifie l'authentification avant d'exécuter une action"""
#         username = self.get_session_from_cookie(handler.headers)
        
#         if username:
#             return callback(username)
#         else:
#             handler.send_response(401)
#             handler.send_header('Content-type', 'application/json')
#             handler.end_headers()
#             handler.wfile.write(json.dumps({
#                 'success': False,
#                 'message': config.MESSAGES['unauthorized'],
#                 'redirect': '/login'
#             }).encode())
#             return False
    
#     def handle_login(self, handler):
#         """Gère la connexion"""
#         content_length = int(handler.headers.get('Content-Length', 0))
#         post_data = handler.rfile.read(content_length)
        
#         try:
#             data = json.loads(post_data.decode())
#             username = data.get('username')
#             password = data.get('password')
            
#             success, token = db.authenticate_user(username, password)
            
#             if success:
#                 handler.send_response(200)
#                 handler.send_header('Content-type', 'application/json')
#                 handler.send_header('Set-Cookie', f'session_token={token}; Path=/; HttpOnly')
#                 handler.end_headers()
#                 handler.wfile.write(json.dumps({
#                     'success': True,
#                     'message': config.MESSAGES['login_success'],
#                     'redirect': '/dashboard'
#                 }).encode())
#             else:
#                 handler.send_response(401)
#                 handler.send_header('Content-type', 'application/json')
#                 handler.end_headers()
#                 handler.wfile.write(json.dumps({
#                     'success': False,
#                     'message': config.MESSAGES['login_failed']
#                 }).encode())
#         except:
#             handler.send_response(400)
#             handler.end_headers()
    
#     def handle_register(self, handler):
#         """Gère l'inscription"""
#         content_length = int(handler.headers.get('Content-Length', 0))
#         post_data = handler.rfile.read(content_length)
        
#         try:
#             data = json.loads(post_data.decode())
#             username = data.get('username')
#             password = data.get('password')
            
#             if len(username) < 3:
#                 handler.send_response(400)
#                 handler.end_headers()
#                 handler.wfile.write(json.dumps({
#                     'success': False,
#                     'message': 'Nom d\'utilisateur trop court (min 3 caractères)'
#                 }).encode())
#                 return
            
#             if len(password) < 4:
#                 handler.send_response(400)
#                 handler.end_headers()
#                 handler.wfile.write(json.dumps({
#                     'success': False,
#                     'message': 'Mot de passe trop court (min 4 caractères)'
#                 }).encode())
#                 return
            
#             success, message = db.create_user(username, password)
            
#             if success:
#                 handler.send_response(200)
#                 handler.send_header('Content-type', 'application/json')
#                 handler.end_headers()
#                 handler.wfile.write(json.dumps({
#                     'success': True,
#                     'message': message
#                 }).encode())
#             else:
#                 handler.send_response(400)
#                 handler.end_headers()
#                 handler.wfile.write(json.dumps({
#                     'success': False,
#                     'message': message
#                 }).encode())
#         except:
#             handler.send_response(400)
#             handler.end_headers()
    
#     def handle_logout(self, handler):
#         """Gère la déconnexion"""
#         cookies = handler.headers.get('Cookie', '')
#         if 'session_token=' in cookies:
#             token = cookies.split('session_token=')[1].split(';')[0]
#             db.logout_user(token)
        
#         handler.send_response(200)
#         handler.send_header('Set-Cookie', 'session_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT')
#         handler.send_header('Content-type', 'application/json')
#         handler.end_headers()
#         handler.wfile.write(json.dumps({
#             'success': True,
#             'message': 'Déconnecté avec succès',
#             'redirect': '/login'
#         }).encode())