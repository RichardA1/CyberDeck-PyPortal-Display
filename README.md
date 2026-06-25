# CyberDeck PyPortal Display

A CircuitPython status display and WLED lighting controller for the [CyberDeck](https://github.com/) hub, running on an Adafruit PyPortal (320×240) or PyPortal Titano (480×320).

The display connects to the CyberDeck's private WiFi network and shows live system stats — CPU temp, memory, uptime, service health, and UPS battery — while a second tab lets you control WLED LED strips over MQTT via the hub's Mosquitto broker.

---

## Screenshots

```
┌─────────────────────────────────────────┐   ┌─────────────────────────────────────────┐
│ // CYBERDECK              14:33:07      │   │ // CYBERDECK              14:33:07      │
├──────────────┬──────────────────────────┤   ├──────────────┬──────────────────────────┤
│    STATUS    │           WLED           │   │    STATUS    │           WLED           │
├─────────────────────────────────────────┤   ├─────────────────────────────────────────┤
│ NETWORK                                 │   │ POWER                             ON    │
│ PRIVATE IP        192.168.4.1           │   │ BRIGHT                           178   │
│ DEVICES           3 connected           │   │ TARGET                      DECK-STRIP  │
│                                         │   │ PRESET                                  │
│ SYSTEM                                  │   │  NIGHTWATCH #1    CYBERPUNK #2          │
│ CPU TEMP          58.4C                 │   │  CAMPFIRE  #3    AURORA    #4           │
│ CPU LOAD          2.2%                  │   │ COLOR             0,255,153             │
│ MEMORY            12% used              │   ├─────────────────────────────────────────┤
│ UPTIME            2h 14m                │   │ PUB deck-strip → ps1                    │
│                                         │   └─────────────────────────────────────────┘
│ SERVICES                                │
│ hostapd           ACTIVE                │
│ nginx             ACTIVE                │
│ smbd              DOWN                  │
├─────────────────────────────────────────┤
│ BAT 90%  DISCHARGING                    │
└─────────────────────────────────────────┘
```

---

## Hardware Required

| Item | Link |
|---|---|
| Adafruit PyPortal (original) | https://www.adafruit.com/product/4116 |
| — or — PyPortal Titano | https://www.adafruit.com/product/4444 |
| Micro USB cable | (data-capable, not charge-only) |
| CyberDeck hub on local network | — |
| ESP8266 running WLED (optional) | https://kno.wled.ge/ |

---

## File Structure

```
CIRCUITPY/
├── code.py                 ← main program (this repo)
├── settings.toml           ← WiFi credentials (NOT committed to git)
└── lib/
    ├── adafruit_display_text/
    ├── adafruit_bitmap_font/
    ├── adafruit_requests/
    ├── adafruit_connection_manager/
    ├── adafruit_touchscreen/
    ├── neopixel.mpy
    └── adafruit_minimqtt/  ← required for WLED tab
```

---

## Setup

### 1 — Install CircuitPython

Download the latest CircuitPython 9.x `.uf2` for your board from [circuitpython.org](https://circuitpython.org/board/pyportal/) and drag it to the `BOOT` drive that appears when you double-tap the reset button.

### 2 — Install Libraries

Download the [Adafruit CircuitPython Library Bundle](https://circuitpython.org/libraries) matching your CircuitPython version. Copy the following folders/files into `CIRCUITPY/lib/`:

```
adafruit_display_text/
adafruit_bitmap_font/
adafruit_requests/
adafruit_connection_manager/
adafruit_touchscreen/
adafruit_minimqtt/
neopixel.mpy
```

> [!TIP]
> Use the [CircUp](https://learn.adafruit.com/keep-your-circuitpython-libraries-on-devices-up-to-date-with-circup) CLI tool to install and keep libraries updated automatically:
> ```
> pip install circup
> circup install adafruit_display_text adafruit_bitmap_font adafruit_requests adafruit_minimqtt adafruit_touchscreen neopixel
> ```

### 3 — Create `settings.toml`

Create a file named `settings.toml` in the **root** of your `CIRCUITPY` drive (not inside any folder). This keeps your WiFi credentials out of `code.py`:

```toml
CIRCUITPY_WIFI_SSID     = "CyberDeck-Private"
CIRCUITPY_WIFI_PASSWORD = "your-wpa2-password"
```

> [!WARNING]
> **Never commit `settings.toml` to a public repository.** Add it to your `.gitignore`:
> ```
> settings.toml
> ```

### 4 — Copy `code.py`

Copy `code.py` from this repo to the root of your `CIRCUITPY` drive, replacing the existing file. The PyPortal will reboot and start automatically.

---

## Configuration

All user-configurable values are grouped at the top of `code.py` under the `★ USER CONFIGURATION ★` section. You should not need to change anything outside that block.

---

### Hub Endpoints

```python
HUB_STATS_URL = "http://192.168.4.1/stats.json"     # ← CHANGE ME
HUB_UPS_URL   = "http://192.168.4.1/ups-status.json" # ← CHANGE ME
```

> [!NOTE]
> Change these if your CyberDeck hub is on a different IP address. The default `192.168.4.1` matches the standard CyberDeck private network configuration. If you have renamed your endpoints on the hub's nginx config, update the paths accordingly.

```python
REFRESH_SEC  = 15   # How often to auto-refresh the status screen (seconds)
RETRY_OFFLINE = 30  # How often to retry when the hub is unreachable (seconds)
```

---

### MQTT Broker

```python
MQTT_BROKER = "192.168.4.1"  # ← CHANGE ME
MQTT_PORT   = 1883            # ← CHANGE ME if non-standard
MQTT_USER   = ""              # ← CHANGE ME if your broker requires auth
MQTT_PASS   = ""              # ← CHANGE ME if your broker requires auth
```

> [!NOTE]
> `MQTT_BROKER` should be the IP of the machine running Mosquitto. On the standard CyberDeck setup this is the same as the hub IP (`192.168.4.1`). If you move the broker to a different machine on the network, update this value.
>
> If your Mosquitto instance has `allow_anonymous false` set in its config, fill in `MQTT_USER` and `MQTT_PASS` with the credentials you configured. Leave them as empty strings `""` for anonymous access (the default CyberDeck Mosquitto setup).

---

### WLED Device Topics

```python
WLED_DEVICES = {
    "DECK-STRIP"  : "wled/deck-strip",    # ← CHANGE ME
    "SHELF"       : "wled/shelf-lights",  # ← CHANGE ME
    "ALL"         : "wled/all",           # broadcast — keep as-is
}
```

> [!IMPORTANT]
> The **value** (e.g. `"wled/deck-strip"`) must match the **Device Topic** you configured in WLED's settings page under **Config → MQTT → Device topic**. The PyPortal publishes to `<device-topic>/api`.
>
> The **key** (e.g. `"DECK-STRIP"`) is just the label shown on the PyPortal screen — keep it short (≤10 characters) so it fits the display.
>
> `wled/all` is a special topic that all WLED devices subscribe to by default when MQTT is enabled. You do not need to configure anything in WLED for this to work. Keep it as `"wled/all"` unless you have changed the default WLED MQTT prefix.
>
> You can add or remove devices from this dictionary. The WLED tab will cycle through them in order when you tap the TARGET row. Only the first entry is shown by default on boot.

---

### WLED Presets

```python
WLED_PRESETS = {
    "NIGHTWATCH" : 1,   # ← CHANGE ME
    "CYBERPUNK"  : 2,   # ← CHANGE ME
    "CAMPFIRE"   : 3,   # ← CHANGE ME
    "AURORA"     : 4,   # ← CHANGE ME
}
```

> [!IMPORTANT]
> The **integer value** (e.g. `1`) must match the **Preset ID** in WLED's preset manager. To find your preset IDs, open the WLED web UI and go to the Presets panel — each preset shows its ID number.
>
> The **key** (e.g. `"NIGHTWATCH"`) is the label shown on the PyPortal. Keep it to 9 characters or fewer for clean display alignment.
>
> Exactly 4 presets are displayed in a 2×2 grid on the PyPortal screen. If you add more entries to this dict, only the first 4 will appear as buttons — the rest are still accessible by editing the code.

---

### WLED Accent Colors

```python
WLED_COLORS = [
    (255,  51,   0),   # Red-orange  ← CHANGE ME
    (255, 136,   0),   # Amber
    (255, 255,   0),   # Yellow
    (  0, 255, 153),   # Cyan-green
    (  0, 136, 255),   # Blue
    (204,   0, 255),   # Violet
]
```

> [!NOTE]
> These are RGB tuples sent alongside the preset in the MQTT payload as `"seg":[{"col":[[R,G,B]]}]`. In WLED, this sets **Color 1** for the active segment.
>
> **Important:** If a WLED preset was saved with its colors locked (the default when you save via the WLED UI), the preset's saved color will override this value and the swatch selection will have no visible effect. To make swatches effective, either save your WLED presets with "Use current colors" unchecked, or treat the swatches as a separate "one-shot color" control independent of presets.
>
> Exactly 6 color swatches are shown. You can change the RGB values to any color you want. Adding or removing entries beyond 6 will require adjusting the touch zone layout in the `handle_touch()` function.

---

### Display Target

```python
DISPLAY_TARGET = "pyportal"  # ← CHANGE ME to "titano" for PyPortal Titano
```

> [!NOTE]
> Set to `"titano"` if you are using the PyPortal Titano (480×320). This adjusts the display dimensions and font scaling. All layout calculations are based on this value, so make sure it matches your hardware.

---

### Optional: Bitmap Font

By default the code uses CircuitPython's built-in `terminalio.FONT`. To use a nicer monospace bitmap font:

1. Download `Hack-Regular-24.bdf` (or another `.bdf` font) from the [Adafruit CircuitPython fonts repo](https://github.com/adafruit/circuitpython-fonts)
2. Copy it to `CIRCUITPY/assets/fonts/Hack-Regular-24.bdf`
3. In `code.py`, comment out the `terminalio.FONT` line and uncomment:
   ```python
   FONT = bitmap_font.load_font("/assets/fonts/Hack-Regular-24.bdf")
   ```

> [!TIP]
> Bitmap fonts use more RAM. If you get `MemoryError` after switching fonts, try a smaller point size (e.g. `Hack-Regular-16.bdf`) or revert to `terminalio.FONT`.

---

## WLED Setup

For each ESP8266/ESP32 running WLED that you want to control:

1. Open the WLED web UI
2. Go to **Config → WiFi Setup** and connect to `CyberDeck-Private`
3. Go to **Config → MQTT** and configure:
   - **MQTT Broker:** `192.168.4.1`
   - **Port:** `1883`
   - **Device topic:** e.g. `wled/deck-strip` (must match your `WLED_DEVICES` entry in `code.py`)
   - Enable MQTT and save
4. Go to **Presets** and create your presets. Note the **ID number** of each preset — you'll enter these in `WLED_PRESETS` in `code.py`

> [!TIP]
> To test MQTT connectivity before using the PyPortal, use `mosquitto_pub` from any machine on the network:
> ```bash
> mosquitto_pub -h 192.168.4.1 -t wled/deck-strip/api -m '{"on":true,"bri":128,"ps":1}'
> ```
> If your strip responds, MQTT is wired up correctly.

---

## How It Works

### Status Tab

On boot the PyPortal connects to `CyberDeck-Private`, fetches `stats.json` and `ups-status.json` from the hub every `REFRESH_SEC` seconds, and updates the display. Tap anywhere on the status screen to trigger an immediate refresh.

The NeoPixel on the PyPortal board shows connection state:

| Color | Meaning |
|---|---|
| Amber (solid) | Fetching data |
| Green (pulse) | Data received successfully |
| Red (solid) | Hub unreachable — retrying every `RETRY_OFFLINE` seconds |

If the hub is offline the display shows `HUB OFFLINE — retrying…` and the last-known data is cleared.

### WLED Tab

Tap the **WLED** tab label to switch. The PyPortal connects to the MQTT broker on first switch and stays connected. Each interaction (power toggle, brightness nudge, preset tap, color swatch tap) immediately publishes a JSON payload to `<device-topic>/api`.

Touch zones on the WLED screen:

| Zone | Action |
|---|---|
| Right side of POWER row | Toggle on/off |
| Left half of BRIGHT row | Brightness −20 |
| Right half of BRIGHT row | Brightness +20 |
| TARGET row | Cycle to next device |
| Preset button | Select preset + publish |
| Color swatch area | Cycle color + publish |

The footer line shows the last published topic and preset ID, or an error if the broker is unreachable.

### MQTT Payload Format

```json
{
  "on": true,
  "bri": 178,
  "ps": 1,
  "seg": [{"col": [[0, 255, 153]]}]
}
```

- `on` — power state
- `bri` — brightness (0–255)
- `ps` — WLED preset ID
- `seg[0].col[0]` — Color 1 RGB (applied only if preset allows color override)

---

## Troubleshooting

**`ImportError: no module named 'adafruit_minimqtt'`**
The MQTT library is missing from `CIRCUITPY/lib/`. The WLED tab will be non-functional but the status tab will still work. Install the library as described in Setup step 2.

**Screen stays blank / shows only header**
Open a serial console (Mu editor or `screen /dev/ttyACM0 115200`) to see the boot log. The most common cause is a WiFi connection failure — double-check `settings.toml`.

**`MemoryError` on boot**
CircuitPython on the SAMD51 has ~256 KB of heap. Try reverting to `terminalio.FONT` if you are using a bitmap font, or reduce `WLED_DEVICES` / `WLED_PRESETS` dict sizes.

**WLED not responding to MQTT**
- Confirm the WLED device topic in WLED's config matches the value in `WLED_DEVICES` exactly (case-sensitive)
- Test with `mosquitto_pub` from the command line (see WLED Setup section above)
- Check that Mosquitto is running on the hub: `systemctl status mosquitto`

**Time shows `--:--:--`**
The PyPortal doesn't have an RTC battery. Time is read from `time.localtime()` which starts at the epoch on boot. For accurate time, add NTP sync via `adafruit_ntp` — not included here to keep memory usage low.

---

## Libraries Used

| Library | Purpose |
|---|---|
| `adafruit_display_text` | Text labels on the display |
| `adafruit_bitmap_font` | Optional .bdf font rendering |
| `adafruit_requests` | HTTP GET requests to hub endpoints |
| `adafruit_connection_manager` | Socket pool management |
| `adafruit_touchscreen` | Resistive touchscreen input |
| `adafruit_minimqtt` | MQTT publish/subscribe for WLED |
| `neopixel` | Onboard NeoPixel status indicator |

---

## License

MIT
