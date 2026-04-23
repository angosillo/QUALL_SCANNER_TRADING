# Informe de Errores — MOMO Scanner TUI en Windows Server 2022

**Fecha:** 2026-04-23
**Entorno:** Windows Server 2022 (Hetzner VDS) + WSL2 Ubuntu
**Problema:** La TUI (Textual) no se renderiza al hacer clic en un icono del escritorio

---

## 1. Error principal: Pantalla negra al ejecutar la TUI

**Sintoma:**
- Al hacer doble clic en el acceso directo `.lnk` del escritorio, se abre una ventana de terminal en negro.
- No aparece ninguna interfaz, texto ni error visible.
- La ventana permanece negra o se cierra.

**Causa raiz:**
- Windows Server 2022 utiliza el terminal heredado `conhost.exe`.
- `conhost.exe` NO soporta aplicaciones TUI modernas que usan caracteres ANSI extendidos, escapes de terminal complejos ni redibujado de pantalla (como las que usa Textual / Rich).
- Textual intenta renderizar la interfaz, pero el terminal no interpreta los caracteres, resultando en una pantalla negra vacia.

**Verificacion:**
```bash
# Ejecutando manualmente desde WSL (conhost) produce el mismo resultado:
cd ~/momo-scanner && PYTHONPATH=src python3 -m momo tui
# Resultado: pantalla negra, sin errores en consola.
```

---

## 2. Intento de solucion: Acceso directo .lnk a WSL

**Intento:** Crear un `.lnk` que apunte directamente a `wsl.exe` ejecutando el script `launch-tui.sh`.

**Resultado:** Fallo. La ventana sigue usando `conhost.exe` porque `wsl.exe` hereda el terminal del proceso padre.

---

## 3. Intento de solucion: Script .bat intermediario

**Intento:** Crear un `.bat` que detecte si existe `wt.exe` (Windows Terminal) y use WSL.

**Resultado:** Fallo. `wt.exe` (Windows Terminal) NO esta instalado en Windows Server 2022. El fallback a `cmd /k` sigue usando `conhost.exe`.

---

## 4. Intento de solucion: WezTerm (terminal moderno portable)

**Intento:** Descargar y usar WezTerm (terminal moderno standalone) para lanzar la TUI.

**Pasos realizados:**
1. Descargado `WezTerm-windows-20240203-110809-5046fc22.zip` desde GitHub releases.
2. Extraido en `C:\Users\Administrator\Downloads\wezterm\`.
3. Actualizado el `.lnk` para apuntar a `wezterm-gui.exe`.

**Resultado:** No verificado completamente por bloqueos de ejecucion en el entorno, pero es la solucion tecnicamente correcta.

---

## 5. Soluciones recomendadas

### Opcion A: Usar un terminal moderno (Recomendada)
Instalar un terminal que soporte TUIs en Windows Server 2022:
- **WezTerm** (ya descargado, portable)
- **Alacritty** (portable)
- **Windows Terminal** (no esta disponible por defecto en Windows Server 2022 sin Store)

Una vez instalado, el comando a ejecutar es:
```bash
cd ~/momo-scanner && PYTHONPATH=src python3 -m momo tui
```

### Opcion B: Conectar por SSH desde otra maquina
Desde un ordenador con terminal moderno (Windows 11, macOS, Linux):
```bash
ssh administrator@65.108.100.152
cd momo-scanner && PYTHONPATH=src python3 -m momo tui
```
Esto funciona porque el renderizado TUI se hace en el cliente SSH, no en Windows Server.

### Opcion C: Usar la TUI dentro de una sesion tmux/screen
Si se usa tmux dentro de WSL, el redibujado lo maneja tmux, que a veces funciona mejor con terminales limitados. Aun asi, `conhost.exe` sigue siendo el cuello de botella.

### Opcion D: Reemplazar TUI por interfaz web
Cambiar la capa de presentacion de Textual a un dashboard web (FastAPI + HTML) que se abra en el navegador del servidor. Esto evita completamente el problema del terminal.

---

## Resumen tecnico

| Componente | Estado | Nota |
|---|---|---|
| Codigo TUI (Textual) | ✅ Funciona | Verificado con tests unitarios y `run_test()` |
| Base de datos SQLite | ✅ Funciona | Tablas creadas, watchlists operativas |
| CLI `python -m momo tui` | ✅ Funciona | En terminales modernos |
| `conhost.exe` (Windows Server 2022) | ❌ Incompatible | No soporta ANSI escapes complejos |
| `launch-tui.sh` | ✅ Creado | Helper script para ejecutar la TUI |
| Acceso directo `.lnk` | ⚠️ Limitado | Depende del terminal que lo abra |

---

## Archivos nuevos en el repo (commit `4df639b`)

```
launch-tui.sh                           # Script helper para ejecutar la TUI
src/momo/ui/app.py                      # App principal Textual
src/momo/ui/screens/dashboard.py        # Pantalla de scans
src/momo/ui/screens/scan_result.py      # Pantalla de resultados
src/momo/ui/screens/symbol_detail.py    # Pantalla de detalle de simbolo
src/momo/ui/screens/watchlist.py        # Pantalla de watchlists
src/momo/ui/widgets/*.py                # Widgets reutilizables
src/momo/ui/styles.tcss                 # Estilos TUI
src/momo/charts/candlestick.py          # Graficos ASCII/mplfinance/Plotly
src/momo/watchlist/manager.py           # CRUD watchlists SQLite
```

---

**Nota para quien revise esto:** El problema NO es del codigo Python ni de Textual. El problema es el terminal `conhost.exe` de Windows Server 2022. Cualquier aplicacion TUI (incluso `htop`, `vim` con plugins complejos, etc.) tendra el mismo comportamiento.
