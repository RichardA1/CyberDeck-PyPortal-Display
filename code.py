# ============================================================
#  CyberDeck PyPortal — Status Display + WLED Controller
#  code.py  |  CircuitPython 9.x
# ============================================================
#
#  QUICK-CONFIG — the only values you should need to change
#  are marked with  ← CHANGE ME  comments below.
#
#  WiFi credentials live in settings.toml (NOT here).
#
# ============================================================

import time
import board
import displayio
import terminalio
import neopixel
import socketpool
import wifi
import adafruit_requests
from adafruit_display_text import label
from adafruit_bitmap_font import bitmap_font

# ── Optional: import MQTT library if installed ──────────────
try:
    import adafruit_minimqtt.adafruit_minimqtt as MQTT
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

# ── Touch ────────────────────────────────────────────────────
try:
    from adafruit_touchscreen import Touchscreen
    ts = Touchscreen(
        board.TOUCH_XL, board.TOUCH_XR,
        board.TOUCH_YD, board.TOUCH_YU,
        calibration=((5200, 59000), (5800, 57000)),
        size=(320, 240),
    )
    TOUCH_AVAILABLE = True
except Exception:
    TOUCH_AVAILABLE = False

# ============================================================
#  ★  USER CONFIGURATION  ★
#  Edit this section to match your network and WLED setup.
# ============================================================

# ── Hub endpoints ────────────────────────────────────────────
HUB_STATS_URL  = "http://192.168.4.1/stats.json"    # ← CHANGE ME if hub IP differs
HUB_UPS_URL    = "http://192.168.4.1/ups-status.json"  # ← CHANGE ME if hub IP differs
REFRESH_SEC    = 15      # How often to auto-refresh status (seconds)
RETRY_OFFLINE  = 30      # Retry interval when hub unreachable (seconds)

# ── MQTT broker ──────────────────────────────────────────────
MQTT_BROKER    = "192.168.4.1"   # ← CHANGE ME — IP of your MQTT broker
MQTT_PORT      = 1883            # ← CHANGE ME if using a non-standard port
MQTT_USER      = ""              # ← CHANGE ME — broker username (leave blank if none)
MQTT_PASS      = ""              # ← CHANGE ME — broker password (leave blank if none)

# ── WLED device MQTT topics ──────────────────────────────────
#    Format:  "display label" : "wled/<device-name>"
#    The device name must match what you set in WLED → Config → MQTT → "Device topic"
WLED_DEVICES = {                          # ← CHANGE ME — add/rename your devices
    "DECK-STRIP"  : "wled/deck-strip",    #   e.g. "wled/<your-device-topic>"
    "SHELF"       : "wled/shelf-lights",
    "ALL"         : "wled/all",           #   WLED subscribes to wled/all automatically
}

# ── WLED Presets ─────────────────────────────────────────────
#    Format:  "LABEL"  :  wled_preset_number (integer)
#    Preset numbers must match the IDs in WLED's Preset manager.
WLED_PRESETS = {                # ← CHANGE ME — match your WLED preset IDs & names
    "NIGHTWATCH" : 1,
    "CYBERPUNK"  : 2,
    "CAMPFIRE"   : 3,
    "AURORA"     : 4,
}

# ── WLED accent colors (R, G, B) ─────────────────────────────
#    Sent alongside the preset. If the preset locks its own
#    colors in WLED, these will be ignored.
WLED_COLORS = [                 # ← CHANGE ME — swap out hex values as desired
    (255,  51,   0),   # Red-orange
    (255, 136,   0),   # Amber
    (255, 255,   0),   # Yellow
    (  0, 255, 153),   # Cyan-green (matches CyberDeck theme)
    (  0, 136, 255),   # Blue
    (204,   0, 255),   # Violet
]

# ── Display target ───────────────────────────────────────────
#    "pyportal"  → 320x240  (original or Pynt)
#    "titano"    → 480x320
DISPLAY_TARGET = "pyportal"    # ← CHANGE ME if using PyPortal Titano

# ============================================================
#  CONSTANTS & PALETTE
# ============================================================

BLACK  = 0x000000
GREEN  = 0x00FF99
DIM    = 0x008844
DARK   = 0x003311
AMBER  = 0xFFAA00
RED    = 0xFF4455
WHITE  = 0xFFFFFF

if DISPLAY_TARGET == "titano":
    DISP_W, DISP_H = 480, 320
    FONT_SCALE = 2
else:
    DISP_W, DISP_H = 320, 240
    FONT_SCALE = 1

