#!/usr/bin/env python3
"""
Sistema de Autenticação para Dashboards OpenClaw
Gerencia usuários, sessões e controle de acesso
"""

import json
import secrets
import hashlib
import base64
from datetime import datetime, timedelta
from pathlib import Path
import pytz

# Timezone Brasil
BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')

# Caminhos - usar diretório atual (onde o script está) para armazenar dados
AUTH_DIR = Path(__file__).parent / 'auth'
USERS_FILE = AUTH_DIR / 'users.json'
SESSIONS_FILE = AUTH_DIR / 'sessions.json'
AUTH_DIR.mkdir(parents=True, exist_ok=True)

# Configurações
SESSION_COOKIE_NAME = 'openclaw_session'
SESSION_EXPIRY_HOURS = 12
COOKIE_MAX_AGE = SESSION_EXPIRY_HOURS * 3600

def hash_password(password: str, salt: bytes = None) -> tuple:
    """Hash de senha usando PBKDF2 + SHA256"""
    if salt is None:
        salt = secrets.token_bytes(32)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return base64.b64encode(dk).decode('utf-8'), base64.b64encode(salt).decode('utf-8')

def verify_password(password: str, stored_hash: str, stored_salt: str) -> bool:
    """Verifica senha contra hash armazenado"""
    salt = base64.b64decode(stored_salt)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return base64.b64encode(dk).decode('utf-8') == stored_hash

class AuthManager:
    """Gerenciador de autenticação"""
    
    def __init__(self):
        self.users = self._load_users()
        self.sessions = self._load_sessions()
    
    def _load_users(self):
        if USERS_FILE.exists():
            try:
                with open(USERS_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_users(self):
        with open(USERS_FILE, 'w') as f:
            json.dump(self.users, f, indent=2)
    
    def _load_sessions(self):
        if SESSIONS_FILE.exists():
            try:
                with open(SESSIONS_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_sessions(self):
        with open(SESSIONS_FILE, 'w') as f:
            json.dump(self.sessions, f, indent=2)
    
    def create_user(self, username, password, role='viewer', full_name=''):
        """Cria novo usuário"""
        if username in self.users:
            return False, "Usuário já existe"
        
        pwd_hash, pwd_salt = hash_password(password)
        
        self.users[username] = {
            'password_hash': pwd_hash,
            'password_salt': pwd_salt,
            'role': role,
            'full_name': full_name,
            'created_at': datetime.now(BRAZIL_TZ).isoformat(),
            'last_login': None
        }
        self._save_users()
        return True, "Usuário criado com sucesso"
    
    def verify_password(self, username, password):
        """Verifica senha do usuário"""
        user = self.users.get(username)
        if not user:
            return False
        
        if verify_password(password, user['password_hash'], user['password_salt']):
            user['last_login'] = datetime.now(BRAZIL_TZ).isoformat()
            self._save_users()
            return True
        return False
    
    def create_session(self, username, ip_address=None):
        """Cria sessão para usuário"""
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(BRAZIL_TZ) + timedelta(hours=SESSION_EXPIRY_HOURS)
        
        self.sessions[session_token] = {
            'username': username,
            'ip_address': ip_address,
            'created_at': datetime.now(BRAZIL_TZ).isoformat(),
            'expires_at': expires_at.isoformat(),
            'user_agent': None
        }
        self._save_sessions()
        return session_token, expires_at
    
    def validate_session(self, session_token):
        """Valida sessão"""
        session = self.sessions.get(session_token)
        if not session:
            return None
        
        expires_at = datetime.fromisoformat(session['expires_at'])
        if datetime.now(BRAZIL_TZ) > expires_at:
            self.invalidate_session(session_token)
            return None
        
        username = session['username']
        if username not in self.users:
            self.invalidate_session(session_token)
            return None
        
        return {
            'username': username,
            'role': self.users[username]['role'],
            'full_name': self.users[username]['full_name'],
            'session_token': session_token
        }
    
    def invalidate_session(self, session_token):
        if session_token in self.sessions:
            del self.sessions[session_token]
            self._save_sessions()
    
    def cleanup_expired_sessions(self):
        now = datetime.now(BRAZIL_TZ)
        expired = [token for token, session in self.sessions.items()
                  if now > datetime.fromisoformat(session['expires_at'])]
        for token in expired:
            del self.sessions[token]
        if expired:
            self._save_sessions()
        return len(expired)
    
    def get_user_info(self, username):
        user = self.users.get(username)
        if user:
            return {
                'username': username,
                'role': user['role'],
                'full_name': user['full_name'],
                'created_at': user['created_at'],
                'last_login': user['last_login']
            }
        return None
    
    def list_users(self):
        return [{'username': u, **{k:v for k,v in d.items() if k not in ['password_hash', 'password_salt']}} 
                for u, d in self.users.items()]
    
    def change_password(self, username, old_password, new_password):
        if not self.verify_password(username, old_password):
            return False, "Senha atual incorreta"
        pwd_hash, pwd_salt = hash_password(new_password)
        self.users[username]['password_hash'] = pwd_hash
        self.users[username]['password_salt'] = pwd_salt
        self._save_users()
        return True, "Senha alterada com sucesso"
    
    def delete_user(self, username):
        if username in self.users:
            del self.users[username]
            to_delete = [token for token, session in self.sessions.items() 
                        if session['username'] == username]
            for token in to_delete:
                del self.sessions[token]
            self._save_users()
            return True, "Usuário removido"
        return False, "Usuário não encontrado"

_auth_manager = None

def get_auth_manager():
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager

def generate_session_cookie(session_token):
    from datetime import datetime, timedelta
    expires = datetime.now(BRAZIL_TZ) + timedelta(hours=SESSION_EXPIRY_HOURS)
    cookie = f"{SESSION_COOKIE_NAME}={session_token}; Path=/; HttpOnly; Max-Age={COOKIE_MAX_AGE}; SameSite=Strict"
    if False:  # Set True para HTTPS
        cookie += "; Secure"
    return cookie

def parse_session_cookie(cookie_header):
    if not cookie_header:
        return None
    for cookie in cookie_header.split(';'):
        cookie = cookie.strip()
        if cookie.startswith(f'{SESSION_COOKIE_NAME}='):
            return cookie.split('=', 1)[1]
    return None
