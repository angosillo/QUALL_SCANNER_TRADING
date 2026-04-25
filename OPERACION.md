# MOMO Scanner — Guía de Operación

Guía paso a paso para poner en marcha, reiniciar y usar el dashboard web.
No se necesitan conocimientos técnicos.

---

## Antes de empezar — ¿Desde dónde se ejecuta?

El proyecto corre dentro de **WSL2 (Ubuntu)**, no directamente en Windows.

Para abrirlo hay dos formas:
- Buscar **"Ubuntu"** en el menú de inicio de Windows y abrirlo
- Abrir **PowerShell** y escribir `wsl` y pulsar Enter

A partir de ahí, todos los comandos de esta guía se escriben en esa ventana de Ubuntu (fondo negro con texto, como un terminal de Linux).

---

## 1. Iniciar el proyecto por primera vez

Solo hace falta hacerlo una vez cuando se instala en un equipo nuevo.

```bash
cd /mnt/c/PLATZI/QUALL_SCANNER_TRADING
pip install -e ".[web]"
PYTHONPATH=src python3 -m momo init
```

Esto instala las dependencias y crea la base de datos.

---

## 2. Iniciar el dashboard (uso diario)

Cada vez que se quiera usar el dashboard hay que arrancar el servidor.

**Paso 1** — Abrir Ubuntu (WSL2) desde el menú de inicio o escribir `wsl` en PowerShell.

**Paso 2** — Escribir este comando y pulsar Enter:

```bash
cd /mnt/c/PLATZI/QUALL_SCANNER_TRADING && PYTHONPATH=src python3 -m momo web --host 0.0.0.0 --port 8000
```

**Paso 3** — Esperar hasta que aparezca algo como:

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Cuando aparezca ese mensaje, el servidor está listo.

**Paso 4** — Abrir Chrome o Edge y entrar en la URL (ver sección 4).

> El servidor tiene que estar corriendo en todo momento mientras se usa el dashboard.
> Si se cierra la ventana de Ubuntu, el dashboard deja de funcionar.

---

## 3. Reiniciar el servidor

Necesario después de actualizar el código con `git pull`.

**Paso 1** — Ir a la ventana de Ubuntu donde está corriendo el servidor.

**Paso 2** — Pulsar `Ctrl + C` para detenerlo. Aparecerá el cursor de nuevo.

**Paso 3** — Volver a ejecutar el comando de inicio:

```bash
cd /mnt/c/PLATZI/QUALL_SCANNER_TRADING && PYTHONPATH=src python3 -m momo web --host 0.0.0.0 --port 8000
```

**Paso 4** — Cuando aparezca `Uvicorn running on...`, pulsar **F5** en el navegador.

---

## 4. Acceder al dashboard desde el navegador

### Si se usa en el mismo equipo (local):
```
http://localhost:8000
```

### Si se usa desde otro equipo en la red (servidor Hetzner):
```
http://<IP_DEL_SERVIDOR>:8000
```

Sustituir `<IP_DEL_SERVIDOR>` por la IP pública del servidor.
Ejemplo: `http://65.108.100.XXX:8000`

---

## 5. Actualizar el código (cuando haya cambios nuevos)

Cuando se notifique que hay una actualización disponible:

```bash
cd /mnt/c/PLATZI/QUALL_SCANNER_TRADING
git pull origin main
```

Después de hacer `git pull`, siempre reiniciar el servidor (ver sección 3).

---

## 6. Apagar el servidor

Ir a la ventana de Ubuntu donde corre el servidor y pulsar `Ctrl + C`.

---

## 7. Ejecutar los scans manualmente

Si los scans no tienen resultados o se quieren actualizar:

```bash
cd /mnt/c/PLATZI/QUALL_SCANNER_TRADING
PYTHONPATH=src python3 -m momo scan
```

También se puede hacer desde el propio dashboard pulsando el botón **"Re-ejecutar todos"** en la pantalla principal.

---

## 8. Solución de problemas frecuentes

### "El dashboard no carga" / pantalla en blanco
El servidor no está corriendo. Seguir los pasos de la sección 2.

### "Puerto 8000 ya en uso"
Ya hay un servidor corriendo. Buscar la ventana de Ubuntu con el proceso activo, o ejecutar:
```bash
pkill -f "momo web"
```
Y volver a iniciar.

### "No hay resultados en los scans"
Los datos de mercado no están descargados. Ejecutar:
```bash
cd /mnt/c/PLATZI/QUALL_SCANNER_TRADING
PYTHONPATH=src python3 -m momo download
PYTHONPATH=src python3 -m momo scan
```

### Los gráficos de TradingView no cargan
Problema de conexión a internet o bloqueador de contenido en el navegador.
Verificar que el servidor tiene acceso a internet y que no hay extensiones bloqueando scripts de `tradingview.com`.

### "Permission denied" al ejecutar comandos
```bash
chmod +x /mnt/c/PLATZI/QUALL_SCANNER_TRADING/start-web.sh
```

---

## Resumen rápido (chuleta)

| Acción | Comando |
|---|---|
| Iniciar servidor | `cd /mnt/c/PLATZI/QUALL_SCANNER_TRADING && PYTHONPATH=src python3 -m momo web --host 0.0.0.0 --port 8000` |
| Parar servidor | `Ctrl + C` en la ventana del servidor |
| Actualizar código | `cd /mnt/c/PLATZI/QUALL_SCANNER_TRADING && git pull origin main` |
| Ejecutar scans | `PYTHONPATH=src python3 -m momo scan` |
| URL local | `http://localhost:8000` |
| URL servidor | `http://<IP>:8000` |