# Use built-in terminal font (always available).
# To use a .bdf bitmap font instead, copy the font file to
# CIRCUITPY/assets/fonts/ and uncomment the two lines below:
#   FONT = bitmap_font.load_font("/assets/fonts/Hack-Regular-24.bdf")
FONT = terminalio.FONT

# ============================================================
#  NEOPIXEL STATUS INDICATOR
# ============================================================

pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.3)

def px_set(color):
    pixel.fill(color)

def px_pulse(color, times=2):
    for _ in range(times):
        pixel.fill(color)
        time.sleep(0.1)
        pixel.fill(BLACK)
        time.sleep(0.1)
    pixel.fill(color)

# ============================================================
#  WIFI & HTTP SESSION
# ============================================================

def connect_wifi():
    px_set(AMBER)
    print("Connecting to WiFi…")
    try:
        wifi.radio.connect(
            str(wifi.radio.ap_info.ssid) if wifi.radio.connected else None
        )
    except Exception:
        pass
    if not wifi.radio.connected:
        # credentials come from settings.toml automatically in CP 8+
        wifi.radio.connect(
            __import__("os").getenv("CIRCUITPY_WIFI_SSID"),
            __import__("os").getenv("CIRCUITPY_WIFI_PASSWORD"),
        )
    pool    = socketpool.SocketPool(wifi.radio)
    session = adafruit_requests.Session(pool)
    print("Connected:", wifi.radio.ipv4_address)
    return pool, session

pool, http = connect_wifi()

# ============================================================
#  DISPLAY LAYOUT
# ============================================================

display = board.DISPLAY
display.rotation = 0

root = displayio.Group()
display.root_group = root

# ── Helpers ─────────────────────────────────────────────────

def make_label(text, x, y, color=GREEN, scale=1):
    lbl = label.Label(FONT, text=text, color=color, scale=scale)
    lbl.x = x
    lbl.y = y
    return lbl

def color_rect(x, y, w, h, color):
    bmp = displayio.Bitmap(w, h, 1)
    pal = displayio.Palette(1)
    pal[0] = color
    tile = displayio.TileGrid(bmp, pixel_shader=pal, x=x, y=y)
    return tile

# ── Header bar ──────────────────────────────────────────────

header_bg = color_rect(0, 0, DISP_W, 18, 0x001a0d)
root.append(header_bg)
header_border = color_rect(0, 18, DISP_W, 1, GREEN)
root.append(header_border)

lbl_title = make_label("// CYBERDECK", 6, 9, GREEN)
root.append(lbl_title)
lbl_time  = make_label("--:--:--", DISP_W - 58, 9, DIM)
root.append(lbl_time)

# ── Nav tab bar (STATUS | WLED) ──────────────────────────────

nav_bg = color_rect(0, 19, DISP_W, 14, 0x000d06)
root.append(nav_bg)
nav_border = color_rect(0, 33, DISP_W, 1, DARK)
root.append(nav_border)

