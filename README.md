# Proyecto de grado AIREA

## Integrantes

- Jeffry Duarte
- María Paula Padilla
- Luna Hernández
- Duvan Rodríguez
- Valentina (colaboradora)

## Descripción

API FastAPI del sitio web AIREA para consulta de calidad del aire. La interfaz mantiene los endpoints `/api`; las cuentas, perfiles, sesiones e invitaciones se guardan en Supabase Postgres.

## Configurar Supabase

1. Crea un proyecto de Supabase y copia la cadena PostgreSQL desde **Project Settings > Database**.
2. Copia `.env.example` como `.env` junto a este README y configura `SUPABASE_DATABASE_URL`. No pongas la contraseña de la base en variables `VITE_`, no la subas a Git ni la compartas por chat.
3. Genera un secreto JWT criptográficamente aleatorio de al menos 32 bytes y guárdalo como `AIREA_JWT_SECRET` en el `.env`. Mantén este secreto privado y estable entre reinicios.
4. Instala dependencias e inicia la API. Al arrancar, Alembic aplica las migraciones, conserva los roles y hashes de cuentas existentes y activa Row Level Security. La conexión a la base ocurre solo en el backend.

`SUPABASE_DATABASE_URL` es obligatoria tanto en desarrollo como en producción; el backend no vuelve silenciosamente a SQLite. SQLite queda disponible solo para la migración única de datos y pruebas explícitamente habilitadas con `AIREA_TEST_MODE=1` y `AIREA_TEST_DATABASE_URL`.

## Administracion del sitio

Al iniciar, la API crea las tablas de avisos, ajustes de estaciones y umbrales en Supabase, con RLS habilitado y acceso de escritura solo desde el backend.

Para habilitar el panel:

1. Si la base no tiene una cuenta administradora, configura temporalmente un valor aleatorio y privado en `AIREA_ADMIN_SETUP_TOKEN` en el `.env` del backend.
2. Desde el modal de acceso del sitio, elige **Configurar administrador** e ingresa ese token para crear la primera cuenta. No compartas el token ni lo guardes en el frontend.
3. Borra el token del `.env` después de crear la cuenta. Las siguientes cuentas administrativas se crean desde **Admin > Invitaciones**; el código de un solo uso se debe compartir privadamente y vence en siete días.
4. Inicia sesión con la cuenta administradora y abre **Admin** en la barra superior.

El panel permite consultar y editar perfiles y roles de usuario, revocar invitaciones, redactar avisos públicos, cambiar el nombre/zona/visibilidad de estaciones y ajustar umbrales de avisos. Protege la última cuenta administradora y la última estación activa. Los cambios de estaciones no modifican coordenadas ni mediciones de fuentes externas; los umbrales solo afectan las opciones informativas de alerta y no reemplazan normas sanitarias.

## Herramientas y agradecimientos

Jeffry Duarte participó en la programación y documentación del proyecto junto con el equipo indicado en la sección de integrantes. GitHub Copilot se utilizó como herramienta de asistencia para apoyar estas tareas; las decisiones de diseño, revisión e integración del proyecto corresponden a sus integrantes.

## Migrar datos existentes

Antes de cambiar un despliegue que tenga cuentas, haz una copia de seguridad del archivo SQLite. Configura `SUPABASE_DATABASE_URL` en el `.env` ignorado por Git y ejecuta desde la raíz del workspace:

```powershell
python -m db.migrate_sqlite_to_supabase --source data/airea.sqlite
```

La migración copia cuentas (incluidos sus hashes de contraseña), perfiles, sesiones e invitaciones y conserva los roles en la tabla `roles`. Las cuentas Scrypt existentes se convierten a Bcrypt cuando inician sesión. No borres la copia SQLite hasta verificar el acceso a la base Supabase.

El endpoint `/login` (también disponible en `/api/auth/login`) autentica mediante Bcrypt y entrega un JWT HS256 en una cookie `HttpOnly`. Las rutas protegidas validan la firma y la sesión revocable contra la base de datos; el rol actual determina el acceso (401/403). Al pasar de las sesiones anteriores, las personas deberán iniciar sesión de nuevo.

## Instalar y ejecutar

Desde la raiz del workspace:

```powershell
Copy-Item .env.example .env
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Para aplicar las migraciones manualmente desde la raíz del repositorio:

```powershell
python -m alembic -c alembic.ini upgrade head
```

En Windows PowerShell, genera el secreto JWT y agrégalo al `.env` con:

```powershell
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$bytes = New-Object byte[] 32
$rng.GetBytes($bytes)
$secret = [Convert]::ToBase64String($bytes)
Add-Content -Path ".env" -Value "AIREA_JWT_SECRET=$secret"
$rng.Dispose()
[Array]::Clear($bytes, 0, $bytes.Length)
Remove-Variable secret, bytes, rng
```
