"""Autenticación del servicio (Laboratorio A3+A4 · caso guía).

Registro, login y token, sin librerías externas. Requisitos mínimos de la A3:
  1. Contraseñas con hash y sal (PBKDF2-HMAC-SHA256), nunca texto plano ni MD5.
  2. Token con expiración de 15 minutos o menos.
  3. El MISMO mensaje para usuario inexistente y contraseña incorrecta.
  4. Comparación en tiempo constante (hmac.compare_digest).
  5. Bloqueo temporal tras intentos fallidos.
  6. La bitácora de intentos NO guarda la contraseña.

Las cinco funciones del laboratorio se completaron con revisión asistida.
El secreto para firmar tokens se lee de TOKEN_SECRET en .env (nunca en el código).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field
from threading import RLock

ITERACIONES = 200_000
VIGENCIA_S = max(1, min(15 * 60, int(os.getenv("TOKEN_VIGENCIA_S", "900"))))
MAX_FALLOS, VENTANA_FALLOS_S = 5, 15 * 60
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MENSAJE_CREDENCIALES = "Correo o contraseña incorrectos"


def _secreto() -> bytes:
    s = os.getenv("TOKEN_SECRET", "")
    if len(s) < 32:
        raise RuntimeError("Define TOKEN_SECRET en .env con al menos 32 caracteres (python -c \"import secrets;print(secrets.token_hex(32))\")")
    return s.encode()


class ErrorAuth(Exception):
    def __init__(self, status: int, mensaje: str):
        super().__init__(mensaje)
        self.status = status


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_contrasena(contrasena: str, sal: bytes | None = None) -> str:
    """Devuelve el algoritmo, las iteraciones y la sal y huella en base64url."""
    if sal is None:
        sal = os.urandom(16)
    if len(sal) != 16:
        raise ValueError("La sal debe tener 16 bytes")
    huella = hashlib.pbkdf2_hmac("sha256", contrasena.encode(), sal, ITERACIONES)
    return f"pbkdf2${ITERACIONES}${_b64(sal)}${_b64(huella)}"


def verificar_contrasena(contrasena: str, guardado: str) -> bool:
    """Recalcula el hash con la misma sal y compara en TIEMPO CONSTANTE."""
    try:
        algoritmo, vueltas, sal_b64, huella_b64 = guardado.split("$")
        iteraciones = int(vueltas)
        sal, huella = _unb64(sal_b64), _unb64(huella_b64)
        if algoritmo != "pbkdf2" or not 1 <= iteraciones <= 1_000_000:
            return False
        if len(sal) != 16 or len(huella) != hashlib.sha256().digest_size:
            return False
        calculada = hashlib.pbkdf2_hmac("sha256", contrasena.encode(), sal, iteraciones)
        return hmac.compare_digest(calculada, huella)
    except (ValueError, AttributeError):
        return False


def emitir_token(usuario: str, ahora: float | None = None) -> str:
    """Token 'payload.firma': payload = {sub, iat, exp} en base64url; firma = HMAC-SHA256 con TOKEN_SECRET."""
    iat = int(time.time() if ahora is None else ahora)
    datos = {"sub": usuario, "iat": iat, "exp": iat + VIGENCIA_S}
    payload = _b64(json.dumps(datos, separators=(",", ":")).encode())
    firma = _b64(hmac.digest(_secreto(), payload.encode("ascii"), "sha256"))
    return f"{payload}.{firma}"


def validar_token(token: str, ahora: float | None = None) -> str:
    """Devuelve el usuario si el token es válido; si no, ErrorAuth(401). Revisa formato, firma y expiración."""
    ahora = time.time() if ahora is None else ahora
    try:
        payload, firma = token.split(".")
        firma_esperada = _b64(hmac.digest(_secreto(), payload.encode("ascii"), "sha256"))
        if not hmac.compare_digest(firma.encode("ascii"), firma_esperada.encode("ascii")):
            raise ValueError("Firma inválida")
        datos = json.loads(_unb64(payload))
        if not isinstance(datos, dict) or set(datos) != {"sub", "iat", "exp"}:
            raise ValueError("Campos inválidos")
        usuario, iat, exp = datos["sub"], datos["iat"], datos["exp"]
        if not isinstance(usuario, str) or not EMAIL.fullmatch(usuario):
            raise ValueError("Usuario inválido")
        if type(iat) is not int or type(exp) is not int or not 0 < exp - iat <= VIGENCIA_S:
            raise ValueError("Vigencia inválida")
        if iat > ahora:
            raise ValueError("Emisión futura")
    except (ValueError, AttributeError):
        raise ErrorAuth(401, "Token inválido") from None
    if ahora >= exp:
        raise ErrorAuth(401, "Token expirado")
    return usuario


@dataclass
class Autenticador:
    ruta_db: str = ":memory:"
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def __post_init__(self):
        self.db = sqlite3.connect(self.ruta_db, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS usuarios (email TEXT PRIMARY KEY, hash TEXT NOT NULL)")
        # Bitácora de intentos: correo, hora y resultado. NUNCA la contraseña.
        self.db.execute("CREATE TABLE IF NOT EXISTS intentos (email TEXT, ts REAL, ok INTEGER)")
        self.db.execute("CREATE INDEX IF NOT EXISTS intentos_email_ts ON intentos (email, ts)")
        self._hash_dummy = hash_contrasena("solo-para-igualar-el-trabajo")

    def registrar(self, email: str, contrasena: str) -> None:
        email = email.strip().lower()
        if not EMAIL.match(email):
            raise ErrorAuth(422, "Correo inválido")
        if len(contrasena) < 8:
            raise ErrorAuth(422, "La contraseña debe tener al menos 8 caracteres")
        try:
            with self._lock, self.db:
                self.db.execute("INSERT INTO usuarios VALUES (?, ?)", (email, hash_contrasena(contrasena)))
        except sqlite3.IntegrityError:
            raise ErrorAuth(409, "El correo ya está registrado")

    def login(self, email: str, contrasena: str, ahora: float | None = None) -> str:
        email = email.strip().lower()
        ahora = time.time() if ahora is None else ahora
        with self._lock, self.db:
            self.db.execute("BEGIN IMMEDIATE")
            recientes = self.db.execute(
                "SELECT ok FROM intentos WHERE email = ? AND ts > ? AND ts <= ? "
                "ORDER BY ts DESC, rowid DESC LIMIT ?",
                (email, ahora - VENTANA_FALLOS_S, ahora, MAX_FALLOS),
            ).fetchall()
            if len(recientes) == MAX_FALLOS and not any(ok for (ok,) in recientes):
                raise ErrorAuth(429, "Bloqueo temporal por intentos fallidos")
            cuenta = self.db.execute("SELECT hash FROM usuarios WHERE email = ?", (email,)).fetchone()
            verificada = verificar_contrasena(contrasena, cuenta[0] if cuenta else self._hash_dummy)
            ok = cuenta is not None and verificada
            token = emitir_token(email, ahora) if ok else None
            self.db.execute("INSERT INTO intentos (email, ts, ok) VALUES (?, ?, ?)", (email, ahora, int(ok)))
        if token is None:
            raise ErrorAuth(401, MENSAJE_CREDENCIALES)
        return token