# Tab divider
tab_div = color_rect(DISP_W // 2, 19, 1, 14, DARK)
root.append(tab_div)

lbl_tab_status = make_label("STATUS", 12, 26, DIM)
root.append(lbl_tab_status)
lbl_tab_wled   = make_label("WLED", DISP_W // 2 + 12, 26, DIM)
root.append(lbl_tab_wled)

# Active-tab underline (moves between tabs)
tab_underline = color_rect(0, 32, DISP_W // 2, 1, GREEN)
root.append(tab_underline)

# ── Status page group ────────────────────────────────────────

status_group = displayio.Group()

# Row Y positions (relative to content area starting at y=34)
ROW_Y = [44, 56, 68, 80, 92, 106, 118, 130, 142, 156, 168]

status_labels = {}

def add_status_row(key, label_text, row, label_color=DIM, val_color=GREEN):
    lbl_k = make_label(label_text, 6,        ROW_Y[row], label_color)
    lbl_v = make_label("--",       DISP_W//2, ROW_Y[row], val_color)
    status_group.append(lbl_k)
    status_group.append(lbl_v)
    status_labels[key] = lbl_v

# Section: Network
status_group.append(make_label("NETWORK", 6, ROW_Y[0]-6, DARK))
add_status_row("ip",      "PRIVATE IP",  0)
add_status_row("clients", "DEVICES",     1)

# Section: System
status_group.append(make_label("SYSTEM",  6, ROW_Y[2]+2, DARK))
add_status_row("cpu_temp","CPU TEMP",    3)
add_status_row("cpu_load","CPU LOAD",    4)
add_status_row("mem",     "MEMORY",      5)
add_status_row("uptime",  "UPTIME",      6)

# Section: Services
status_group.append(make_label("SERVICES", 6, ROW_Y[7]+2, DARK))
add_status_row("svc_hostapd",   "hostapd",   8)
add_status_row("svc_nginx",     "nginx",     9)
add_status_row("svc_smbd",      "smbd",      10)

root.append(status_group)

# ── Footer ───────────────────────────────────────────────────

footer_border = color_rect(0, DISP_H - 14, DISP_W, 1, DARK)
root.append(footer_border)
footer_bg = color_rect(0, DISP_H - 13, DISP_W, 13, 0x000d06)
root.append(footer_bg)

lbl_footer = make_label("CONNECTING…", 6, DISP_H - 7, DARK)
root.append(lbl_footer)

# ── WLED page group ──────────────────────────────────────────

wled_group = displayio.Group()
wled_group.hidden = True

WLED_Y_BASE = 38

# Power row
wled_group.append(make_label("POWER", 6, WLED_Y_BASE + 8, DIM))
lbl_power_val = make_label("OFF", DISP_W - 36, WLED_Y_BASE + 8, RED)
wled_group.append(lbl_power_val)

# Brightness row
wled_group.append(make_label("BRIGHT", 6, WLED_Y_BASE + 22, DIM))
lbl_bri_val = make_label("178", DISP_W - 36, WLED_Y_BASE + 22, GREEN)
wled_group.append(lbl_bri_val)

# Device row
wled_group.append(make_label("TARGET", 6, WLED_Y_BASE + 36, DIM))
lbl_device = make_label(list(WLED_DEVICES.keys())[0], 60, WLED_Y_BASE + 36, GREEN)
wled_group.append(lbl_device)

# Preset section
wled_group.append(make_label("PRESET", 6, WLED_Y_BASE + 52, DARK))

preset_names = list(WLED_PRESETS.keys())
preset_labels = []
PRESET_COLS = [6, DISP_W // 2]
for i, name in enumerate(preset_names[:4]):
    row = i // 2
    col = i % 2
    px = PRESET_COLS[col]
    py = WLED_Y_BASE + 64 + row * 16
    pl = make_label(f"{name[:9]:<9} #{WLED_PRESETS[name]}", px, py, DARK)
    wled_group.append(pl)
    preset_labels.append(pl)

# Color row
wled_group.append(make_label("COLOR", 6, WLED_Y_BASE + 100, DARK))
lbl_color_val = make_label("255,51,0", 50, WLED_Y_BASE + 100, GREEN)
wled_group.append(lbl_color_val)

# MQTT status line in footer area (shared footer)
lbl_mqtt_status = make_label("MQTT: --", 6, DISP_H - 7, DARK)

root.append(wled_group)

# ============================================================
#  STATE MACHINE
# ============================================================

SCREEN_STATUS = 0
SCREEN_WLED   = 1
current_screen = SCREEN_STATUS

wled_power     = False
wled_bri       = 178
wled_device_idx = 0
wled_preset_idx = 0
wled_color_idx  = 0

mqtt_client = None

def set_screen(screen):
    global current_screen
    current_screen = screen
    if screen == SCREEN_STATUS:
        status_group.hidden = False
        wled_group.hidden   = True
        tab_underline.x     = 0
        lbl_tab_status.color = GREEN
        lbl_tab_wled.color   = DIM
        # swap footer label
        root.remove(lbl_mqtt_status) if lbl_mqtt_status in root else None
        if lbl_footer not in root:
            root.append(lbl_footer)
    else:
        status_group.hidden = True
        wled_group.hidden   = False
        tab_underline.x     = DISP_W // 2
        lbl_tab_status.color = DIM
        lbl_tab_wled.color   = GREEN
        if lbl_footer in root:
            root.remove(lbl_footer)
        if lbl_mqtt_status not in root:
            root.append(lbl_mqtt_status)

def svc_color(state):
    return GREEN if state == "active" else RED

# ============================================================
#  DATA FETCH — STATUS
# ============================================================

hub_offline = False

def fetch_status():
    global hub_offline
    px_set(AMBER)
    try:
        r = http.get(HUB_STATS_URL, timeout=8)
        stats = r.json()
        r.close()

        r2 = http.get(HUB_UPS_URL, timeout=8)
        ups = r2.json()
        r2.close()

        hub_offline = False
        px_pulse(GREEN)
        return stats, ups

    except Exception as e:
        print("Fetch error:", e)
        hub_offline = True
        px_set(RED)
        return None, None

def update_status_display(stats, ups):
    if stats is None:
        lbl_footer.text  = "HUB OFFLINE — retrying…"
        lbl_footer.color = RED
        for lbl in status_labels.values():
            lbl.text  = "--"
            lbl.color = DIM
        return

    lbl_footer.color = DARK
    lbl_footer.text  = f"refreshed {int(time.monotonic()//1)}s ago"

    status_labels["ip"].text      = stats.get("ip", "?")
    status_labels["clients"].text = f"{stats.get('clients', '?')} connected"

    temp = stats.get("cpu_temp", 0)
    status_labels["cpu_temp"].text  = f"{temp:.1f}C"
    status_labels["cpu_temp"].color = AMBER if temp >= 70 else GREEN

    status_labels["cpu_load"].text = f"{stats.get('cpu_load', '?')}%"
    status_labels["mem"].text      = f"{stats.get('mem_pct', '?')}% used"
    status_labels["uptime"].text   = stats.get("uptime", "?").replace("up ", "")

    svcs = stats.get("services", {})
    for key in ("hostapd", "nginx", "smbd"):
        state = svcs.get(key, "unknown")
        status_labels[f"svc_{key}"].text  = state.upper()
        status_labels[f"svc_{key}"].color = svc_color(state)

    # Battery in footer if UPS available
    if ups and ups.get("available"):
        batt = ups["battery"]
        pct  = batt.get("percent", "?")
        stat = batt.get("status", "?")
        lbl_footer.text  = f"BAT {pct}%  {stat}"
        lbl_footer.color = AMBER if stat == "DISCHARGING" else GREEN

# ============================================================
#  MQTT — WLED CONTROL
# ============================================================

def mqtt_connect():
    global mqtt_client
    if not MQTT_AVAILABLE:
        lbl_mqtt_status.text = "MQTT LIB MISSING"
        return False
    try:
        mqtt_client = MQTT.MQTT(
            broker   = MQTT_BROKER,
            port     = MQTT_PORT,
            username = MQTT_USER or None,
            password = MQTT_PASS or None,
            socket_pool = pool,
        )
        mqtt_client.connect()
        lbl_mqtt_status.text  = f"MQTT OK  {MQTT_BROKER}"
        lbl_mqtt_status.color = DIM
        return True
    except Exception as e:
        print("MQTT connect error:", e)
        lbl_mqtt_status.text  = "MQTT OFFLINE"
        lbl_mqtt_status.color = RED
        mqtt_client = None
        return False

def mqtt_publish_wled():
    """Build and publish a WLED JSON payload to the active device topic."""
    global mqtt_client
    device_key   = list(WLED_DEVICES.keys())[wled_device_idx]
    base_topic   = WLED_DEVICES[device_key]
    topic        = base_topic + "/api"

    preset_key   = list(WLED_PRESETS.keys())[wled_preset_idx]
    preset_id    = WLED_PRESETS[preset_key]
    r, g, b      = WLED_COLORS[wled_color_idx]

    payload = (
        f'{{"on":{str(wled_power).lower()},'
        f'"bri":{wled_bri},'
        f'"ps":{preset_id},'
        f'"seg":[{{"col":[[{r},{g},{b}]]}}]}}'
    )

    if mqtt_client is None:
        if not mqtt_connect():
            return

    try:
        mqtt_client.publish(topic, payload)
        short = f"PUB {base_topic.split('/')[-1]}→ps{preset_id}"
        lbl_mqtt_status.text  = short
        lbl_mqtt_status.color = DIM
        print(f"MQTT → {topic}: {payload}")
    except Exception as e:
        print("MQTT publish error:", e)
        lbl_mqtt_status.text  = "MQTT ERR — tap retry"
        lbl_mqtt_status.color = RED
        mqtt_client = None

def update_wled_display():
    """Refresh all text labels on the WLED page to match current state."""
    device_key = list(WLED_DEVICES.keys())[wled_device_idx]
    preset_key = list(WLED_PRESETS.keys())[wled_preset_idx]
    r, g, b    = WLED_COLORS[wled_color_idx]

    lbl_power_val.text  = "ON"  if wled_power else "OFF"
    lbl_power_val.color = GREEN if wled_power else RED
    lbl_bri_val.text    = str(wled_bri)
    lbl_device.text     = device_key
    lbl_color_val.text  = f"{r},{g},{b}"

    for i, pl in enumerate(preset_labels):
        name = preset_names[i] if i < len(preset_names) else ""
        pid  = WLED_PRESETS.get(name, "?")
        pl.color = GREEN if i == wled_preset_idx else DARK
        pl.text  = f"{name[:9]:<9} #{pid}"

# ============================================================
#  TOUCH ZONES
#  Each zone is (x1, y1, x2, y2) → action string
# ============================================================

def point_in(touch, x1, y1, x2, y2):
    if touch is None:
        return False
    tx, ty = touch[0], touch[1]
    return x1 <= tx <= x2 and y1 <= ty <= y2

def handle_touch(touch):
    global wled_power, wled_bri, wled_device_idx, wled_preset_idx, wled_color_idx

    # ── Tab bar ──────────────────────────────────────────────
    if point_in(touch, 0, 19, DISP_W//2, 33):
        set_screen(SCREEN_STATUS)
        return
    if point_in(touch, DISP_W//2, 19, DISP_W, 33):
        set_screen(SCREEN_WLED)
        if mqtt_client is None:
            mqtt_connect()
        return

    # ── Status screen: tap anywhere = refresh ────────────────
    if current_screen == SCREEN_STATUS:
        return True   # signal caller to refresh

    # ── WLED screen touch zones ───────────────────────────────
    if current_screen == SCREEN_WLED:
        WY = WLED_Y_BASE

        # Power toggle (right side of power row)
        if point_in(touch, DISP_W//2, WY, DISP_W, WY+16):
            wled_power = not wled_power
            update_wled_display()
            mqtt_publish_wled()
            return

        # Brightness — left/right halves of the row nudge ±20
        if point_in(touch, 0, WY+16, DISP_W, WY+32):
            if touch[0] < DISP_W // 2:
                wled_bri = max(0,   wled_bri - 20)
            else:
                wled_bri = min(255, wled_bri + 20)
            update_wled_display()
            mqtt_publish_wled()
            return

        # Device cycle (tap device row)
        if point_in(touch, 0, WY+32, DISP_W, WY+48):
            wled_device_idx = (wled_device_idx + 1) % len(WLED_DEVICES)
            update_wled_display()
            return

        # Preset buttons (2×2 grid)
        for i in range(min(4, len(WLED_PRESETS))):
            row = i // 2
            col = i % 2
            px1 = PRESET_COLS[col]
            px2 = px1 + DISP_W // 2 - 4
            py1 = WY + 60 + row * 16
            py2 = py1 + 15
            if point_in(touch, px1, py1, px2, py2):
                wled_preset_idx = i
                update_wled_display()
                mqtt_publish_wled()
                return

        # Color swatches — divide the color row into 6 equal zones
        SWATCH_W = (DISP_W - 50) // 6
        for i in range(6):
            sx1 = 50 + i * SWATCH_W
            sx2 = sx1 + SWATCH_W
            if point_in(touch, sx1, WY+95, sx2, WY+115):
                wled_color_idx = i
                update_wled_display()
                mqtt_publish_wled()
                return

    return False

# ============================================================
#  MAIN LOOP
# ============================================================

set_screen(SCREEN_STATUS)
update_wled_display()

last_refresh  = -REFRESH_SEC   # force immediate fetch on boot
last_touch_t  = 0
TOUCH_DEBOUNCE = 0.4

print("CyberDeck PyPortal ready.")

while True:
    now = time.monotonic()

    # ── Touch handling ───────────────────────────────────────
    if TOUCH_AVAILABLE:
        touch = ts.touch_point
        if touch and (now - last_touch_t) > TOUCH_DEBOUNCE:
            last_touch_t = now
            result = handle_touch(touch)
            if result is True:
                last_refresh = -REFRESH_SEC   # force refresh

    # ── Auto-refresh status data ─────────────────────────────
    interval = RETRY_OFFLINE if hub_offline else REFRESH_SEC
    if current_screen == SCREEN_STATUS and (now - last_refresh) >= interval:
        last_refresh = now
        stats, ups = fetch_status()
        update_status_display(stats, ups)

    # ── Clock tick ───────────────────────────────────────────
    try:
        t = time.localtime()
        lbl_time.text = f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}"
    except Exception:
        pass

    # ── Keep MQTT socket alive ────────────────────────────────
    if current_screen == SCREEN_WLED and mqtt_client is not None:
        try:
            mqtt_client.loop(timeout=0.1)
        except Exception:
            mqtt_client = None
            lbl_mqtt_status.text  = "MQTT DROPPED"
            lbl_mqtt_status.color = RED

    time.sleep(0.05)
