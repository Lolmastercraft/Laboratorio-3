"""Toma las capturas de Streamlit de la entrega usando una cuenta ficticia."""
from __future__ import annotations

import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path

import requests
from playwright.sync_api import expect, sync_playwright


API_URL = "http://127.0.0.1:8000"
APP_URL = "http://127.0.0.1:8501"
TAREA = "Quiero desplegar un cambio de riesgo alto en pagos-api el 2026-11-24. Si se puede, crea el ticket."


def esperar(url: str) -> None:
    for intento in range(120):
        try:
            if requests.get(url, timeout=1).ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.25)
    raise RuntimeError(f"No respondió el servicio local {url}")


def detener(proceso: subprocess.Popen) -> None:
    if proceso.poll() is None:
        proceso.terminate()
    proceso.wait(timeout=10)


def main(destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporal, ExitStack() as sesiones:
        env = dict(os.environ, LLM_PROVIDER="fake", EMB_PROVIDER="hash", API_URL=API_URL,
                   AUTH_DB=str(Path(temporal) / "usuarios.db"), TOKEN_SECRET=secrets.token_hex(32))
        api = subprocess.Popen([sys.executable, "-m", "uvicorn", "api.producto:app"], env=env)
        sesiones.callback(detener, api)
        esperar(f"{API_URL}/salud")
        interfaz = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "app/cliente_api.py", "--server.headless=true",
             "--server.address=127.0.0.1", "--browser.gatherUsageStats=false"], env=env,
        )
        sesiones.callback(detener, interfaz)
        esperar(f"{APP_URL}/_stcore/health")

        correo, contrasena = "captura@example.com", secrets.token_urlsafe(14)
        requests.post(f"{API_URL}/auth/registro", json={"email": correo, "contrasena": contrasena},
                      timeout=5).raise_for_status()
        with sync_playwright() as navegador:
            browser = navegador.chromium.launch()
            pagina = browser.new_page(viewport={"width": 1160, "height": 860}, device_scale_factor=1)
            pagina.goto(APP_URL, wait_until="domcontentloaded")
            pagina.get_by_label("Correo", exact=True).fill(correo)
            pagina.get_by_label("Contraseña", exact=True).fill(contrasena)
            pagina.get_by_role("button", name="Entrar", exact=True).click()
            expect(pagina.get_by_role("button", name="Cerrar sesión")).to_be_visible()
            pagina.get_by_text("Agente", exact=True).click()
            pagina.get_by_label("Tarea", exact=True).fill(TAREA)
            pagina.get_by_role("button", name="Ejecutar agente").click()

            expect(pagina.get_by_text("Acción pendiente:", exact=False).first).to_be_visible()
            pagina.get_by_role("button", name=re.compile("Rechazar")).scroll_into_view_if_needed()
            pagina.screenshot(path=destino / "01-pendiente.png")
            pagina.get_by_role("button", name=re.compile("Rechazar")).click()
            rechazo = pagina.get_by_text(re.compile("Acción rechazada:"))
            expect(rechazo).to_be_visible()
            rechazo.scroll_into_view_if_needed()
            pagina.screenshot(path=destino / "02-rechazo.png")

            pagina.get_by_text("Preguntar (caso guía)", exact=True).click()
            pagina.get_by_label("Tu pregunta", exact=True).fill("¿Cada cuánto se rotan los secretos?")
            detener(api)
            pagina.get_by_role("button", name="Preguntar", exact=True).click()
            expect(pagina.get_by_text("Servicio no disponible", exact=False).first).to_be_visible()
            pagina.screenshot(path=destino / "03-servicio-apagado.png")
            browser.close()


if __name__ == "__main__":
    main(Path(sys.argv[1]))
