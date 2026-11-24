# Laboratorio 3 · Producto FinNorte

Entrega individual de Luis Alfonso Juárez Amaro (`Lolmastercraft`) para LSCA2318. Se implementa la autenticación del servicio y se verifica el caso guía del kit v2 con FastAPI, SQLite y Streamlit.

## Ejecución local

Requiere Python 3.10 o posterior. Desde la raíz, en un entorno virtual activo, instala las dependencias.

```text
python -m pip install -r requirements.txt
python -m pip install -e .
```

Copia `.env.example` a `.env`. Genera un secreto local con `python -c "import secrets; print(secrets.token_hex(32))"` y colócalo en `TOKEN_SECRET`. Para reproducir la demostración se usan `LLM_PROVIDER=fake` y `EMB_PROVIDER=hash`. Para usar Gemini, configura `LLM_PROVIDER=gemini` y `GEMINI_API_KEY` en ese mismo archivo local.

Ejecuta estos comandos en terminales separadas.

```text
python -m uvicorn api.producto:app
python -m streamlit run app/cliente_api.py
```

La documentación interactiva está en `http://127.0.0.1:8000/docs` y Streamlit en `http://localhost:8501`. Registra una cuenta de demostración, inicia sesión y, en `/docs`, pega solo el token en **Authorize**. Para el agente, usa el martes 24 de noviembre de 2026 con riesgo alto y compara la aprobación, el rechazo y el viernes 27.

```text
python -m pytest tests/test_lab_producto.py
```

La suite oficial cubre los errores `problem+json`, la autenticación y la confirmación en dos pasos del caso guía. Las decisiones de implementación están en [ai_log.md](ai_log.md).

Los módulos compartidos proceden del andamio del curso. Este repositorio público utiliza un documento original y ficticio para verificar que la búsqueda devuelve una fuente. El servicio y la interfaz proceden del [kit v2 A3+A4](https://github.com/CyberProf-tecmi/lsca2318-lab-a3-a4).
