# server.py
import http.server
import os
import json
import socket
import threading
import time
import zipfile
import io
import tempfile
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import config
import database as db
from auth import AuthHandler

# Initialiser les bases de données
db.init_database()

# Initialisation
config.init_directories()
auth = AuthHandler()

CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB chunks pour lecture/écriture


class UploadServer(http.server.BaseHTTPRequestHandler, AuthHandler):

    def log_message(self, format, *args):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        client_ip = self.client_address[0]
        print(f"[{timestamp}] [{client_ip}] {format % args}")

    def send_html(self, filename):
        try:
            with open(filename, 'rb') as f:
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(f.read())
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Page not found')

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _parse_multipart_header(self):
        """Extrait boundary depuis Content-Type"""
        ct = self.headers.get('Content-Type', '')
        boundary = None
        for part in ct.split(';'):
            part = part.strip()
            if part.startswith('boundary='):
                boundary = part[9:].strip('"')
                break
        return boundary

    def _stream_upload(self, dest_path, content_length):
        """Lit le corps multipart et écrit le fichier en streaming (chunk par chunk)"""
        boundary = self._parse_multipart_header()
        if not boundary:
            return False, "Boundary manquant"

        boundary_bytes = b'--' + boundary.encode()
        end_boundary = boundary_bytes + b'--'

        # Lire les en-têtes de la partie
        # Chercher le début des données fichier
        buf = b''
        header_done = False
        written = 0

        with open(dest_path, 'wb') as f_out:
            bytes_remaining = content_length
            # Phase 1 : trouver la fin des headers de part (\r\n\r\n)
            while bytes_remaining > 0 and not header_done:
                chunk = self.rfile.read(min(4096, bytes_remaining))
                if not chunk:
                    break
                bytes_remaining -= len(chunk)
                buf += chunk
                idx = buf.find(b'\r\n\r\n')
                if idx != -1:
                    buf = buf[idx + 4:]  # données après les headers
                    header_done = True

            if not header_done:
                return False, "En-têtes multipart introuvables"

            # Phase 2 : écrire les données en évitant le boundary de fin
            # On garde un buffer de tail pour détecter le boundary de fin
            tail_size = len(end_boundary) + 4  # marge

            while True:
                if bytes_remaining > 0:
                    chunk = self.rfile.read(min(CHUNK_SIZE, bytes_remaining))
                    if not chunk:
                        break
                    bytes_remaining -= len(chunk)
                    buf += chunk
                else:
                    # Plus rien à lire
                    break

                # Chercher le boundary de fin dans buf
                end_idx = buf.find(b'\r\n' + end_boundary)
                if end_idx != -1:
                    f_out.write(buf[:end_idx])
                    written += end_idx
                    buf = b''
                    break

                # Écrire ce qu'on peut (garder tail_size pour détection)
                if len(buf) > tail_size:
                    safe = len(buf) - tail_size
                    f_out.write(buf[:safe])
                    written += safe
                    buf = buf[safe:]

            # Vider le reste si pas de boundary trouvé
            if buf:
                # Essayer encore une fois de trouver le boundary
                end_idx = buf.find(b'\r\n' + boundary_bytes)
                if end_idx != -1:
                    f_out.write(buf[:end_idx])
                    written += end_idx
                else:
                    f_out.write(buf)
                    written += len(buf)

        return True, written

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path in ('/', '/index.html'):
            self.send_html('index.html')

        elif parsed.path == '/login':
            self.send_html('login.html')

        elif parsed.path == '/dashboard':
            username = auth.get_session_from_cookie(self.headers)
            if username:
                self.send_html('dashboard.html')
            else:
                self.send_response(302)
                self.send_header('Location', '/login')
                self.end_headers()

        elif parsed.path == '/api/user':
            username = auth.get_session_from_cookie(self.headers)
            if username:
                users_db = db.load_users_db()
                user_data = users_db['users'].get(username, {})
                self.send_json({
                    'success': True,
                    'username': username,
                    'files_count': user_data.get('files_count', 0),
                    'total_size': user_data.get('total_size', 0)
                })
            else:
                self.send_json({'success': False, 'message': 'Non connecté'}, 401)

        elif parsed.path == '/api/public-files':
            try:
                files = db.get_public_files()
                self.send_json(files)
            except Exception as e:
                print(f"Erreur get_public_files: {e}")
                self.send_json([])

        elif parsed.path == '/api/private-files':
            username = auth.get_session_from_cookie(self.headers)
            if username:
                try:
                    files = db.get_private_files(username)
                    self.send_json(files)
                except Exception as e:
                    print(f"Erreur get_private_files: {e}")
                    self.send_json([])
            else:
                self.send_json({'success': False, 'message': 'Non connecté'}, 401)

        elif parsed.path == '/download':
            params = parse_qs(parsed.query)
            filename = params.get('file', [None])[0]
            file_type = params.get('type', ['public'])[0]

            if not filename:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Missing filename')
                return

            if file_type == 'public':
                file_path = os.path.join(config.PUBLIC_DIR, filename)
            else:
                username = auth.get_session_from_cookie(self.headers)
                if not username:
                    self.send_response(401)
                    self.end_headers()
                    return
                file_path = os.path.join(config.PRIVATE_DIR, username, filename)

            if not os.path.exists(file_path):
                self.send_response(404)
                self.end_headers()
                self.wfile.write(f'Fichier introuvable: {filename}'.encode())
                return

            file_size = os.path.getsize(file_path)
            wip_threshold = config.WIP_THRESHOLD  # 2 GB

            try:
                if file_size > wip_threshold:
                    # --- WIP : compression à la volée en ZIP ---
                    print(f"🗜️  Fichier > 2 Go, compression WIP: {filename} ({file_size} octets)")
                    zip_name = os.path.splitext(filename)[0] + '.zip'

                    self.send_response(200)
                    self.send_header('Content-Type', 'application/zip')
                    self.send_header('Content-Disposition', f'attachment; filename="{zip_name}"')
                    self.send_header('Transfer-Encoding', 'chunked')
                    self.end_headers()

                    # Écrire le ZIP en streaming via un pipe mémoire
                    # On utilise un ZipFile sur un objet qui écrit directement vers wfile
                    class ChunkedWriter:
                        def __init__(self, wfile):
                            self.wfile = wfile

                        def write(self, data):
                            if data:
                                size_hex = format(len(data), 'x').encode() + b'\r\n'
                                self.wfile.write(size_hex)
                                self.wfile.write(data)
                                self.wfile.write(b'\r\n')
                            return len(data) if data else 0

                        def flush(self):
                            pass

                    writer = ChunkedWriter(self.wfile)

                    with zipfile.ZipFile(writer, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                        with open(file_path, 'rb') as src:
                            with zf.open(filename, 'w', force_zip64=True) as dest:
                                while True:
                                    chunk = src.read(CHUNK_SIZE)
                                    if not chunk:
                                        break
                                    dest.write(chunk)

                    # Fin du chunked transfer
                    self.wfile.write(b'0\r\n\r\n')
                    print(f"✅ WIP envoyé: {zip_name}")

                else:
                    # --- Téléchargement normal en streaming ---
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/octet-stream')
                    self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                    self.send_header('Content-Length', str(file_size))
                    self.end_headers()

                    with open(file_path, 'rb') as f:
                        while True:
                            chunk = f.read(CHUNK_SIZE)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                    print(f"✅ Fichier envoyé: {filename}")

            except Exception as e:
                print(f"❌ Erreur téléchargement: {e}")

        elif parsed.path == '/api/logout':
            auth.handle_logout(self)

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == '/api/login':
            auth.handle_login(self)

        elif parsed.path == '/api/register':
            auth.handle_register(self)

        elif parsed.path in ('/api/upload-public', '/api/upload-private'):
            is_public = parsed.path == '/api/upload-public'
            username = auth.get_session_from_cookie(self.headers)
            if not username:
                self.send_json({'success': False, 'message': 'Non connecté'}, 401)
                return

            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > config.MAX_FILE_SIZE:
                self.send_json({'success': False, 'message': config.MESSAGES['file_too_large']})
                return

            # Extraire le nom du fichier depuis Content-Disposition du header multipart
            # On lit juste les premiers octets pour récupérer le nom
            try:
                boundary = self._parse_multipart_header()
                if not boundary:
                    self.send_json({'success': False, 'message': 'Requête invalide'})
                    return

                # Lire le début pour trouver le filename
                peek = self.rfile.read(1024)
                # Remettre dans un buffer pour _stream_upload
                # On ne peut pas "unread", donc on reconstruit

                filename = None
                cd_idx = peek.find(b'Content-Disposition:')
                if cd_idx != -1:
                    cd_end = peek.find(b'\r\n', cd_idx)
                    cd_line = peek[cd_idx:cd_end].decode('utf-8', errors='replace')
                    for part in cd_line.split(';'):
                        part = part.strip()
                        if part.startswith('filename='):
                            filename = part[9:].strip('"').strip("'")
                            filename = os.path.basename(filename)

                if not filename:
                    self.send_json({'success': False, 'message': 'Nom de fichier manquant'})
                    return

                # Déterminer le dossier de destination
                if is_public:
                    dest_dir = config.PUBLIC_DIR
                else:
                    dest_dir = os.path.join(config.PRIVATE_DIR, username)

                os.makedirs(dest_dir, exist_ok=True)

                # Gestion des doublons
                base_filename = filename
                file_path = os.path.join(dest_dir, base_filename)
                counter = 1
                while os.path.exists(file_path):
                    name, ext = os.path.splitext(base_filename)
                    base_filename = f"{name}_{counter}{ext}"
                    file_path = os.path.join(dest_dir, base_filename)
                    counter += 1

                print(f"📤 Upload {'public' if is_public else 'privé'}: {base_filename} de {username} ({content_length} octets)")
                start_time = time.time()

                # Écriture streaming — on préfixe avec le peek déjà lu
                boundary_bytes = b'--' + boundary.encode()
                end_boundary_bytes = boundary_bytes + b'--'

                buf = peek
                header_done = False
                bytes_remaining = content_length - len(peek)
                written = 0
                tail_size = len(end_boundary_bytes) + 4

                with open(file_path, 'wb') as f_out:
                    # Phase 1: trouver fin des headers de part
                    while not header_done:
                        idx = buf.find(b'\r\n\r\n')
                        if idx != -1:
                            buf = buf[idx + 4:]
                            header_done = True
                        else:
                            if bytes_remaining <= 0:
                                break
                            chunk = self.rfile.read(min(4096, bytes_remaining))
                            if not chunk:
                                break
                            bytes_remaining -= len(chunk)
                            buf += chunk

                    if not header_done:
                        self.send_json({'success': False, 'message': 'En-têtes multipart invalides'})
                        return

                    # Phase 2: écrire en streaming
                    while True:
                        if bytes_remaining > 0:
                            chunk = self.rfile.read(min(CHUNK_SIZE, bytes_remaining))
                            if not chunk:
                                break
                            bytes_remaining -= len(chunk)
                            buf += chunk

                        end_idx = buf.find(b'\r\n' + end_boundary_bytes)
                        if end_idx != -1:
                            f_out.write(buf[:end_idx])
                            written += end_idx
                            buf = b''
                            break

                        if bytes_remaining <= 0:
                            # Dernier passage
                            end_idx2 = buf.find(b'\r\n' + boundary_bytes)
                            if end_idx2 != -1:
                                f_out.write(buf[:end_idx2])
                                written += end_idx2
                            else:
                                f_out.write(buf)
                                written += len(buf)
                            buf = b''
                            break

                        if len(buf) > tail_size:
                            safe = len(buf) - tail_size
                            f_out.write(buf[:safe])
                            written += safe
                            buf = buf[safe:]

                elapsed = time.time() - start_time
                file_size = os.path.getsize(file_path)
                speed_mb = (file_size / (1024 * 1024)) / max(elapsed, 0.1)
                print(f"✅ Upload terminé: {base_filename} ({file_size} octets) en {elapsed:.1f}s ({speed_mb:.1f} MB/s)")

                # Enregistrer en base
                file_id = db.get_next_id()
                if is_public:
                    db.add_public_file(base_filename, file_size, username, file_id)
                else:
                    db.add_private_file(username, base_filename, file_size, file_id)

                self.send_json({
                    'success': True,
                    'message': config.MESSAGES['upload_success'],
                    'filename': base_filename,
                    'size': file_size,
                    'elapsed': round(elapsed, 1)
                })

            except Exception as e:
                print(f"❌ Erreur upload: {e}")
                import traceback; traceback.print_exc()
                self.send_json({'success': False, 'message': str(e)})

        else:
            self.send_response(404)
            self.end_headers()


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'


if __name__ == '__main__':
    print("=" * 60)
    print("🔐 SERVEUR AVEC AUTHENTIFICATION UTILISATEUR")
    print("=" * 60)

    port = 8081
    server_address = (config.SERVER_HOST, port)

    # Augmenter la limite de timeout pour les gros fichiers
    http.server.HTTPServer.timeout = 0  # pas de timeout

    httpd = http.server.HTTPServer(server_address, UploadServer)

    local_ip = get_local_ip()
    print(f"\n🌐 Serveur démarré sur:")
    print(f"   • Local:  http://localhost:{port}")
    print(f"   • Réseau: http://{local_ip}:{port}")
    print(f"\n📦 Limites:")
    print(f"   • Taille max: 10 Go par fichier")
    print(f"   • Types: TOUS les formats acceptés")
    print(f"   • WIP automatique pour fichiers > 2 Go (téléchargement)")
    print(f"\n❌ CTRL+C pour arrêter\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Serveur arrêté")














# # Au début du fichier, assurez-vous d'avoir les imports
# import http.server
# import os
# import cgi
# import json
# import socket
# import threading
# import time
# from urllib.parse import urlparse, parse_qs
# from datetime import datetime
# import config
# import database as db
# from auth import AuthHandler

# # Initialiser les bases de données
# db.init_database()

# # Initialisation
# config.init_directories()
# auth = AuthHandler()

# class UploadServer(http.server.BaseHTTPRequestHandler, AuthHandler):
    
#     def log_message(self, format, *args):
#         """Log personnalisé"""
#         timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         client_ip = self.client_address[0]
#         print(f"[{timestamp}] [{client_ip}] {format % args}")
    
#     def send_html(self, filename):
#         """Envoie un fichier HTML"""
#         try:
#             with open(filename, 'rb') as f:
#                 self.send_response(200)
#                 self.send_header('Content-type', 'text/html; charset=utf-8')
#                 self.end_headers()
#                 self.wfile.write(f.read())
#         except FileNotFoundError:
#             self.send_response(404)
#             self.end_headers()
#             self.wfile.write(b'Page not found')
    
#     def send_json(self, data, status=200):
#         """Envoie une réponse JSON"""
#         self.send_response(status)
#         self.send_header('Content-type', 'application/json; charset=utf-8')
#         self.end_headers()
#         self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
#     def do_GET(self):
#         parsed = urlparse(self.path)
        
#         # Pages publiques
#         if parsed.path == '/' or parsed.path == '/index.html':
#             self.send_html('index.html')
        
#         elif parsed.path == '/login':
#             self.send_html('login.html')
        
#         elif parsed.path == '/dashboard':
#             username = auth.get_session_from_cookie(self.headers)
#             if username:
#                 self.send_html('dashboard.html')
#             else:
#                 self.send_response(302)
#                 self.send_header('Location', '/login')
#                 self.end_headers()
        
#         elif parsed.path == '/api/user':
#             username = auth.get_session_from_cookie(self.headers)
#             if username:
#                 users_db = db.load_users_db()
#                 user_data = users_db['users'].get(username, {})
#                 self.send_json({
#                     'success': True,
#                     'username': username,
#                     'files_count': user_data.get('files_count', 0),
#                     'total_size': user_data.get('total_size', 0)
#                 })
#             else:
#                 self.send_json({'success': False, 'message': 'Non connecte'}, 401)
        
#         elif parsed.path == '/api/public-files':
#             try:
#                 files = db.get_public_files()
#                 self.send_json(files)
#             except Exception as e:
#                 print(f"Erreur dans get_public_files: {e}")
#                 self.send_json([])
        
#         elif parsed.path == '/api/private-files':
#             username = auth.get_session_from_cookie(self.headers)
#             if username:
#                 try:
#                     files = db.get_private_files(username)
#                     self.send_json(files)
#                 except Exception as e:
#                     print(f"Erreur dans get_private_files: {e}")
#                     self.send_json([])
#             else:
#                 self.send_json({'success': False, 'message': 'Non connecte'}, 401)
        
#         elif parsed.path == '/download':
#             params = parse_qs(parsed.query)
#             filename = params.get('file', [None])[0]
#             file_type = params.get('type', ['public'])[0]
            
#             print(f"📥 Telechargement demande: {filename} (type: {file_type})")
            
#             if not filename:
#                 self.send_response(400)
#                 self.end_headers()
#                 self.wfile.write(b'Missing filename')
#                 return
            
#             if file_type == 'public':
#                 file_path = os.path.join(config.PUBLIC_DIR, filename)
#             else:
#                 username = auth.get_session_from_cookie(self.headers)
#                 if not username:
#                     self.send_response(401)
#                     self.end_headers()
#                     self.wfile.write(b'Unauthorized')
#                     return
#                 file_path = os.path.join(config.PRIVATE_DIR, username, filename)
            
#             if os.path.exists(file_path):
#                 try:
#                     file_size = os.path.getsize(file_path)
#                     self.send_response(200)
#                     self.send_header('Content-Type', 'application/octet-stream')
#                     self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
#                     self.send_header('Content-Length', str(file_size))
#                     self.end_headers()
                    
#                     with open(file_path, 'rb') as f:
#                         while True:
#                             chunk = f.read(8192)
#                             if not chunk:
#                                 break
#                             self.wfile.write(chunk)
                    
#                     print(f"✅ Fichier envoye: {filename}")
                    
#                 except Exception as e:
#                     print(f"❌ Erreur: {e}")
#                     self.send_response(500)
#                     self.end_headers()
#                     self.wfile.write(f'Error: {str(e)}'.encode())
#             else:
#                 print(f"❌ Fichier non trouve: {file_path}")
#                 self.send_response(404)
#                 self.end_headers()
#                 self.wfile.write(f'File not found: {filename}'.encode())
        
#         elif parsed.path == '/api/logout':
#             auth.handle_logout(self)
        
#         else:
#             self.send_response(404)
#             self.end_headers()
    
#     def do_POST(self):
#         parsed = urlparse(self.path)
        
#         if parsed.path == '/api/login':
#             auth.handle_login(self)
        
#         elif parsed.path == '/api/register':
#             auth.handle_register(self)
        
#         elif parsed.path == '/api/upload-public':
#             username = auth.get_session_from_cookie(self.headers)
#             if not username:
#                 self.send_json({'success': False, 'message': 'Non connecte'}, 401)
#                 return
            
#             try:
#                 form = cgi.FieldStorage(
#                     fp=self.rfile,
#                     headers=self.headers,
#                     environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': self.headers.get('Content-Type', '')}
#                 )
#                 file_item = form['file']
                
#                 if file_item.filename:
#                     filename = os.path.basename(file_item.filename)
#                     print(f"📤 Upload public: {filename} de {username}")
                    
#                     file_data = file_item.file.read()
#                     file_size = len(file_data)
                    
#                     if file_size > config.MAX_FILE_SIZE:
#                         self.send_json({'success': False, 'message': 'Fichier trop volumineux'})
#                         return
                    
#                     if not os.path.exists(config.PUBLIC_DIR):
#                         os.makedirs(config.PUBLIC_DIR)
                    
#                     file_path = os.path.join(config.PUBLIC_DIR, filename)
#                     counter = 1
#                     while os.path.exists(file_path):
#                         name, ext = os.path.splitext(filename)
#                         filename = f"{name}_{counter}{ext}"
#                         file_path = os.path.join(config.PUBLIC_DIR, filename)
#                         counter += 1
                    
#                     with open(file_path, 'wb') as f:
#                         f.write(file_data)
                    
#                     file_id = db.get_next_id()
#                     db.add_public_file(filename, file_size, username, file_id)
                    
#                     self.send_json({
#                         'success': True,
#                         'message': 'Fichier uploade avec succes',
#                         'filename': filename
#                     })
#                 else:
#                     self.send_json({'success': False, 'message': 'Aucun fichier'})
#             except Exception as e:
#                 print(f"❌ Erreur: {e}")
#                 self.send_json({'success': False, 'message': str(e)})
        
#         elif parsed.path == '/api/upload-private':
#             username = auth.get_session_from_cookie(self.headers)
#             if not username:
#                 self.send_json({'success': False, 'message': 'Non connecte'}, 401)
#                 return
            
#             try:
#                 form = cgi.FieldStorage(
#                     fp=self.rfile,
#                     headers=self.headers,
#                     environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': self.headers.get('Content-Type', '')}
#                 )
#                 file_item = form['file']
                
#                 if file_item.filename:
#                     filename = os.path.basename(file_item.filename)
#                     print(f"🔒 Upload prive: {filename} de {username}")
                    
#                     file_data = file_item.file.read()
#                     file_size = len(file_data)
                    
#                     if file_size > config.MAX_FILE_SIZE:
#                         self.send_json({'success': False, 'message': 'Fichier trop volumineux'})
#                         return
                    
#                     user_dir = os.path.join(config.PRIVATE_DIR, username)
#                     if not os.path.exists(user_dir):
#                         os.makedirs(user_dir)
                    
#                     file_path = os.path.join(user_dir, filename)
#                     counter = 1
#                     while os.path.exists(file_path):
#                         name, ext = os.path.splitext(filename)
#                         filename = f"{name}_{counter}{ext}"
#                         file_path = os.path.join(user_dir, filename)
#                         counter += 1
                    
#                     with open(file_path, 'wb') as f:
#                         f.write(file_data)
                    
#                     file_id = db.get_next_id()
#                     db.add_private_file(username, filename, file_size, file_id)
                    
#                     self.send_json({
#                         'success': True,
#                         'message': 'Fichier uploade avec succes',
#                         'filename': filename
#                     })
#                 else:
#                     self.send_json({'success': False, 'message': 'Aucun fichier'})
#             except Exception as e:
#                 print(f"❌ Erreur: {e}")
#                 self.send_json({'success': False, 'message': str(e)})
        
#         else:
#             self.send_response(404)
#             self.end_headers()

# def get_local_ip():
#     """Récupère l'IP locale"""
#     try:
#         s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         s.connect(("8.8.8.8", 80))
#         ip = s.getsockname()[0]
#         s.close()
#         return ip
#     except:
#         return '127.0.0.1'

# def check_port(port):
#     """Vérifie si un port est disponible"""
#     with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#         try:
#             s.bind(('0.0.0.0', port))
#             return True
#         except socket.error:
#             return False

# if __name__ == '__main__':
#     print("=" * 60)
#     print("🔐 SERVEUR AVEC AUTHENTIFICATION UTILISATEUR")
#     print("=" * 60)
    
#     # Utiliser le port 8081 pour éviter les conflits
#     port = 8081
    
#     # Démarrer le serveur
#     server_address = (config.SERVER_HOST, port)
#     httpd = http.server.HTTPServer(server_address, UploadServer)
    
#     local_ip = get_local_ip()
#     print(f"\n🌐 Serveur demarre sur:")
#     print(f"   • Local: http://localhost:{port}")
#     print(f"   • Reseau: http://{local_ip}:{port}")
#     print(f"\n👥 Fonctionnalites:")
#     print(f"   • 🔐 Connexion/Inscription")
#     print(f"   • 📁 Espace public (visible par tous)")
#     print(f"   • 🔒 Espace prive (visible seulement par vous)")
#     print(f"\n💡 Pour commencer:")
#     print(f"   1. Creez un compte sur /login")
#     print(f"   2. Connectez-vous")
#     print(f"   3. Uploader dans Public ou Prive")
#     print(f"\n❌ CTRL+C pour arreter\n")
    
#     try:
#         httpd.serve_forever()
#     except KeyboardInterrupt:
#         print("\n\n👋 Serveur arrete")