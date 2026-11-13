# Instalación

## Requisitos

- **Node.js 22+** (librerías `ws` y `@simplewebauthn/server` para el Touch ID del admin).
- Para el admin: **python3** y **ffmpeg** (convertir audio/vídeo y volumen de las canciones; sin ffmpeg el Megamix se
  recorta igual si el audio es WAV, y las demos de `tools/demo-song.py` se generan en WAV).
- Un **dominio con HTTPS** para jugar con móviles (los navegadores solo dejan usar el micro en páginas seguras).

## En local (para desarrollar)

```bash
cd server
npm install
npm start                 # http://localhost:8877
npm test                  # pruebas del servidor (arranca uno aparte con datos temporales)
```

## Despliegue, copias y datos

- La versión sigue el esquema `1.AA.MMDD.HHMM` con la hora real del despliegue y se pone en todos los sitios de una
  vez con `python3 tools/version.py 1.26.1103.1102` (VERSION, insignia del README, página de la tele, `?v=` del
  móvil y nombre de la caché de su service worker). `deploy.sh` no despliega si no coinciden.

- `deploy/deploy.sh` comprueba la sintaxis, espera hasta 90 s a que nadie esté cantando (`DEPLOY_FORCE=1` lo salta),
  instala las dependencias en una copia (`server.new`) y solo entonces cambia de carpeta y reinicia: un fallo de `npm`
  nunca deja el servicio sin arrancar. Al parar, el servidor guarda las salas en `data/salas.json` y las restaura al
  arrancar, así que un despliegue no echa a nadie de su sala.
- Lo que hay que guardar: `data/` (récords, estadísticas, actividad, **llaves de Touch ID** en `admin.json`, novedades,
  versiones del editor, retiradas; `data/trabajos` es prescindible) y `web/songs` (las canciones con sus portadas,
  Megamix y volumen igualado). En el servidor de producción hay una copia diaria a las 04:10 en
  `/root/backups/gramola/` (`datos-AAAA-MM-DD.tgz`, 14 días, y una réplica de `web/songs`), hecha por
  `/root/backups/gramola/backup.sh`. El admin (Servidor → Descargar copia) baja récords, estadísticas, actividad,
  novedades y llaves.
- Un fichero de datos que no sea JSON válido no se pisa en silencio: el servidor lo aparta como
  `*.corrupto-<fecha>` y lo dice en el registro (`journalctl -u gramola`).
```
```

Variables de entorno:

| Variable | Por defecto | Uso |
|---|---|---|
| `PORT` | `8877` | Puerto de escucha. |
| `HOST` | `127.0.0.1` | Interfaz. Usa `0.0.0.0` para entrar desde otros equipos de la red. |
| `WEB_DIR` | `../web` | Carpeta de la web. |
| `SONGS_DIR` | `$WEB_DIR/songs` | Carpeta de canciones. |
| `SERVE_STATIC` | `1` | Con `0`, el servidor solo atiende `/api` y `/ws` (si los estáticos los sirve nginx). |
| `DATA_DIR` | `server/data` | Récords (`records.json`), estadísticas, actividad, llaves del admin y canciones retiradas. |
| `ADMIN_HOST` | — | Host del portal de administración. Sin ella, cualquier host que empiece por `admin.` (en local, `admin.localhost:8877`). |
| `TLS_CERT` | — | Ruta al certificado. Con `TLS_KEY`, el servidor atiende por **https** en vez de http. |
| `TLS_KEY` | — | Ruta a la clave privada del certificado. |
| `HTTP_PORT` | — | Solo con https activo: abre además un puerto **http** en el mismo proceso (`0` lo desactiva). Sirve para que la tele entre sin aviso de certificado y siga compartiendo sala con los móviles. |

En `localhost` el micro funciona porque los navegadores lo tratan como seguro. Lo normal es instalarlo como app
(icono de instalar de la barra de direcciones), pero tampoco hace falta: en una página segura la pantalla de instalar
ofrece **«Seguir sin instalar»** y el micro funciona igual en una pestaña. Si la página **no** es segura, el botón no
aparece: sin contexto seguro el navegador no concede el micrófono y la pantalla de instalar pasa a explicar cómo
instalar el certificado.

### Micro en móviles de la red local (sin dominio ni internet)

