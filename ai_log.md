# Bitácora de IA · Laboratorio 3

**Fecha:** 24 de noviembre de 2026. **Asistente:** ChatGPT. **Alcance:** propuesta, revisión e implementación asistida de las cinco funciones de autenticación del kit v2.

## Solicitud de diseño

«Propón en Python, con la biblioteca estándar, cómo completar las cinco funciones de `api/auth.py` sin cambiar sus firmas. Usa PBKDF2-HMAC-SHA256 con sal, compara firmas y huellas en tiempo constante, limita el token a 15 minutos, bloquea tras cinco fallos consecutivos y registra solo correo, hora y resultado. Señala los casos límite y cómo verificarlos con la suite del laboratorio».

| Decisión | Criterio técnico y evidencia |
|---|---|
| Aceptado · PBKDF2-HMAC-SHA256 y sal aleatoria de 16 bytes | Se conserva el formato del andamio. La verificación usa `hmac.compare_digest`. La suite comprueba la persistencia del hash y el login con credenciales válidas. |
| Modificado · expiración configurable | Se acotó la configuración a un máximo de 900 segundos. La validación exige firma válida y revisa el vencimiento. La suite prueba una firma alterada y un token expirado. |
| Modificado · bloqueo y registro | Se comprueban los cinco intentos consecutivos recientes y se registra el resultado en una transacción SQLite. Un intento fallido queda registrado antes de devolver 401. La suite comprueba que el sexto intento recibe 429. |
| Rechazado · omitir el cálculo de huella para un correo inexistente | Se calcula una huella con un registro auxiliar y ambas rutas devuelven el mismo mensaje. La prueba oficial verifica cada 401 y la igualdad del mensaje. |
| Rechazado · guardar la contraseña o un secreto fijo en el código | La tabla de intentos guarda correo, hora y resultado, de acuerdo con ing-02. El secreto de firma se obtiene del entorno. Los errores esperados se entregan como `problem+json`, de acuerdo con ing-07. |

Se usó el proveedor simulado `fake` para reproducir el caso guía sin consumir cuota. Las cuentas y los datos de prueba son ficticios.