El micrófono solo se concede en **contexto seguro**, así que con una IP (`http://192.168.1.50:8877`) los móviles entran
pero no pueden cantar. Para una LAN sin dominio hace falta un certificado propio:

```bash
# 1. Una CA local y un certificado para la IP del portátil (sustituye la IP)
openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes -keyout ca.key -out ca.crt \
  -subj "/CN=Gramola Local CA" -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign"
openssl req -newkey rsa:2048 -nodes -keyout srv.key -out srv.csr -subj "/CN=192.168.1.50"
printf "subjectAltName=IP:192.168.1.50,IP:127.0.0.1,DNS:localhost\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n" > san.cnf
openssl x509 -req -in srv.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out srv.crt -days 825 -sha256 -extfile san.cnf

# 2. Arrancar en https (el QR de la tele apunta solo a https)
HOST=0.0.0.0 PORT=8878 TLS_CERT=$PWD/srv.crt TLS_KEY=$PWD/srv.key npm start
```

Hay que instalar `ca.crt` en cada móvil (Android: Ajustes → Seguridad → Cifrado y credenciales → Instalar certificado
→ Certificado de CA; iPhone: instalar el perfil y activarlo en Ajustes → General → Información → Ajustes de confianza
de certificados). Sin la CA el navegador avisa en cada visita, no deja instalar la app y no da contexto seguro, así que
tampoco deja encender el micro.

Para no pelearse con el móvil, el servidor publica la CA en **`/ca.crt`** y la propia app enlaza ahí. Como en la tele
ya hay un puerto http, el enlace de descarga apunta a ese puerto (`GET /api/mic-config` devuelve `caUrl`), de modo que
el móvil se baja el certificado **sin aviso**: `http://IP-DEL-PORTATIL:8877/ca.crt`.

#### La tele, sin avisos de certificado

La tele no necesita el certificado: se abre la tele por **http** y solo los móviles entran por https. Con `HTTP_PORT`
el mismo proceso atiende los dos puertos, así que la sala y los jugadores se comparten:

```bash
HOST=0.0.0.0 PORT=8878 HTTP_PORT=8877 \
  TLS_CERT=$PWD/srv.crt TLS_KEY=$PWD/srv.key npm start
```

Como en la tele `location.origin` es http, el QR saldría inseguro; por eso se le pasa la dirección del micro a mano:

```
http://IP-DEL-PORTATIL:8877/app/?micro=https%3A%2F%2FIP-DEL-PORTATIL%3A8878%2Fm%2Findex.html
```

El QR y el texto «o entra en…» usan ese valor, así que los móviles siguen cayendo en el https.

## En un servidor

### 1. Ficheros

```bash
sudo mkdir -p /var/www/vhosts/DOMINIO/app
sudo rsync -a server web /var/www/vhosts/DOMINIO/app/
cd /var/www/vhosts/DOMINIO/app/server && sudo -u USUARIO npm ci --omit=dev
```

### 2. Servicio systemd

Copia `deploy/gramola.service` a `/etc/systemd/system/`, cambia `USUARIO` y `DOMINIO`, crea la carpeta de datos
(`app/data`, donde se guardan los récords) y:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gramola
curl -s http://127.0.0.1:8877/api/health
```

### 3. Proxy con WebSocket

**Plesk con Apache**: pega `deploy/apache-gramola.conf` en *Configuración de Apache y nginx → Directivas adicionales
para HTTPS* (necesita `mod_proxy_wstunnel`). **nginx**: `proxy_pass` a `127.0.0.1:8877` con las cabeceras `Upgrade` y
`Connection "upgrade"` en `/ws`.

### 4. HTTPS y Cloudflare

- Certificado Let's Encrypt para el dominio (y `www`).
- Con Cloudflare en modo proxy los WebSocket funcionan sin cambios (el servidor envía pings cada 25 s).
  Si el modo SSL es «Full (strict)», emite el certificado con el registro en «solo DNS» y activa el proxy después.

### 5. Canciones

Sube las carpetas UltraStar a `SONGS_DIR` (por SFTP). Aparecen en menos de 5 s, sin reiniciar nada.

### 6. Diseño

Si cambia el diseño de la tele: copia la exportación nueva en `diseno/` y ejecuta `python3 tools/build-tv.py`.
