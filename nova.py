import sys, os
if sys.stdout is None: sys.stdout = open(os.devnull, "w")     # exe без консоли: print() не должен падать
if sys.stderr is None: sys.stderr = open(os.devnull, "w")

VERSION = "7.0.0"                      # ← именно эту строку читает самообновление; при выпуске правь её и тег релиза (v7.0.0)
REPO = "fundreamer365/Nova"

from difflib import SequenceMatcher
import html as htmllib, zipfile, shutil
import asyncio, ast, base64, ctypes, difflib, hashlib, io, json, math, operator, queue, random, re, subprocess, threading, time, webbrowser
from collections import deque
from pathlib import Path
from urllib.parse import quote
import numpy as np, psutil, requests, sounddevice as sd
import speech_recognition as sr, edge_tts
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame
from PySide6.QtCore import Qt, QTimer, QObject, Signal, QPointF
from PySide6.QtGui import (QColor, QPainter, QPen, QBrush, QRadialGradient, QPainterPath, QFont, QTextCharFormat, QTextCursor,
                           QTextBlockFormat, QIcon, QImage, QKeySequence, QShortcut, QAction, QPalette)
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
                               QLineEdit, QComboBox, QTextBrowser, QTextEdit, QScrollArea, QDialog, QSlider, QFileDialog,
                               QMessageBox, QFrame, QSystemTrayIcon, QMenu, QAbstractButton)

FROZEN = getattr(sys, "frozen", False)
SELF = Path(sys.executable if FROZEN else __file__).resolve()
API, RAW = f"https://api.github.com/repos/{REPO}", f"https://raw.githubusercontent.com/{REPO}"
UA = {"User-Agent": f"Nova/{VERSION}", "Accept": "application/vnd.github+json"}
HOME = Path.home() / ".nova"
CACHE = HOME / "cache"


def resource(name):
    """Файл, лежащий рядом со скриптом (или внутри exe, если собрано PyInstaller)."""
    base = Path(getattr(sys, "_MEIPASS", SELF.parent))
    return base / name


def known_dir(name):
    """Настоящая папка Windows (рабочий стол часто лежит в OneDrive, а не в ~/Desktop)."""
    if os.name == "nt":
        try:
            import winreg
            key = {"Desktop": "Desktop", "Documents": "Personal", "Pictures": "My Pictures", "Music": "My Music", "Videos": "My Video",
                   "Downloads": "{374DE290-123F-4565-9164-39C4925E467B}"}[name]
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
                p = Path(os.path.expandvars(winreg.QueryValueEx(k, key)[0]))
                if p.exists(): return p
        except Exception: pass
    return Path.home() / name


VOICES = {"Светлана (рус)": "ru-RU-SvetlanaNeural", "Дмитрий (рус)": "ru-RU-DmitryNeural",
          "Polina (укр)": "uk-UA-PolinaNeural",
          "Ava · multilingual": "en-US-AvaMultilingualNeural", "Andrew · multilingual": "en-US-AndrewMultilingualNeural",
          "Emma · multilingual": "en-US-EmmaMultilingualNeural", "Brian · multilingual": "en-US-BrianMultilingualNeural",
          "Aria (en)": "en-US-AriaNeural", "Guy (en)": "en-US-GuyNeural"}
LANGS = {"Русский": "ru-RU", "English": "en-US", "Українська": "uk-UA", "Deutsch": "de-DE"}
STYLES = {"Коротко": "1–2 предложения", "Обычно": "2–4 предложения", "Подробно": "5–8 предложений"}
MIC_DEFAULT = "По умолчанию"
DEFAULT_CFG = dict(
    name="Нова", voice="Светлана (рус)", rate=8, pitch=0, volume=100, tts=True, sync_text=True,
    mic=MIC_DEFAULT, mic_sens=2.5, silence=0.9, max_rec=20, wait_speech=8, lang="ru-RU", auto=False,
    ai=True, ai_model="openai", ai_style="Коротко", ai_timeout=40, history_len=12, learn=True, persona="Дружелюбная",
    font_size=11, topmost=False, opacity=100, theme="Аврора", copy_on_select=False, city="",
    ver=7, wake=True, wake_aliases="", conv_window=25, wake_chime=True, speak_typed=True,
    autosave=True, autosave_dir=str(HOME / "chats"), autosave_fmt="txt", autosave_sec=30, autosave_keep=30, restore_chat=False,
    work_dir=str(known_dir("Desktop") / "Nova"), allow_control=True, allow_power=True, allow_shell=False, confirm_actions=True,
    vision=True, img_side=1280,
    auto_update=True, update_hours=6, auto_install=False, autostart=False, tray_close=False)
UI_KEYS = {"font_size", "topmost", "opacity", "theme"}

BG, PANEL, CARD, TEXT, MUTE = "#0b0d1a", "#151932", "#1f2547", "#eceeff", "#7f86b8"
PINK, VIO, CYAN = "#ff6b8b", "#7c5cff", "#38e1e6"
THEMES = {"Аврора": (PINK, VIO, CYAN), "Океан": ("#4cc9f0", "#4361ee", "#7ae7c7"), "Закат": ("#ff9f1c", "#ff4d6d", "#c77dff"),
          "Неон": ("#39ff14", "#00f5d4", "#f15bb5"), "Лёд": ("#b8c0ff", "#74c0fc", "#e0fbfc")}
PERSONAS = {"Дружелюбная": "Ты дружелюбный голосовой помощник.",
            "Саркастичная": "Ты остроумный помощник с лёгким сарказмом, но всегда по делу и без грубости.",
            "Пират": "Ты весёлый пират-помощник: говоришь с морскими словечками, но отвечаешь по делу.",
            "Профессор": "Ты увлечённый профессор: объясняешь с яркими примерами и аналогиями.",
            "Сказочница": "Ты добрая сказочница: отвечаешь образно и тепло.",
            "Лаконичная": "Ты предельно лаконичный помощник: только суть, без вступлений."}
DUR_RE = r"\d+(?:[.,]\d+)?\s*(?:сек\w*|мин\w*|час\w*|ч\b)|полтора\s+час\w*|полчаса|\b(?:час|минуту|секунду)\b"
SYSTEM_ARGS = {"блокнот": "notepad", "калькулятор": "calc", "проводник": "explorer", "диспетчер задач": "taskmgr",
               "пэйнт": "mspaint", "paint": "mspaint", "настройки": "ms-settings:", "параметры": "ms-settings:",
               "командную строку": "cmd", "терминал": "wt"}
ALIASES = {"хром": "chrome", "гугл хром": "chrome", "дискорд": "discord", "стим": "steam", "телеграм": "telegram",
           "спотифай": "spotify", "юнити": "unity hub", "ворд": "word", "эксель": "excel", "обс": "obs studio",
           "браузер": "chrome", "майнкрафт": "minecraft launcher", "фаерфокс": "firefox"}
SITES = {"ютуб": "youtube.com", "youtube": "youtube.com", "гугл": "google.com", "гитхаб": "github.com", "вк": "vk.com",
         "вконтакте": "vk.com", "почту": "mail.google.com", "карты": "maps.google.com", "твич": "twitch.tv",
         "itch": "itch.io", "тикток": "tiktok.com", "переводчик": "translate.google.com"}
DAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
AI_URL = "https://text.pollinations.ai/openai"
DETAILS_RE = re.compile(r"\n\s*-{3,}")
MAX_ATT = 10
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
TEXT_EXT = {".txt", ".md", ".py", ".js", ".ts", ".json", ".csv", ".html", ".css", ".xml", ".yaml", ".yml", ".log", ".ini", ".cfg",
            ".toml", ".cs", ".java", ".cpp", ".c", ".h", ".sql", ".bat", ".ps1", ".sh", ".lua", ".gd", ".rs", ".go", ".php", ".kt"}
PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s`\"'<>|?*]+")
KNOWN = {"загрузки": "Downloads", "документы": "Documents", "рабочий стол": "Desktop", "картинки": "Pictures",
         "изображения": "Pictures", "музыка": "Music", "музыку": "Music", "видео": "Videos", "скриншоты": "Pictures/Nova"}
KEYS = {"энтер": 0x0D, "enter": 0x0D, "ввод": 0x0D, "эскейп": 0x1B, "escape": 0x1B, "esc": 0x1B, "таб": 0x09, "tab": 0x09,
        "пробел": 0x20, "space": 0x20, "бэкспейс": 0x08, "backspace": 0x08, "удалить": 0x2E, "delete": 0x2E, "del": 0x2E,
        "вверх": 0x26, "вниз": 0x28, "влево": 0x25, "вправо": 0x27, "виндовс": 0x5B, "win": 0x5B, "винда": 0x5B,
        "ctrl": 0x11, "контрол": 0x11, "control": 0x11, "alt": 0x12, "альт": 0x12, "shift": 0x10, "шифт": 0x10,
        "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22, "printscreen": 0x2C}
KEYS.update({f"f{i}": 0x6F + i for i in range(1, 13)})
RU2EN = dict(zip("йцукенгшщзфывапролдячсмить", "qwertyuiopasdfghjklzxcvbnm"))
EXT_KEYS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B}
SETTINGS_PAGES = {"wifi": "network-wifi", "вайфай": "network-wifi", "wi-fi": "network-wifi", "звука": "sound", "звук": "sound",
                  "экрана": "display", "дисплея": "display", "bluetooth": "bluetooth", "блютуз": "bluetooth",
                  "обновления": "windowsupdate", "приложений": "appsfeatures", "батареи": "batterysaver", "принтеров": "printers"}

QSS = """
QMainWindow, QDialog, QScrollArea, #central, #body { background: $BG; }
QWidget { color: $TEXT; font-family: 'Segoe UI'; font-size: 13px; }
QLabel { background: transparent; }
QTextBrowser { background: $PANEL; border: none; border-radius: 18px; padding: 8px; selection-background-color: $VIO; selection-color: #fff; }
QLineEdit { background: $PANEL; border: 1px solid $CARD; border-radius: 21px; padding: 0 16px; min-height: 40px; selection-background-color: $VIO; }
QLineEdit:focus { border: 1px solid $VIO; }
#findbar { background: $PANEL; border-radius: 14px; }
#findbar QLineEdit { min-height: 28px; border-radius: 14px; background: $CARD; border: none; }
#abar { background: $PANEL; border-radius: 14px; }
QPushButton { background: $CARD; border: none; border-radius: 19px; padding: 0 16px; min-height: 38px; }
QPushButton:hover { background: $VIO; }
QPushButton#accent { background: $CYAN; color: #07202a; font-weight: 600; }
QPushButton#accent:hover { background: #7cf0f4; }
QPushButton#icon { min-width: 38px; max-width: 38px; padding: 0; font-size: 16px; }
QPushButton#chip { min-height: 22px; border-radius: 11px; padding: 0 10px; font-size: 11px; }
QPushButton#chip:hover { background: $PINK; }
QComboBox { background: $PANEL; border: 1px solid $CARD; border-radius: 14px; padding: 6px 12px; min-height: 22px; }
QComboBox:hover { border-color: $VIO; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: $PANEL; selection-background-color: $VIO; border: 1px solid $CARD; outline: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px; }
QScrollBar::handle:vertical { background: $CARD; border-radius: 3px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $VIO; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSlider::groove:horizontal { height: 5px; background: $CARD; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $VIO; border-radius: 2px; }
QSlider::handle:horizontal { background: #fff; width: 14px; margin: -5px 0; border-radius: 7px; }
QMenu { background: $CARD; border: 1px solid $PANEL; padding: 6px; }
QMenu::item { padding: 6px 24px; border-radius: 6px; }
QMenu::item:selected { background: $VIO; }
QMenu::item:disabled { color: $MUTE; }
QMenu::separator { height: 1px; background: $PANEL; margin: 4px 8px; }
QMessageBox { background: $BG; }
QToolTip { background: $CARD; color: $TEXT; border: 1px solid $VIO; padding: 4px; }
"""
for _k, _v in dict(BG=BG, PANEL=PANEL, CARD=CARD, TEXT=TEXT, MUTE=MUTE, PINK=PINK, VIO=VIO, CYAN=CYAN).items():
    QSS = QSS.replace("$" + _k, _v)


# ---------- утилиты ----------
def tts_clean(s):
    s = re.sub(r"```.*?```", " ", s, flags=re.S)
    s = re.sub(r"[*_`#>]|[\U0001F300-\U0001FAFF]", "", s)
    for a, b in ((" ГБ", " гигабайт"), ("%", " процентов"), ("°C", " градусов"), ("&", " и "), ("—", ", ")):
        s = s.replace(a, b)
    return s.strip()


def sentences(s):
    return [x.strip() for x in re.split(r"(?<=[.!?…])\s+|\n+", s) if x.strip()]


def split_long(items, n=200):
    """Режем очень длинные предложения: короткие куски синтезируются быстрее и параллельно."""
    out = []
    for s in items:
        while len(s) > n:
            k = s.rfind(", ", 0, n)
            if k < 40: k = s.rfind(" ", 0, n)
            if k < 40: k = n
            out.append(s[:k + 1].strip()); s = s[k + 1:].strip()
        if s: out.append(s)
    return out


def parse_duration(t):
    s = 0.0
    if "полчаса" in t: s += 1800
    if re.search(r"полтора\s+час", t): s += 5400
    for n, u in re.findall(r"(\d+(?:[.,]\d+)?)\s*(сек\w*|мин\w*|час\w*|ч\b)", t):
        s += float(n.replace(",", ".")) * (1 if u.startswith("сек") else 60 if u.startswith("мин") else 3600)
    if s == 0:
        if re.search(r"\bчас\b", t): s = 3600
        elif re.search(r"\bминуту\b", t): s = 60
        elif re.search(r"\bсекунду\b", t): s = 1
    return int(s)


def fmt_dur(s):
    h, r = divmod(int(s), 3600); m, sc = divmod(r, 60); out = []
    for n, f in ((h, ("час", "часа", "часов")), (m, ("минуту", "минуты", "минут")), (sc, ("секунду", "секунды", "секунд"))):
        if n:
            w = f[2] if 11 <= n % 100 <= 14 else f[0] if n % 10 == 1 else f[1] if 2 <= n % 10 <= 4 else f[2]
            out.append(f"{n} {w}")
    return " ".join(out) or "0 секунд"


def fmt_num(x):
    if isinstance(x, float):
        if x.is_integer() and abs(x) < 1e15: return str(int(x))
        return f"{x:.6g}".replace(".", ",")
    return str(x)


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}


def calc(expr):
    """Безопасный калькулятор: понимает и «25 умножить на 4», и «15 процентов от 200». None — если не выражение."""
    e = expr.lower().replace(",", ".")
    if m := re.search(r"(\d+(?:\.\d+)?)\s*(?:%|процент\w*)\s*от\s*(\d+(?:\.\d+)?)", e):
        return fmt_num(float(m[1]) * float(m[2]) / 100)
    for a, b in (("умножить на", "*"), ("умножь на", "*"), ("помножить на", "*"), ("разделить на", "/"), ("поделить на", "/"),
                 ("делить на", "/"), ("в степени", "**"), ("в квадрате", "**2"), ("в кубе", "**3"), ("плюс", "+"),
                 ("минус", "-"), ("÷", "/"), ("^", "**"), (":", "/")):
        e = e.replace(a, b)
    e = re.sub(r"(?<=\d)\s*[хx×]\s*(?=[\d(])", "*", e).strip()
    if not re.fullmatch(r"[\d\s+\-*/().%]+", e): return None

    def ev(n):
        if isinstance(n, ast.Expression): return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)): return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and (abs(b) > 100 or abs(a) > 1e6): raise ValueError
            return _OPS[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS: return _OPS[type(n.op)](ev(n.operand))
        raise ValueError
    try: return fmt_num(ev(ast.parse(e, mode="eval")))
    except Exception: return None


def vk_of(n):
    n = n.strip().lower()
    if n in KEYS: return KEYS[n]
    n = RU2EN.get(n, n)
    return ord(n.upper()) if len(n) == 1 and n.isascii() and n.isalnum() else None


def key_combo(*vks, hold=0.03):
    u = ctypes.windll.user32
    for v in vks: u.keybd_event(v, 0, 1 if v in EXT_KEYS else 0, 0); time.sleep(hold)
    for v in reversed(vks): u.keybd_event(v, 0, (1 if v in EXT_KEYS else 0) | 2, 0); time.sleep(hold)


def mouse_pos():
    class P(ctypes.Structure): _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    p = P(); ctypes.windll.user32.GetCursorPos(ctypes.byref(p)); return p.x, p.y


def mouse_move(x, y): ctypes.windll.user32.SetCursorPos(int(x), int(y))


def mouse_click(btn="left", n=1):
    dn, up = {"left": (2, 4), "right": (8, 16), "middle": (0x20, 0x40)}[btn]
    for _ in range(n):
        ctypes.windll.user32.mouse_event(dn, 0, 0, 0, 0); ctypes.windll.user32.mouse_event(up, 0, 0, 0, 0); time.sleep(0.06)


def mouse_wheel(d): ctypes.windll.user32.mouse_event(0x800, 0, 0, d & 0xFFFFFFFF, 0)


def screen_size(): return ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)


def list_windows():
    """(окна этого стола, окна других рабочих столов). Windows помечает окна чужих столов как «cloaked» (значение 2)."""
    u, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
    u.IsWindowVisible.argtypes = u.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
    u.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    u.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    dwm.DwmGetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
    here, other = [], []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, _):
        try:
            if not u.IsWindowVisible(h) or u.GetWindowTextLengthW(h) == 0 or u.GetWindowLongW(h, -20) & 0x80: return True
            buf = ctypes.create_unicode_buffer(256); u.GetWindowTextW(h, buf, 256)
            title = buf.value.strip()
            if not title or title in ("Program Manager", "Settings", "Параметры"): return True
            cl = ctypes.c_int(0); dwm.DwmGetWindowAttribute(h, 14, ctypes.byref(cl), 4)
            if cl.value == 0: here.append(title)
            elif cl.value == 2: other.append(title)
        except Exception: pass
        return True
    u.EnumWindows(cb, 0)
    return here, other


def read_file_text(p, limit=20000):
    p = Path(p); ext = p.suffix.lower()
    try:
        if ext in TEXT_EXT: return p.read_text("utf-8", errors="replace")[:limit]
        if ext == ".docx":
            x = zipfile.ZipFile(p).read("word/document.xml").decode("utf-8", "ignore")
            return re.sub(r"[ \t]+", " ", re.sub(r"<[^>]+>", "", x.replace("</w:p>", "\n")))[:limit]
        if ext == ".pdf":
            from pypdf import PdfReader
            return "\n".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages[:20])[:limit]
    except Exception: pass
    return None


def img_b64(path, side=1280):
    try:
        from PIL import Image
        im = Image.open(path); im.thumbnail((side, side))
        if im.mode != "RGB": im = im.convert("RGB")
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=82); data, mime = buf.getvalue(), "image/jpeg"
    except Exception:
        data = Path(path).read_bytes(); mime = "image/png" if str(path).lower().endswith(".png") else "image/jpeg"
        if len(data) > 4_000_000: return None
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def safe_name(s, default="новый"):
    return re.sub(r'[<>:"/\\|?*\n\r\t]', "", s).strip(" .")[:80] or default


def unique_path(p):
    p = Path(p); q, i = p, 2
    while q.exists(): q = p.with_name(f"{p.stem} ({i}){p.suffix}"); i += 1
    return q


def scan_start_menu():
    apps = {}
    for root in (os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
                 os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs")):
        for d, _, files in os.walk(root):
            for f in files:
                if f.lower().endswith(".lnk"): apps[f[:-4].lower()] = os.path.join(d, f)
    return apps


def mic_names():
    try:
        return [MIC_DEFAULT] + sorted({d["name"] for d in sd.query_devices() if d["max_input_channels"] > 0})
    except Exception:
        return [MIC_DEFAULT]


def vtuple(s):
    return tuple(int(x) for x in re.findall(r"\d+", str(s))[:4]) or (0,)


def set_autostart(on):
    if os.name != "nt": return
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as k:
            if on:
                py = sys.executable.replace("python.exe", "pythonw.exe")
                cmd = f'"{sys.executable}"' if FROZEN else f'"{py}" "{SELF}"'
                winreg.SetValueEx(k, "Nova", 0, winreg.REG_SZ, cmd)
            else:
                try: winreg.DeleteValue(k, "Nova")
                except FileNotFoundError: pass
    except Exception: pass


_MUTEX = None


def single_instance(wait=0):
    """Не даём запустить вторую Нову (два микрофона и две озвучки — каша). wait — сколько ждать, пока закроется старая."""
    global _MUTEX
    if os.name != "nt": return True
    k, end = ctypes.windll.kernel32, time.time() + wait
    while True:
        h = k.CreateMutexW(None, False, "NovaAssistant_fundreamer365")
        if k.GetLastError() != 183: _MUTEX = h; return True
        k.CloseHandle(h)
        if time.time() >= end: return False
        time.sleep(0.3)


def dark_titlebar(win):
    if os.name != "nt": return
    try:
        hwnd, f = int(win.winId()), ctypes.windll.dwmapi.DwmSetWindowAttribute
        one = ctypes.c_int(1); f(hwnd, 20, ctypes.byref(one), 4); f(hwnd, 19, ctypes.byref(one), 4)     # тёмный заголовок
        col = ctypes.c_int(0x1a0d0b); f(hwnd, 35, ctypes.byref(col), 4); f(hwnd, 34, ctypes.byref(col), 4)   # цвет заголовка/рамки (Win11)
    except Exception: pass


# ---------- память и настройки ----------
class Memory:
    FILE = HOME / "memory.json"

    def __init__(self):
        self.lock = threading.RLock()
        self.d = {"facts": [], "requests": [], "history": [], "cfg": {}}
        try: self.d.update(json.loads(self.FILE.read_text("utf-8")))
        except Exception: pass
        old = {k: self.d[k] for k in ("voice", "rate") if k in self.d}          # миграция со старой версии
        self.cfg = {**DEFAULT_CFG, **old, **self.d.get("cfg", {})}
        if self.cfg.get("ver", 0) < 6:        # миграция: отклик на имя включён по умолчанию, рабочая папка — настоящий рабочий стол
            self.cfg.update(wake=True, work_dir=DEFAULT_CFG["work_dir"])
        self.cfg["ver"] = DEFAULT_CFG["ver"]
        self.d["cfg"] = self.cfg

    def save(self):
        with self.lock:
            try:
                self.FILE.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.FILE.with_suffix(".tmp")
                tmp.write_text(json.dumps(self.d, ensure_ascii=False, indent=1), "utf-8"); os.replace(tmp, self.FILE)
            except Exception: pass

    def fact(self, f):
        f = f.strip()
        with self.lock:
            if f and f.lower() not in [x.lower() for x in self.d["facts"]]:
                self.d["facts"] = (self.d["facts"] + [f])[-60:]; self.save()

    def request(self, t):
        with self.lock: self.d["requests"] = (self.d["requests"] + [t])[-100:]; self.save()


# ---------- озвучка: один event loop, параллельный синтез, кэш на диске ----------
class Speaker:
    def __init__(self, app):
        self.app, self.mem = app, app.mem
        self.skip, self.q, self.err = threading.Event(), queue.Queue(), False
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self.sem = asyncio.run_coroutine_threadsafe(self._mk_sem(), self.loop).result()
        CACHE.mkdir(parents=True, exist_ok=True); self.prune()
        try: pygame.mixer.init(); self.ok = True
        except Exception: self.ok = False
        threading.Thread(target=self.worker, daemon=True).start()

    @staticmethod
    async def _mk_sem(): return asyncio.Semaphore(3)

    @staticmethod
    def prune(keep=300):
        try:
            fs = sorted(CACHE.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
            for p in fs[keep:]:
                p.unlink(missing_ok=True); p.with_suffix(".json").unlink(missing_ok=True)
        except Exception: pass

    @staticmethod
    def clear_cache():
        for p in CACHE.glob("*"):
            try: p.unlink()
            except Exception: pass

    async def synth(self, text, voice, rate, pitch):
        key = hashlib.sha1(f"{voice}|{rate}|{pitch}|{text}".encode()).hexdigest()[:24]
        mp3, js = CACHE / (key + ".mp3"), CACHE / (key + ".json")
        if mp3.exists() and js.exists():
            try:
                mp3.touch(); return mp3.read_bytes(), json.loads(js.read_text("utf-8"))
            except Exception: pass
        kw = dict(rate=f"{rate:+d}%", pitch=f"{pitch:+d}Hz")
        async with self.sem:
            for attempt in range(2):
                try:
                    try: com = edge_tts.Communicate(text, voice, boundary="WordBoundary", **kw)
                    except TypeError: com = edge_tts.Communicate(text, voice, **kw)
                    audio, words = bytearray(), []
                    async for ch in com.stream():
                        if ch["type"] == "audio": audio += ch["data"]
                        elif ch["type"] == "WordBoundary": words.append((ch["offset"] / 10000, ch["text"]))
                    if not audio: raise RuntimeError("пустое аудио")
                    break
                except Exception:
                    if attempt: raise
        try: mp3.write_bytes(bytes(audio)); js.write_text(json.dumps(words), "utf-8")
        except Exception: pass
        return bytes(audio), words

    def begin(self): self.skip.clear(); self.err = False

    def feed(self, s):
        tokens = re.sub(r"[*_`#]", "", s).split()
        if not tokens: return
        c, fut = self.mem.cfg, None
        txt = tts_clean(s)
        if self.ok and c["tts"] and not self.app.silent and not self.skip.is_set() and re.search(r"\w", txt):
            fut = asyncio.run_coroutine_threadsafe(
                self.synth(txt, VOICES.get(c["voice"], VOICES["Светлана (рус)"]), int(c["rate"]), int(c["pitch"])), self.loop)
        self.q.put(("s", tokens, fut))

    def end(self, card=None):
        done = threading.Event(); self.q.put(("e", card, done)); done.wait()

    def worker(self):
        app, first = self.app, True
        while True:
            kind, a, b = self.q.get()
            try:
                if kind == "e":
                    app.ui(app.put, "\n")
                    if self.err: app.ui(app.put, "(голос недоступен — проверь интернет)\n", "time")
                    if a: app.ui(app.md, a)
                    app.ui(app.put, "\n"); first = True; app.last_end = time.time(); continue
                audio = words = None
                if b is not None:
                    if self.skip.is_set(): b.cancel()
                    else:
                        try: audio, words = b.result(timeout=40)
                        except Exception: self.err = True
                if first: app.ui(app.head, app.mem.cfg["name"]); app.set_state("speaking"); first = False
                if audio and not self.skip.is_set(): self.play(a, audio, words)
                else: app.ui(app.put, " ".join(a) + " ", "ai")
            except Exception: pass
            finally:
                if kind == "e": b.set()          # поток озвучки не умирает от одной ошибки и никогда не оставляет вызывающего ждать вечно

    def play(self, tokens, audio, words):
        c, n, app = self.mem.cfg, len(tokens), self.app
        sync = bool(c["sync_text"] and words)
        if not sync: app.ui(app.put, " ".join(tokens) + " ", "ai")
        times = [words[min(len(words) - 1, int(i * len(words) / n))][0] for i in range(n)] if sync else []
        try:
            pygame.mixer.music.set_volume(max(0, min(1, c["volume"] / 100)))
            pygame.mixer.music.load(io.BytesIO(audio), "mp3"); pygame.mixer.music.play()
        except Exception:
            self.err = True
            if sync: app.ui(app.put, " ".join(tokens) + " ", "ai")
            return
        t0, i = time.time(), 0
        while not self.skip.is_set():
            if sync:
                pos = pygame.mixer.music.get_pos()
                while i < n and times[i] <= pos + 60: app.ui(app.put, tokens[i] + " ", "ai"); i += 1
            if not pygame.mixer.music.get_busy() and time.time() - t0 > .25: break
            time.sleep(.02)
        pygame.mixer.music.stop()
        if sync and i < n: app.ui(app.put, " ".join(tokens[i:]) + " ", "ai")


# ---------- виджеты ----------
class Bridge(QObject):
    """Переправляет вызовы из рабочих потоков в поток интерфейса."""
    call = Signal(object)

    def __init__(self):
        super().__init__(); self.call.connect(self.run)

    def run(self, fn):
        try: fn()
        except Exception: pass


class Toggle(QAbstractButton):
    def __init__(self, color=VIO):
        super().__init__(); self.col = color; self.setCheckable(True); self.setFixedSize(42, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self.col if self.isChecked() else CARD)); p.drawRoundedRect(0, 0, 42, 22, 11, 11)
        p.setBrush(QColor("#ffffff")); p.drawEllipse(23 if self.isChecked() else 3, 3, 16, 16)


class Orb(QWidget):
    def __init__(self, app):
        super().__init__(); self.app, self.t, self.amp = app, 0.0, 0.05
        self.setFixedHeight(200); self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.timer = QTimer(self); self.timer.timeout.connect(self.step); self.timer.start(33)

    def step(self):
        a = self.app; self.t += 0.033
        tgt = {"idle": .05, "waiting": .05 + a.level * .3, "listening": .08 + a.level * .5, "thinking": .09,
               "speaking": .12 + .05 * math.sin(self.t * 11) + .04 * random.random()}.get(a.state_, .05)
        self.amp += (tgt - self.amp) * .15; self.update()

    def mousePressEvent(self, e): self.app.orb_click()

    def paintEvent(self, e):
        a = self.app; p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2; R = min(60, self.height() / 2 - 22)
        pk, vi, cn = a.theme
        acc = {"idle": vi, "waiting": vi, "listening": cn, "thinking": vi, "speaking": pk}.get(a.state_, vi)
        sp = 2.6 if a.state_ == "thinking" else 1
        rr = R * 2.1 * (1 + self.amp * .5)
        g = QRadialGradient(cx, cy, rr); c0, c1 = QColor(acc), QColor(acc)
        c0.setAlpha(int(min(255, 90 + self.amp * 500))); c1.setAlpha(0); g.setColorAt(0, c0); g.setColorAt(1, c1)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawEllipse(QPointF(cx, cy), rr, rr)
        for i, col in enumerate(a.theme):
            path = QPainterPath()
            for k in range(73):
                ang = k / 72 * 2 * math.pi
                n = math.sin(ang * (2 + i) + self.t * 1.4 * sp + i * 2) + math.sin(ang * 3 - self.t * 1.1 * sp)
                r = R * (1 + self.amp * n * .9); x, y = cx + math.cos(ang) * r, cy + math.sin(ang) * r
                if k == 0: path.moveTo(x, y)
                else: path.lineTo(x, y)
            for w, alpha in ((10, 55), (2.6, 255)):
                c = QColor(col); c.setAlpha(alpha); pen = QPen(c, w); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(path)


class Entry(QLineEdit):
    def __init__(self, app): super().__init__(); self.app = app

    def keyPressEvent(self, e):
        if e.matches(QKeySequence.StandardKey.Paste) and self.app.paste_media(): return
        super().keyPressEvent(e)


# ---------- приложение ----------
class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.bridge = Bridge(); self.mem = Memory(); c = self.mem.cfg
        self.setWindowTitle(c["name"]); self.setMinimumSize(420, 560); self.setAcceptDrops(True)
        if resource("icon.png").exists(): self.setWindowIcon(QIcon(str(resource("icon.png"))))
        self.resize(500, 820)
        self.state_, self.level, self.busy = "idle", 0.0, False
        self.stop_rec = threading.Event(); self.rec = sr.Recognizer(); self.win = None; self._gpu = None
        self.blocks, self.nblk, self.last_code, self.last_ai = {}, 0, "", ""
        self.timers = []
        self.att, self.last_path, self.last_shot = {"img": [], "file": []}, "", ""
        self.silent, self.conv_until, self.last_end = False, 0.0, 0.0
        self.hold, self._werr, self.macro_depth = False, 0.0, 0
        self.stem, self.saved_txt = time.strftime("chat_%Y%m%d_%H%M%S"), ""
        self.pending, self.upd_lock, self._bl = None, threading.Lock(), threading.Lock()
        self.really_quit, self._topmost = False, None
        self.apps = {}
        self.theme = THEMES.get(c["theme"], THEMES["Аврора"])
        if os.name == "nt": threading.Thread(target=lambda: self.apps.update(scan_start_menu()), daemon=True).start()
        self.speaker = Speaker(self)

        central = QWidget(); central.setObjectName("central"); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(16, 12, 16, 12); root.setSpacing(8)

        top = QHBoxLayout()
        self.title_l = QLabel(c["name"]); self.title_l.setStyleSheet("font-size:26px;font-weight:700;")
        top.addWidget(self.title_l); top.addStretch()
        self.upd_btn = QPushButton("⬆ Обновить"); self.upd_btn.setObjectName("accent"); self.upd_btn.hide()
        self.upd_btn.clicked.connect(self.btn_update); top.addWidget(self.upd_btn)
        gear = QPushButton("⚙"); gear.setObjectName("icon"); gear.clicked.connect(self.open_settings); top.addWidget(gear)
        self.vmenu = QComboBox(); self.vmenu.addItems(list(VOICES)); self.vmenu.setFixedWidth(178)
        self.vmenu.setCurrentText(c["voice"] if c["voice"] in VOICES else "Светлана (рус)")
        self.vmenu.currentTextChanged.connect(lambda v: self.cfg_set("voice", v)); top.addWidget(self.vmenu)
        root.addLayout(top)

        self.orb = Orb(self); root.addWidget(self.orb)
        self.status = QLabel(""); self.status.setAlignment(Qt.AlignmentFlag.AlignCenter); self.status.setStyleSheet(f"color:{MUTE};font-size:14px;")
        root.addWidget(self.status)

        self.fbar = QFrame(); self.fbar.setObjectName("findbar"); fl = QHBoxLayout(self.fbar); fl.setContentsMargins(8, 6, 8, 6)
        self.fent = QLineEdit(); self.fent.setPlaceholderText("Поиск по чату (Enter — дальше, Esc — закрыть)"); fl.addWidget(self.fent)
        fx = QPushButton("✕"); fx.setObjectName("icon"); fx.setFixedHeight(28); fx.clicked.connect(self.close_find); fl.addWidget(fx)
        self.fent.textChanged.connect(self.find_update); self.fent.returnPressed.connect(self.find_next); self.fbar.hide()
        root.addWidget(self.fbar)

        self.tx = QTextBrowser(); self.tx.setOpenLinks(False); self.tx.setOpenExternalLinks(False)
        self.tx.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.tx.customContextMenuRequested.connect(self.ctx_menu)
        self.tx.anchorClicked.connect(self.anchor_click); self.tx.document().setDocumentMargin(10)
        pal = self.tx.palette(); pal.setColor(QPalette.ColorRole.Link, QColor("#7cd4ff")); self.tx.setPalette(pal)
        self._cos = QTimer(self); self._cos.setSingleShot(True); self._cos.setInterval(250); self._cos.timeout.connect(self.copy_sel)
        self.tx.copyAvailable.connect(lambda ok: ok and self.mem.cfg["copy_on_select"] and self._cos.start())
        root.addWidget(self.tx, 1)

        self.abar = QFrame(); self.abar.setObjectName("abar"); QVBoxLayout(self.abar).setContentsMargins(8, 6, 8, 6)
        self.abar.hide(); root.addWidget(self.abar)

        row = QHBoxLayout(); row.setSpacing(8)
        self.entry = Entry(self); self.entry.setPlaceholderText("Напиши команду, вопрос или вставь фото (Ctrl+V)")
        self.entry.returnPressed.connect(self.on_enter); row.addWidget(self.entry, 1)
        clip = QPushButton("📎"); clip.setObjectName("icon"); clip.setFixedHeight(42); clip.clicked.connect(self.pick_files); row.addWidget(clip)
        sp = QPushButton("Говорить"); sp.setObjectName("accent"); sp.setFixedHeight(42); sp.clicked.connect(self.start_voice); row.addWidget(sp)
        sk = QPushButton("Пропустить"); sk.setFixedHeight(42); sk.clicked.connect(self.do_skip); row.addWidget(sk)
        root.addLayout(row)

        box, self.auto_t, _ = self.toggle_row("Диалог без нажатий", VIO, c["auto"], lambda v: self.cfg_set("auto", bool(v)))
        root.addWidget(box)
        box, self.wake_t, self.wake_l = self.toggle_row(f"Отзываться на имя «{c['name']}»", CYAN, c["wake"], self.toggle_wake)
        root.addWidget(box)

        QShortcut(QKeySequence.StandardKey.Find, self, self.open_find)
        QShortcut(QKeySequence("Ctrl+L"), self, self.clear_chat)
        QShortcut(QKeySequence("Escape"), self, self.on_escape)
        self.setStyleSheet(QSS); self.setup_tags(int(c["font_size"])); self.apply_ui()

        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self.windowIcon(), self); self.tray.setToolTip(c["name"])
            m = QMenu(); a1 = QAction("Открыть", self); a1.triggered.connect(self.show_front); m.addAction(a1)
            a2 = QAction("Выход", self); a2.triggered.connect(self.quit_app); m.addAction(a2)
            self.tray.setContextMenu(m); self._tray_menu = m
            self.tray.activated.connect(lambda r: r == QSystemTrayIcon.ActivationReason.Trigger and self.show_front()); self.tray.show()

        name = next((f[6:] for f in self.mem.d["facts"] if f.lower().startswith("зовут ")), "")
        if c["restore_chat"]: self.restore_last()
        self.head(c["name"]); self.put(f"Привет{', ' + name if name else ''}! Спроси что угодно или скажи «что ты умеешь».\n\n", "ai")
        self.set_state("idle"); QTimer.singleShot(2000, self.autosave_tick)
        threading.Thread(target=self.wake_loop, daemon=True).start()
        threading.Thread(target=self.update_loop, daemon=True).start()

    # ---------- потокобезопасный UI ----------
    def ui(self, fn, *a): self.bridge.call.emit(lambda: fn(*a))

    def after(self, ms, fn): QTimer.singleShot(ms, fn)

    def on_main(self, fn, timeout=3):
        """Выполнить fn в потоке интерфейса и вернуть результат (для голосовых команд)."""
        if threading.current_thread() is threading.main_thread():
            try: return fn()
            except Exception: return None
        box, ev = [], threading.Event()

        def run():
            try: box.append(fn())
            except Exception: box.append(None)
            ev.set()
        self.ui(run); ev.wait(timeout)
        return box[0] if box else None

    def take(self):
        with self._bl:
            if self.busy: return False
            self.busy = True; return True

    def toggle_row(self, text, color, checked, slot):
        t = Toggle(color); t.setChecked(bool(checked)); t.toggled.connect(slot)
        box = QWidget(); h = QHBoxLayout(box); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(10)
        lb = QLabel(text); lb.setStyleSheet(f"color:{MUTE};")
        h.addStretch(); h.addWidget(t); h.addWidget(lb); h.addStretch()
        return box, t, lb

    def show_front(self):
        self.showNormal(); self.raise_(); self.activateWindow()

    def on_escape(self):
        if self.fbar.isVisible() and self.fent.hasFocus(): self.close_find()
        else: self.do_skip()

    def orb_click(self):
        if self.state_ in ("speaking", "listening"): self.do_skip()
        else: self.start_voice()

    def showEvent(self, e):
        super().showEvent(e); dark_titlebar(self)

    def closeEvent(self, e):
        if self.mem.cfg["tray_close"] and self.tray and not self.really_quit:
            e.ignore(); self.hide(); self.tray.showMessage(self.mem.cfg["name"], "Я в трее — слушаю дальше.", QSystemTrayIcon.MessageIcon.NoIcon, 2500); return
        e.accept(); self.quit_app()

    def quit_app(self):
        self.really_quit = True; self.autosave()
        try: pygame.mixer.quit()
        except Exception: pass
        QApplication.quit(); QTimer.singleShot(2500, lambda: os._exit(0))

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()

    def dropEvent(self, e):
        fs = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile() and os.path.isfile(u.toLocalFile())]
        if fs: self.add_att(fs)

    # ---------- оформление ----------
    def mkfmt(self, fg=None, bg=None, size=0, bold=False, family=None, underline=False):
        f = QTextCharFormat()
        if fg: f.setForeground(QColor(fg))
        if bg: f.setBackground(QColor(bg))
        if family: f.setFontFamilies([family])
        if size: f.setFontPointSize(size)
        if bold: f.setFontWeight(QFont.Weight.Bold)
        if underline: f.setFontUnderline(True)
        return f

    def setup_tags(self, fs):
        m = self.mkfmt; self.fs = fs
        self.tagfmt = {"who_me": m("#a995ff", size=fs - 1, bold=True), "who_ai": m(CYAN, size=fs - 1, bold=True),
                       "time": m(MUTE, size=fs - 3), "me": m(), "ai": m(), "b": m("#ffffff", bold=True),
                       "code": m("#ffb3c4", CARD, fs - 1, family="Consolas"), "cb": m("#d6dcff", CARD, fs - 1, family="Consolas"),
                       "h": m(CYAN, size=fs + 1, bold=True), "bl": m(), "cbh": m(MUTE, CARD, fs - 2, family="Consolas"),
                       "link": m("#7cd4ff", underline=True), "copy": m("#ffffff", VIO, fs - 2, bold=True)}
        self.tx.setFont(QFont("Segoe UI", fs))

    def fmt(self, tags, href=None):
        f = QTextCharFormat(); f.setForeground(QColor(TEXT)); f.setFontFamilies(["Segoe UI"]); f.setFontPointSize(self.fs)
        for t in tags:
            if t in self.tagfmt: f.merge(self.tagfmt[t])
        if href: f.setAnchor(True); f.setAnchorHref(href)
        return f

    def apply_ui(self):
        c = self.mem.cfg
        self.theme = THEMES.get(c["theme"], THEMES["Аврора"])
        self.setWindowOpacity(max(0.4, min(1.0, c["opacity"] / 100)))
        if self._topmost != bool(c["topmost"]):
            first = self._topmost is None; self._topmost = bool(c["topmost"])
            if not first or self._topmost:
                vis = self.isVisible(); self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self._topmost)
                if vis: self.show()
        if int(c["font_size"]) != self.fs: self.setup_tags(int(c["font_size"]))

    def cfg_set(self, key, val):
        self.mem.cfg[key] = val; self.mem.save()
        if key in UI_KEYS: self.ui(self.apply_ui)
        if key == "autostart": set_autostart(bool(val))

    def set_state(self, s):
        self.state_ = s
        txt = {"idle": "Нажми на шар и говори или пиши внизу", "listening": "Слушаю… (Esc — отмена)", "thinking": "Думаю…",
               "waiting": f"Жду обращения: скажи «{self.mem.cfg['name']}…»  (или пиши внизу)",
               "speaking": "Говорю… (Esc — пропустить)"}[s]
        self.ui(lambda: self.status.setText(txt))

    # ---------- вывод в чат ----------
    def scroll_end(self):
        sb = self.tx.verticalScrollBar(); sb.setValue(sb.maximum())

    def put(self, text, *tags, href=None):
        sb = self.tx.verticalScrollBar(); stick = sb.value() >= sb.maximum() - 8
        cur = QTextCursor(self.tx.document()); cur.movePosition(QTextCursor.MoveOperation.End)
        cur.insertText(text, self.fmt(tags, href))          # отдельный курсор: выделение пользователя не сбивается
        if stick: QTimer.singleShot(0, self.scroll_end)

    def head(self, who):
        k = "me" if who == "Ты" else "ai"
        cur = QTextCursor(self.tx.document()); cur.movePosition(QTextCursor.MoveOperation.End)
        bf = QTextBlockFormat(); bf.setAlignment(Qt.AlignmentFlag.AlignRight if k == "me" else Qt.AlignmentFlag.AlignLeft)
        cur.setBlockFormat(bf)
        self.put(who + "  ", "who_" + k); self.put(time.strftime("%H:%M") + "\n", "time")

    def user_msg(self, text, att=None):
        self.head("Ты"); self.put(text + "\n", "me")
        if att and (att["img"] or att["file"]): self.show_att(att)
        else: self.put("\n")

    def md(self, text):
        code = None
        for line in text.strip().split("\n"):
            if line.strip().startswith("```"):
                if code is None: code = [line.strip()[3:].strip()]
                else: self.code_block(code); code = None
                continue
            if code is not None: code.append(line); continue
            if m := re.match(r"^#{1,3}\s+(.*)", line): self.put(m[1] + "\n", "h"); continue
            m = re.match(r"^\s*([-*•]|\d+[.)])\s+(.*)", line)
            pre = "bl" if m else None
            body = (("• " if m[1] in "-*•" else m[1] + " ") + m[2]) if m else line
            for part in re.split(r"(\*\*.+?\*\*|`.+?`)", body):
                if len(part) > 4 and part.startswith("**") and part.endswith("**"): self.put(part[2:-2], "b", pre)
                elif len(part) > 2 and part.startswith("`") and part.endswith("`"):
                    s = part[1:-1]
                    if re.fullmatch(r"[A-Za-z]:[\\/].+", s): self.put(s, "link", "code", pre, href=s); self.last_path = s
                    else: self.put(s, "code", pre)
                else: self.put_rich(part, pre)
            self.put("\n", pre)
        if code is not None: self.code_block(code)
        self.put("\n")

    def code_block(self, code):
        lang, lines = code[0], code[1:]
        body = "\n".join(lines).rstrip("\n")
        self.nblk += 1; tag = f"blk{self.nblk}"; self.blocks[tag] = body; self.last_code = body
        self.put((lang or "код") + "  ", "cbh"); self.put(" ⧉ Копировать ", "copy", href="copy:" + tag); self.put("\n", "cbh")
        for ln in lines: self.put(ln + "\n", "cb")
        self.put("\n")

    def put_rich(self, text, *tags):
        pos = 0
        for m in PATH_RE.finditer(text):
            p = m[0].rstrip(".,;:)»")
            if m.start() > pos: self.put(text[pos:m.start()], *tags)
            self.put(p, "link", *tags, href=p); self.last_path = p; pos = m.start() + len(p)
        if pos < len(text): self.put(text[pos:], *tags)

    def anchor_click(self, url):
        h = url.toString()
        if h.startswith("copy:"):
            self.copy_text(self.blocks.get(h[5:], "")); self.flash("Код скопирован", 1500)
        elif not self.open_path(h): self.flash("Файл не найден")

    # ---------- выделение, копирование, поиск ----------
    def copy_text(self, s):
        if s: QApplication.clipboard().setText(s)

    def sel_text(self):
        return self.tx.textCursor().selectedText().replace("\u2029", "\n").replace("\ufffc", "")

    def copy_sel(self): self.copy_text(self.sel_text())

    def clip(self): return QApplication.clipboard().text()

    def ctx_menu(self, pos):
        m = QMenu(self); has = bool(self.sel_text())
        href = self.tx.anchorAt(pos)
        if href and not href.startswith("copy:"):
            m.addAction("Открыть файл / папку", lambda: self.open_path(href))
            m.addAction("Показать в папке", lambda: self.open_path(href, True))
            m.addAction("Копировать путь", lambda: self.copy_text(href)); m.addSeparator()
        m.addAction("Копировать выделенное   Ctrl+C", self.copy_sel).setEnabled(has)
        m.addAction("Копировать последний ответ", lambda: self.copy_text(DETAILS_RE.sub("\n", self.last_ai)))
        m.addAction("Выделить всё   Ctrl+A", self.tx.selectAll); m.addSeparator()
        m.addAction("Озвучить выделенное", lambda: self.speak_async(self.sel_text())).setEnabled(has)
        m.addAction("Поиск по чату   Ctrl+F", self.open_find)
        m.addAction("Сохранить чат…", self.save_chat)
        m.addAction("Очистить чат   Ctrl+L", self.clear_chat)
        m.exec(self.tx.mapToGlobal(pos))

    def speak_async(self, text):
        if text.strip() and not self.busy: threading.Thread(target=self._speak_bg, args=(text.strip()[:1500],), daemon=True).start()

    def _speak_bg(self, text):
        if not self.take(): return
        try: self.say(text)
        finally: self.busy = False; self.set_state("idle")

    def open_find(self):
        self.fbar.show(); s = self.sel_text().strip()
        if s and "\n" not in s: self.fent.setText(s)
        self.fent.setFocus(); self.fent.selectAll(); self.find_update()

    def close_find(self):
        self.tx.setExtraSelections([]); self.fbar.hide(); self.tx.setFocus()

    def find_update(self, *_):
        q, sels = self.fent.text(), []
        if q:
            doc = self.tx.document(); cur = QTextCursor(doc)
            while True:
                cur = doc.find(q, cur)
                if cur.isNull(): break
                s = QTextEdit.ExtraSelection(); f = QTextCharFormat(); f.setBackground(QColor("#5a4a1a"))
                s.cursor, s.format = cur, f; sels.append(s)
        self.tx.setExtraSelections(sels)
        if q: self.tx.moveCursor(QTextCursor.MoveOperation.Start); self.find_next()

    def find_next(self):
        q = self.fent.text()
        if q and not self.tx.find(q):
            self.tx.moveCursor(QTextCursor.MoveOperation.Start); self.tx.find(q)

    def save_chat(self):
        p, _ = QFileDialog.getSaveFileName(self, "Сохранить чат", "nova_chat_" + time.strftime("%Y%m%d_%H%M") + ".txt",
                                           "Текст (*.txt);;Markdown (*.md)")
        if p:
            try: Path(p).write_text(self.chat_text(), "utf-8")
            except Exception as ex: self.put(f"Не удалось сохранить: {ex}\n", "time")

    def clear_chat(self): self.tx.clear(); self.blocks.clear()

    # ---------- таймеры, погода, скриншот и прочие умения ----------
    @staticmethod
    def beep():
        try:
            import winsound
            for f in (880, 1175, 1568): winsound.Beep(f, 180)
        except Exception: pass

    @staticmethod
    def press_key(vk, n=1):
        for _ in range(n):
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0); ctypes.windll.user32.keybd_event(vk, 0, 2, 0)

    def notify(self, text):
        for _ in range(300):
            if self.take(): break
            time.sleep(0.2)
        else: return
        try: self.say(text)
        finally: self.busy = False; self.set_state("idle")

    def fire(self, end):
        item = next((x for x in self.timers if x["end"] == end), None)
        if not item: return
        self.timers.remove(item); self.beep()
        self.notify(f"Напоминаю: {item['what']}." if item["what"] else "Таймер сработал!")

    def weather(self, city):
        cands = [city]
        if len(city) > 3 and city[-1] in "еуыи": cands += [city[:-1] + x for x in ("а", "я", "ь", "")]    # «в Москве» → «Москва»
        for q in dict.fromkeys(cands):
            try:
                r = requests.get("https://wttr.in/" + quote(q), params={"format": "%l|%C|%t|%f|%w|%h", "lang": "ru", "m": "1"},
                                 headers={"User-Agent": "curl/8.0"}, timeout=7)
            except requests.RequestException: return "Не получилось узнать погоду — проверь интернет."
            parts = [x.strip() for x in r.text.split("|")]
            if r.ok and len(parts) == 6 and "Unknown" not in r.text: break
        else: return f"Не нашла город «{city}»."
        place, cond, temp, feels, wind, hum = parts
        wind = re.sub(r"[←-⇿]", "", wind).replace("km/h", " километров в час").replace("m/s", " метров в секунду").strip()
        return (f"{place}: {cond}, {temp}, ощущается как {feels}.", f"- **Ветер:** {wind}\n- **Влажность:** {hum}")

    def capture(self, hide=True):
        """Снимок всех мониторов → (путь, None) или (None, текст ошибки)."""
        try: from PIL import ImageGrab
        except ImportError: return None, "Для скриншотов нужна библиотека Pillow: pip install pillow."
        d = known_dir("Pictures") / "Nova"; d.mkdir(parents=True, exist_ok=True)
        p = d / time.strftime("screen_%Y%m%d_%H%M%S.png")
        if hide: self.ui(self.showMinimized); time.sleep(0.7)               # прячем окно, чтобы оно не попало в кадр
        try: ImageGrab.grab(all_screens=True).save(p)
        except Exception as ex: return None, f"Не получилось сделать скриншот: {ex}"
        finally:
            if hide: self.ui(self.showNormal)
        self.last_shot = self.last_path = str(p)
        return p, None

    def ps(self, script, timeout=20):
        try: subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", script], creationflags=0x08000000, timeout=timeout, check=True); return True
        except Exception: return False

    def clip_image(self, p):      # картинка в буфер обмена: вставляется в Paint, мессенджеры, документы
        q = str(p).replace("'", "''")
        return os.name == "nt" and self.ps("Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
                                           f"$i=[System.Drawing.Image]::FromFile('{q}'); [System.Windows.Forms.Clipboard]::SetImage($i); $i.Dispose()")

    def clip_file(self, p):       # сам файл в буфер обмена: вставляется в Проводник, Telegram, Discord как вложение
        return os.name == "nt" and self.ps("Set-Clipboard -Path '" + str(p).replace("'", "''") + "'")

    def screenshot(self):
        p, err = self.capture()
        if err: return err
        tip = "Он уже в буфере обмена — вставляй через Ctrl+V." if self.clip_image(p) else "Он сохранён в файл."
        return (f"Скриншот сделан. {tip}", f"`{p}`\n\nКлик по пути открывает файл, правая кнопка — показать в папке.")

    def look(self, question=""):
        """Зрение: снимаем экран и отдаём картинку ИИ."""
        if not self.mem.cfg["vision"]: return "Зрение выключено в настройках."
        p, err = self.capture()
        if err: return err
        q = question.strip() or "Опиши, что сейчас на экране и чем я занят. Коротко и по делу."
        titles = ""
        if os.name == "nt":
            try:
                here, other = list_windows()
                titles = "\n\nОткрытые окна на этом рабочем столе: " + "; ".join(x[:70] for x in here[:20]) + (
                    "\nНа других столах: " + "; ".join(x[:70] for x in other[:15]) if other else "")
            except Exception: pass
        res = self.ask_ai(q + "\n\n(К сообщению приложен реальный снимок моего экрана — смотри на него и отвечай по нему. "
                          "Не говори, что не можешь видеть экран.)" + titles, learn=False, att={"img": [str(p)], "file": []})
        if res and titles:       # ИИ не принял картинку — хотя бы отвечаем по списку окон
            return ("Картинку ИИ принять не смог, но вот что у тебя открыто.", titles.strip().replace("; ", "\n- ").replace("Открытые окна на этом рабочем столе: ", "**На этом столе:**\n- "))
        return res

    # ---------- ссылки на файлы ----------
    def open_path(self, p, reveal=False):
        p = os.path.normpath(os.path.expandvars(os.path.expanduser(str(p).strip().strip('"`'))))
        if not os.path.exists(p): return False
        self.last_path = p
        try:
            if os.name == "nt":
                if reveal: subprocess.Popen(["explorer", "/select," + p])
                else: os.startfile(p)
            else: subprocess.Popen(["xdg-open", os.path.dirname(p) if reveal else p])
        except Exception: return False
        return True

    def flash(self, msg, ms=2500):
        def go():
            self.status.setText(msg); QTimer.singleShot(ms, lambda: self.set_state(self.state_))
        self.ui(go)

    # ---------- вложения: до 10 фото и до 10 файлов ----------
    def pick_files(self):
        ps, _ = QFileDialog.getOpenFileNames(self, f"Прикрепить фото и файлы (до {MAX_ATT} фото и {MAX_ATT} файлов)")
        if ps: self.add_att(ps)

    def add_att(self, paths):
        over = 0
        for p in paths:
            p = str(p); k = "img" if Path(p).suffix.lower() in IMG_EXT else "file"
            if p in self.att[k]: continue
            if len(self.att[k]) >= MAX_ATT: over += 1; continue
            self.att[k].append(p)
        self.refresh_att()
        if over: self.flash(f"Максимум {MAX_ATT} фото и {MAX_ATT} файлов — лишнее пропущено")

    def remove_att(self, k, p):
        if p in self.att[k]: self.att[k].remove(p)
        self.refresh_att()

    def clear_att(self): self.att = {"img": [], "file": []}; self.refresh_att()

    def refresh_att(self):
        lay = self.abar.layout()
        while lay.count():
            w = lay.takeAt(0).widget()
            if w: w.deleteLater()
        n_i, n_f = len(self.att["img"]), len(self.att["file"])
        if not (n_i or n_f): self.abar.hide(); return
        inner = QWidget(); g = QGridLayout(inner); g.setContentsMargins(0, 0, 0, 0); g.setSpacing(6)
        lb = QLabel(f"Фото {n_i}/{MAX_ATT} · Файлы {n_f}/{MAX_ATT}"); lb.setStyleSheet(f"color:{MUTE};font-size:12px;"); g.addWidget(lb, 0, 0, 1, 2)
        clr = QPushButton("Убрать все"); clr.setObjectName("chip"); clr.clicked.connect(self.clear_att); g.addWidget(clr, 0, 2)
        items = [("img", p) for p in self.att["img"]] + [("file", p) for p in self.att["file"]]
        for i, (k, p) in enumerate(items):
            nm = Path(p).name; nm = nm if len(nm) <= 16 else nm[:13] + "…"
            b = QPushButton(("🖼 " if k == "img" else "📄 ") + nm + " ✕"); b.setObjectName("chip")
            b.clicked.connect(lambda _=False, k=k, p=p: self.remove_att(k, p)); g.addWidget(b, 1 + i // 3, i % 3)
        lay.addWidget(inner); self.abar.show()

    def paste_media(self):
        """Ctrl+V в строке ввода: картинка или файлы из Проводника → вложения; обычный текст вставляется как всегда."""
        cb = QApplication.clipboard(); md = cb.mimeData()
        if md.hasUrls():
            fs = [u.toLocalFile() for u in md.urls() if u.isLocalFile() and os.path.isfile(u.toLocalFile())]
            if fs: self.add_att(fs); return True
        if md.hasImage() and not md.text().strip():
            im = cb.image()
            if not im.isNull():
                d = HOME / "attach"; d.mkdir(parents=True, exist_ok=True)
                p = d / time.strftime("paste_%Y%m%d_%H%M%S.png"); im.save(str(p)); self.add_att([p]); return True
        return False

    def put_thumb(self, p):
        im = QImage(str(p))
        if im.isNull(): self.put("🖼 " + Path(p).name, "time"); return
        im = im.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        cur = QTextCursor(self.tx.document()); cur.movePosition(QTextCursor.MoveOperation.End); cur.insertImage(im); cur.insertText(" ")

    def show_att(self, att):
        for p in att["img"]: self.put_thumb(p)
        for p in att["file"]: self.put(("  " if att["img"] else "") + "📄 " + Path(p).name, "time")
        self.put("\n")

    # ---------- автосохранение чата ----------
    def chat_text(self): return self.tx.toPlainText().replace("\ufffc", "").strip()

    def chat_files(self, d):
        return sorted((f for f in Path(d).glob("chat_*.*") if f.suffix in (".txt", ".md")), key=lambda f: f.stat().st_mtime, reverse=True)

    def autosave(self):
        c = self.mem.cfg
        if not c["autosave"]: return
        txt = self.chat_text()
        if not txt or txt == self.saved_txt: return
        try:
            d = Path(c["autosave_dir"]); d.mkdir(parents=True, exist_ok=True)
            ext = c["autosave_fmt"] if c["autosave_fmt"] in ("txt", "md") else "txt"
            p = d / f"{self.stem}.{ext}"
            body = (f"# Чат с {c['name']} — {time.strftime('%d.%m.%Y %H:%M')}\n\n" if ext == "md" else "") + txt + "\n"
            tmp = p.with_suffix(".tmp"); tmp.write_text(body, "utf-8"); os.replace(tmp, p)
            self.saved_txt = txt
            if int(c["autosave_keep"]) > 0:
                for f in self.chat_files(d)[int(c["autosave_keep"]):]: f.unlink(missing_ok=True)
        except Exception: pass

    def autosave_tick(self):
        self.autosave(); QTimer.singleShot(max(5, int(self.mem.cfg["autosave_sec"])) * 1000, self.autosave_tick)

    def restore_last(self):
        try:
            fs = self.chat_files(self.mem.cfg["autosave_dir"])
            if fs:
                self.put("— прошлый сеанс —\n", "time"); self.put(fs[0].read_text("utf-8")[-6000:].strip() + "\n", "time")
                self.put("— новый сеанс —\n\n", "time")
        except Exception: pass

    def toggle_wake(self, on=None):
        on = bool(self.wake_t.isChecked() if on is None else on); self.cfg_set("wake", on); self.conv_until = 0
        if not on: self.stop_rec.set()
        if self.state_ in ("idle", "waiting"): self.set_state("waiting" if on else "idle")

    # ---------- самообновление из GitHub ----------
    def check_update(self):
        """→ (info | None, текст ошибки). Источник: GitHub Releases; если релизов ещё нет — файл nova.py из ветки main."""
        try:
            r = requests.get(f"{API}/releases/latest", headers=UA, timeout=10)
            if r.status_code == 200:
                j = r.json(); tag = j["tag_name"]; ver = tag.lstrip("vV")
                if vtuple(ver) <= vtuple(VERSION): return None, ""
                assets = {a["name"].lower(): a["browser_download_url"] for a in j.get("assets", [])}
                if FROZEN:
                    if "nova.exe" not in assets: return None, "В релизе нет файла Nova.exe."
                    return dict(version=ver, kind="exe", url=assets["nova.exe"], sha=assets.get("nova.exe.sha256"), notes=j.get("body") or ""), ""
                return dict(version=ver, kind="py", url=assets.get("nova.py", f"{RAW}/{tag}/nova.py"), notes=j.get("body") or ""), ""
            if r.status_code == 404 and not FROZEN:
                src = requests.get(f"{RAW}/main/nova.py", headers=UA, timeout=15); src.raise_for_status()
                m = re.search(r'^VERSION\s*=\s*"([^"]+)"', src.text, re.M)
                if m and vtuple(m[1]) > vtuple(VERSION): return dict(version=m[1], kind="py", url=f"{RAW}/main/nova.py", notes=""), ""
                return None, ""
            if r.status_code == 403: return None, "GitHub временно ограничил запросы — попробую позже."
            return None, f"GitHub ответил кодом {r.status_code}."
        except requests.RequestException: return None, "Нет связи с GitHub."

    def install_update(self, info):
        """Скачивает и подменяет себя. None — всё хорошо (после этого нужно закрыться), иначе текст ошибки."""
        tmp = HOME / "update"; tmp.mkdir(parents=True, exist_ok=True)
        part = tmp / ("Nova_new.exe" if info["kind"] == "exe" else "nova_new.py"); h = hashlib.sha256()
        try:
            r = requests.get(info["url"], headers=UA, timeout=(10, 120), stream=True); r.raise_for_status()
            with open(part, "wb") as f:
                for ch in r.iter_content(1 << 16): f.write(ch); h.update(ch)
        except Exception as ex: return f"Не удалось скачать обновление: {ex}"
        if info["kind"] == "py":
            try:
                src = part.read_text("utf-8"); compile(src, "nova.py", "exec")                  # файл должен хотя бы компилироваться
                m = re.search(r'^VERSION\s*=\s*"([^"]+)"', src, re.M)
                if not m or vtuple(m[1]) <= vtuple(VERSION): return "Скачанный файл не новее текущего — не ставлю."
                shutil.copy2(SELF, str(SELF) + ".bak"); os.replace(part, SELF)
            except Exception as ex: return f"Не получилось поставить обновление: {ex}"
            subprocess.Popen([sys.executable, str(SELF), "--restarted"], cwd=str(SELF.parent))
            return None
        if part.stat().st_size < 5_000_000: return "Скачанный файл слишком маленький — отменяю."
        if info.get("sha"):
            try: want = requests.get(info["sha"], headers=UA, timeout=10).text.split()[0].lower()
            except Exception: return "Не получилось проверить контрольную сумму — отменяю."
            if want != h.hexdigest(): part.unlink(missing_ok=True); return "Контрольная сумма не совпала — обновление отменено."
        bat = tmp / "apply.bat"                  # exe нельзя заменить на ходу: батник ждёт, пока мы закроемся, и подменяет файл
        bat.write_text("@echo off\r\nchcp 65001 >nul\r\n"
                       f'for /l %%i in (1,1,60) do (\r\n  timeout /t 1 /nobreak >nul\r\n  move /Y "{part}" "{SELF}" >nul 2>&1 && goto done\r\n)\r\n'
                       f'exit /b 1\r\n:done\r\nstart "" "{SELF}"\r\n(goto) 2>nul & del "%~f0"\r\n', "utf-8")
        env = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}      # чтобы новый exe не унаследовал временную папку старого
        subprocess.Popen(["cmd", "/c", str(bat)], env=env, creationflags=0x08000008, close_fds=True)
        return None

    def update_flow(self, silent=False):
        """Проверка → подтверждение → установка → перезапуск. Возвращает текст для пользователя ('' — уже всё сказано)."""
        if not self.upd_lock.acquire(blocking=False): return "Обновление уже идёт."
        try:
            info = self.pending
            if not info:
                info, err = self.check_update()
                if err: return err
                if not info: return f"У тебя последняя версия — {VERSION}."
                self.pending = info
            if not silent and not self.confirm(f"Обновить Нову {VERSION} → {info['version']}?\nПриложение перезапустится.", force=True):
                return "Хорошо, не обновляю."
            self.flash("Скачиваю обновление…", 60000)
            err = self.install_update(info)
            if err: return err
            self.say("Обновилась. Сейчас перезапущусь."); self.ui(self.quit_app); return ""
        finally: self.upd_lock.release()

    def btn_update(self):
        def run():
            r = self.update_flow()
            if r: self.ui(self.put, r + "\n\n", "time")
        threading.Thread(target=run, daemon=True).start()

    def show_update(self, info):
        self.upd_btn.setText(f"⬆ Обновить до {info['version']}"); self.upd_btn.show()
        self.put(f"Доступно обновление {VERSION} → {info['version']}. Нажми «⬆ Обновить» вверху или скажи «обнови себя».\n\n", "time")

    def update_loop(self):
        time.sleep(8)
        while True:
            c = self.mem.cfg
            try:
                if c["auto_update"]:
                    info, _ = self.check_update()
                    if info and (not self.pending or self.pending["version"] != info["version"]):
                        self.pending = info; self.ui(self.show_update, info)
                        if c["auto_install"]: self.update_flow(silent=True)
            except Exception: pass
            time.sleep(max(1, int(c["update_hours"])) * 3600)

    def extra(self, t, raw):
        """Дополнительные команды. None — не мои; "" — выполнено молча."""
        c, d = self.mem.cfg, self.mem.d
        # обновления
        if re.search(r"проверь\s+обновлен|есть\s+(?:ли\s+)?обновлен|обновлени\w+\s+есть", t):
            info, err = self.check_update()
            if err: return err
            if not info: return f"У тебя последняя версия — {VERSION}."
            self.pending = info; self.ui(self.show_update, info)
            return f"Есть обновление до версии {info['version']}. Скажи «обнови себя», и я поставлю."
        if re.search(r"обнови\s+(?:себя|нову)|обновись|установи\s+обновлени", t): return self.update_flow()
        if re.search(r"какая\s+(?:у\s+тебя\s+)?версия|твоя\s+версия", t): return f"Моя версия {VERSION}."
        # таймеры и напоминания
        if re.search(r"(какие|покажи|сколько)\s+(у меня\s+)?(таймер|напоминан)", t):
            now = time.time(); items = [x for x in self.timers if x["end"] > now]
            if not items: return "Активных таймеров нет."
            return ("Вот активные таймеры.", "\n".join(f"- {x['what'] or 'Таймер'}: осталось {fmt_dur(x['end'] - now)}" for x in items))
        if re.search(r"(отмени|сбрось|удали|останови)\s+(все\s+)?(мои\s+)?(таймер|напоминан)", t):
            n = len(self.timers)
            for x in self.timers: x["tm"].cancel()
            self.timers.clear(); return "Отменила." if n else "Таймеров и так нет."
        # только настоящие команды: «как сделать таймер в Unity» уйдёт к ИИ, а не сюда
        if re.match(r"(?:(?:поставь|засеки|запусти|установи|заведи|включи|сделай)\s+(?:мне\s+)?)?(?:таймер|будильник)|напомни|разбуди", t):
            sec, at = parse_duration(t), ""
            if not sec and (m := re.search(r"\b(?:в|на|к)\s+(\d{1,2})[:.\s](\d{2})\b", t)) and int(m[1]) < 24 and int(m[2]) < 60:
                n_ = time.localtime()
                goal = time.mktime((n_.tm_year, n_.tm_mon, n_.tm_mday, int(m[1]), int(m[2]), 0, 0, 0, -1))
                if goal <= time.time(): goal += 86400
                sec, at = int(goal - time.time()), f"{int(m[1])}:{int(m[2]):02d}"
            if not sec: return "На сколько? Например: «таймер на 5 минут», «напомни через час позвонить маме» или «разбуди меня в 7:30»."
            if sec > 86400: return "Максимум — сутки."
            what = re.sub(DUR_RE + r"|\b(?:в|на|к)\s+\d{1,2}[:.\s]\d{2}\b", " ", t)
            what = re.sub(r"^(?:\s*(?:напомни|разбуди|поставь|засеки|запусти|таймер|будильник|меня|мне|на|через|что|пожалуйста)\b)+", "", what)
            what = re.sub(r"\s+(?:через|на|в)\s*$", "", what).strip(" ,.")
            if at and not what: what = "пора вставать"
            end = time.time() + sec; tm = threading.Timer(sec, self.fire, args=(end,)); tm.daemon = True
            self.timers.append({"end": end, "what": what, "tm": tm}); tm.start()
            if at: return f"Поставила будильник на {at}."
            return f"Напомню {what} через {fmt_dur(sec)}." if what else f"Таймер на {fmt_dur(sec)} запущен."
        # калькулятор
        if m := re.match(r"(?:посчитай|вычисли|сколько будет|реши)\s+(.+)", t):
            if (r := calc(m[1])) is not None: return f"Получается {r}."
        # погода и курс валют
        if m := re.search(r"\bпогод[аеуы]\b(?:\s+(?:в|во|на|для)\s+(.+))?$", re.sub(r"\s+(?:сегодня|сейчас|на улице|завтра)$", "", t)):
            return self.weather((m[1] or "").strip() or c["city"])
        if m := re.search(r"курс\s+(доллар\w*|бакс\w*|евро|юан\w*|фунт\w*)", t):
            code = {"д": "USD", "б": "USD", "е": "EUR", "ю": "CNY", "ф": "GBP"}[m[1][0]]
            name = {"USD": "доллар", "EUR": "евро", "CNY": "юань", "GBP": "фунт"}[code]
            try: rub = requests.get(f"https://open.er-api.com/v6/latest/{code}", timeout=8).json()["rates"]["RUB"]
            except Exception: return "Не получилось узнать курс — проверь интернет."
            return "Сейчас один " + name + " стоит примерно " + f"{rub:.1f}".replace(".", ",") + " рубля."
        # заметки
        if m := re.match(r"(?:запиши|добавь|создай|сделай)\s+заметку,?\s*(?:что\s+)?(.+)", t):
            with self.mem.lock: d["notes"] = (d.get("notes", []) + [{"t": m[1], "d": time.strftime("%d.%m %H:%M")}])[-200:]
            self.mem.save(); return "Записала."
        if re.search(r"(удали|очисти|сотри)\s+(все\s+)?заметки", t): d["notes"] = []; self.mem.save(); return "Заметки удалены."
        if re.search(r"(покажи|прочитай|какие|мои|список)\s+(мои\s+)?заметк|список заметок", t):
            n = d.get("notes", [])
            return ("Вот твои заметки.", "\n".join(f"- {x['t']} ({x['d']})" for x in n)) if n else "Заметок пока нет."
        # игры и случайности
        if re.search(r"(брось|кинь|бросай)\s+(игральн\w+\s+)?(кубик|кость)", t): return f"Выпало {random.randint(1, 6)}."
        if re.search(r"(подбрось|брось|кинь)\s+монет", t): return random.choice(["Орёл.", "Решка."])
        if m := re.search(r"случайное число(?:\s+от\s+(\d+)\s+до\s+(\d+))?", t):
            a, b = sorted((int(m[1] or 1), int(m[2] or 100))); return f"Выпало {random.randint(a, b)}."
        if m := re.match(r"выбери\s+(?:между\s+|из\s+)?(.+?)\s+или\s+(.+)", t): return f"Выбираю: {random.choice([m[1], m[2]])}."
        # буфер обмена и выделение
        if re.search(r"(прочитай|озвучь|зачитай)\s+буфер", t):
            txt = self.on_main(self.clip) or ""
            return txt.strip()[:1500] or "Буфер обмена пуст."
        if re.search(r"(прочитай|озвучь|зачитай)\s+выделенн", t):
            txt = self.on_main(self.sel_text) or ""
            return txt.strip()[:1500] or "Ничего не выделено."
        if m := re.search(r"(перескажи|объясни|переведи|исправь|улучши|сократи)\s+(?:текст\s+|код\s+)?(?:из\s+)?(буфер\w*|выделенн\w+)", t):
            src = (self.on_main(self.clip if m[2].startswith("буфер") else self.sel_text) or "").strip()
            if not src: return "Там пусто. Скопируй или выдели текст и повтори."
            inst = {"перескажи": "Кратко перескажи", "объясни": "Объясни простыми словами",
                    "переведи": "Переведи на русский (если уже на русском — на английский)", "исправь": "Исправь ошибки в",
                    "улучши": "Улучши", "сократи": "Сократи"}[m[1]]
            return self.ask_ai(f"{inst} следующий текст:\n{src[:4000]}", learn=False)
        if re.search(r"скопируй\s+(последний\s+)?код", t):
            if not self.last_code: return "Кода пока не было."
            self.on_main(lambda: self.copy_text(self.last_code)); return "Скопировала код."
        if re.search(r"скопируй\s+(последний\s+)?(ответ|текст)", t):
            if not self.last_ai: return "Пока нечего копировать."
            self.on_main(lambda: self.copy_text(DETAILS_RE.sub("\n", self.last_ai))); return "Скопировала ответ."
        if re.search(r"очисти\s+(чат|экран)", t): self.ui(self.clear_chat); return ""
        if re.search(r"сохрани\s+(чат|диалог|переписку)", t): self.ui(self.after, 50, self.save_chat); return "Выбери, куда сохранить."
        if re.search(r"(?:сделай|сними|сделать|заскринь|сфотографируй|нужен)\s+(?:мне\s+)?(?:скриншот|скрин|снимок\s+экрана|экран)|^(?:скриншот|скрин)$|заскринь", t):
            return self.screenshot()
        # управление компьютером (Windows)
        if os.name == "nt":
            if re.search(r"заблокируй\s+(компьютер|пк|экран)", t): ctypes.windll.user32.LockWorkStation(); return "Блокирую."
            if re.fullmatch(r"пауза|поставь на паузу|продолжи", t) or re.search(r"(пауза|останови|продолжи)\s+(музык|трек|видео|воспроизведен)", t):
                self.press_key(0xB3); return "Готово."
            if re.search(r"следующ\w+\s+(трек|песн\w+|композиц\w+)|переключи трек", t): self.press_key(0xB0); return "Следующий."
            if re.search(r"предыдущ\w+\s+(трек|песн\w+|композиц\w+)", t): self.press_key(0xB1); return "Предыдущий."
            if m := re.search(r"(?:компьютер|системн\w+\s+громкост\w+)\s+(громче|тише)", t):
                self.press_key(0xAF if m[1] == "громче" else 0xAE, 5); return "Готово."
            if re.search(r"заглуши компьютер|(выключи|включи) звук на компьютере", t): self.press_key(0xAD); return "Готово."
        return None

    # ---------- файлы, папки, сценарии, зрение ----------
    def where(self, s):
        for pat, v in ((r"(?:на|в)\s+(?:моём\s+|моем\s+)?(?:рабоч\w+\s+стол\w*|столе)", "Desktop"), (r"в\s+(?:папк\w+\s+)?документ\w*", "Documents"),
                       (r"в\s+(?:папк\w+\s+)?загрузк\w*", "Downloads"), (r"в\s+(?:папк\w+\s+)?(?:картинк\w*|изображени\w*)", "Pictures")):
            if m := re.search(pat, s, re.I): return (s[:m.start()] + " " + s[m.end():]).strip(), known_dir(v)
        return s, Path(self.mem.cfg["work_dir"])

    def find_files(self, name, limit=8):
        name = name.strip().strip('"«»')
        if os.path.isabs(name) and os.path.exists(name): return [name]
        low, t0, out = name.lower(), time.time(), []
        for r in [Path(self.mem.cfg["work_dir"])] + [known_dir(x) for x in ("Desktop", "Documents", "Downloads", "Pictures")]:
            base = len(r.parts)
            for d, dirs, files in os.walk(r):
                names = files + dirs
                if len(Path(d).parts) - base >= 3: dirs[:] = []
                out += [os.path.join(d, f) for f in names if low in f.lower()]
                if len(out) >= limit or time.time() - t0 > 4: return out[:limit]
        return out

    def gen_file(self, desc, p):
        p = p if p.suffix else p.with_suffix(".py")
        try:
            r = self.post_ai([{"role": "user", "content": f"Напиши код: {desc}. Целевой файл: {p.name}. Ответь ТОЛЬКО кодом одним блоком ``` без пояснений."}])
            txt = r.json()["choices"][0]["message"]["content"]
        except Exception: return "Не получилось сгенерировать код — проверь интернет."
        m = re.search(r"```[\w+#-]*\n(.*?)```", txt, re.S); code = (m[1] if m else txt).strip("\n")
        p = unique_path(p); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(code + "\n", "utf-8")
        self.last_code, self.last_path = code, str(p)
        return (f"Готово, файл {p.name} создан.", f"`{p}`\n\n```{p.suffix[1:]}\n{code[:4000]}\n```")

    # ---------- создание документов: txt / md / html / csv / docx / pdf ----------
    def ai_text(self, prompt):
        try: return self.post_ai([{"role": "user", "content": prompt}]).json()["choices"][0]["message"]["content"].strip()
        except Exception: return ""

    @staticmethod
    def html_doc(body, title="Документ"):
        ps = "".join(f"<p>{htmllib.escape(x)}</p>" for x in body.split("\n") if x.strip())
        return (f"<!doctype html><html><head><meta charset='utf-8'><title>{htmllib.escape(title)}</title></head>"
                f"<body style=\"font-family:'Segoe UI',Arial,sans-serif;font-size:14pt;line-height:1.55;margin:36px\">{ps}</body></html>")

    def write_docx(self, p, body):
        paras = "".join(f'<w:p><w:r><w:t xml:space="preserve">{htmllib.escape(x)}</w:t></w:r></w:p>' for x in body.split("\n"))
        hdr = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", hdr + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                       '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                       '<Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" '
                       'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
            z.writestr("_rels/.rels", hdr + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                       'Target="word/document.xml"/></Relationships>')
            z.writestr("word/document.xml", hdr + '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                       f"<w:body>{paras}</w:body></w:document>")

    def write_pdf(self, p, body):
        """1) печать HTML через Edge/Chrome без окна (есть на любом Windows), 2) запасной вариант — Pillow."""
        tmp = HOME / "pdf_tmp"; tmp.mkdir(parents=True, exist_ok=True)
        h = tmp / "doc.html"; h.write_text(self.html_doc(body, p.stem), "utf-8")
        pf = [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
              os.environ.get("LocalAppData", "")]
        for exe in [os.path.join(b, r) for b in pf if b for r in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe")]:
            if not os.path.exists(exe): continue
            try:
                subprocess.run([exe, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={tmp / 'profile'}",
                                f"--print-to-pdf={p}", h.as_uri()], timeout=45, capture_output=True, creationflags=0x08000000 if os.name == "nt" else 0)
            except Exception: pass
            if p.exists() and p.stat().st_size > 500: return
        from PIL import Image, ImageDraw, ImageFont
        font = None
        for f in (r"C:\Windows\Fonts\arial.ttf", "arial.ttf", "DejaVuSans.ttf"):
            try: font = ImageFont.truetype(f, 28); break
            except Exception: pass
        if font is None: raise RuntimeError("не нашла шрифт для PDF")
        import textwrap
        lines = [w for x in body.split("\n") for w in (textwrap.wrap(x, 62) or [""])]
        W, H, per = 1240, 1754, 38
        pages = []
        for i in range(0, max(1, len(lines)), per):
            im = Image.new("RGB", (W, H), "white"); dr = ImageDraw.Draw(im)
            for j, ln in enumerate(lines[i:i + per]): dr.text((100, 100 + j * 42), ln, fill="black", font=font)
            pages.append(im)
        pages[0].save(p, "PDF", resolution=150, save_all=True, append_images=pages[1:])

    def write_doc(self, p, body, ext):
        if ext == "docx": return self.write_docx(p, body)
        if ext == "pdf": return self.write_pdf(p, body)
        if ext == "html": body = self.html_doc(body, p.stem)
        p.write_text(body, encoding="utf-8-sig" if ext in ("txt", "csv") else "utf-8")

    def make_docs(self, raw):
        t = raw.lower(); kinds = []
        for pat, ext in ((r"\bpdf\b|пдф|пэ\s?дэ\s?эф", "pdf"), (r"docx|ворд|\bword\b", "docx"), (r"markdown|маркдаун|\bmd\b", "md"),
                         (r"html|веб-?страниц", "html"), (r"\bcsv\b", "csv"), (r"текстов\w+|\btxt\b|блокнот|обычн\w+\s+файл|\bфайл\b|документ", "txt")):
            if re.search(pat, t) and ext not in kinds: kinds.append(ext)
        if "txt" in kinds and len(kinds) > 1 and not re.search(r"текстов\w+|\btxt\b|блокнот", t): kinds.remove("txt")   # «файл» в «pdf файл» — не txt
        if not kinds: kinds = ["txt"]
        _, base = self.where(raw)
        m = re.search(r"(?:называ\w+|название|под\s+названием|с\s+названием|под\s+именем)\s+[«\"']?(.+?)[»\"']?(?:\s+(?:и|с|где|на|в|со)\s|[,.!]|$)", raw, re.I)
        name = safe_name(m[1]) if m else ""
        body = None
        if m := re.search(r"(?:с\s+текстом|с\s+содержимым|где\s+написано|со\s+словами|напиши\s+в\s+(?:нём|нем|него)|внутри)[:\s]+(.+)$", raw, re.I | re.S): body = m[1].strip()
        doc = getattr(self, "last_doc", None)
        if body is None and doc and re.search(r"теперь|тоже|ещё|еще|из\s+(?:него|неё|этого|того)|такой\s+же|а\s+потом|то\s+же", t):
            body, name = doc["body"], name or doc["name"]                      # «теперь сделай pdf» — берём текст прошлого файла
        if body is None:
            topic = re.search(r"(?:про|на\s+тему|о\s+том,?\s+(?:как|что))\s+(.+?)(?:\s+и\s+(?:сохрани|сделай|создай)|[.!]|$)", raw, re.I)
            body = self.ai_text("Напиши содержимое файла" + (f" на тему: {topic[1]}" if topic else " — что-нибудь короткое и приятное, 3–5 предложений")
                                + ". Выведи ТОЛЬКО текст файла на русском, без пояснений, без заголовка «Файл» и без markdown.") or "Привет! Этот файл создала Нова."
        name = name or time.strftime("Нова %Y-%m-%d %H-%M")
        made, errs = [], []
        for ext in kinds:
            p = unique_path(base / f"{name}.{ext}")
            try: p.parent.mkdir(parents=True, exist_ok=True); self.write_doc(p, body, ext); made.append(p)
            except Exception as ex: errs.append(f"{ext}: {ex}")
        if made: self.last_path = str(made[-1]); self.last_doc = {"body": body, "name": name}
        if not made: return "Не получилось создать файл: " + "; ".join(errs)
        card = "\n".join(f"- `{x}`" for x in made) + ("\n\nНе вышло: " + "; ".join(errs) if errs else "") + "\n\nКлик по пути открывает файл. Скажи «открой его»."
        return ((f"Готово, создала {len(made)} файла." if len(made) > 1 else f"Готово, создала файл {made[0].name}.") + f" Лежит здесь: {made[0].parent.name}.", card)

    def run_macro(self, name, steps):
        if self.macro_depth >= 2: return "Сценарии вызывают друг друга по кругу — останавливаюсь."
        self.macro_depth += 1; log = []
        try:
            for s in steps:
                if s == name: continue
                try: res = self.route(s)
                except Exception as ex: res = f"ошибка: {ex}"
                if isinstance(res, tuple): res = res[0]
                log.append(f"- {s} → {res or 'ок'}"); time.sleep(0.8)
        finally: self.macro_depth -= 1
        return (f"Сценарий «{name}» выполнен.", "\n".join(log))

    def confirm(self, msg, force=False):
        if not force and not self.mem.cfg["confirm_actions"]: return True

        def ask():
            self.show_front()
            return QMessageBox.question(self, "Подтверждение", msg) == QMessageBox.StandardButton.Yes
        return bool(self.on_main(ask, timeout=90))

    def extra2(self, t, raw):
        """Файлы, папки, поиск, сценарии, зрение, список окон. None — не мои."""
        c, d = self.mem.cfg, self.mem.d
        r_ = re.sub(r"^\s*(?:эй\s+)?" + re.escape(c["name"]) + r"[, ]+", "", raw.strip(), flags=re.I)
        if re.fullmatch(r"(стоп|отбой|хватит|достаточно|отмена)", t): self.conv_until = 0; return "Хорошо, я на связи."
        if re.fullmatch(r"(спасибо|благодарю|спасибо большое)", t): self.conv_until = 0; return "Всегда пожалуйста!"
        # сценарии: «создай сценарий работа: открой дискорд, открой хром» → потом просто «работа»
        mac = d.setdefault("macros", {})
        if t in mac: return self.run_macro(t, mac[t])
        if m := re.match(r"(?:выполни|запусти|включи)\s+(?:сценарий|макрос)\s+(.+)", t):
            return self.run_macro(m[1], mac[m[1]]) if m[1] in mac else f"Не нашла сценарий «{m[1]}»."
        if m := re.match(r"(?:создай|добавь|сохрани)\s+(?:сценарий|макрос)\s+(.+?)\s*(?::|—|\s-\s|\sэто\s)\s*(.+)", t):
            steps = [s.strip() for s in re.split(r"\s*(?:;|,|\bпотом\b|\bзатем\b)\s*", m[2]) if s.strip()]
            if not steps: return "Какие шаги? Например: «создай сценарий работа: открой дискорд, открой хром»."
            with self.mem.lock: mac[m[1].strip()] = steps
            self.mem.save(); return f"Сценарий «{m[1].strip()}» сохранён, шагов: {len(steps)}. Чтобы запустить, скажи «{m[1].strip()}»."
        if re.search(r"(мои|покажи|список)\s+(мои\s+)?(сценарии|макросы)", t):
            return ("Вот твои сценарии.", "\n".join(f"- **{k}:** {', '.join(v)}" for k, v in mac.items())) if mac else "Сценариев пока нет."
        if m := re.match(r"(?:удали|убери)\s+(?:сценарий|макрос)\s+(.+)", t):
            if m[1] in mac: del mac[m[1]]; self.mem.save(); return "Удалила."
            return "Такого сценария нет."
        # папки и пути
        if (m := re.match(r"(?:открой|покажи|зайди в)\s+(?:мне\s+)?(?:папку\s+)?(?:мои\s+)?(загрузки|документы|рабочий стол|картинки|изображения|музыку?|видео|скриншоты)"
                          r"(?:\s+пожалуйста)?$", t)) and t != "покажи рабочий стол":      # «покажи рабочий стол» = свернуть окна
            top, _, rest = KNOWN[m[1]].partition("/")
            return f"Открываю {m[1]}." if self.open_path(known_dir(top) / rest) else "Такой папки ещё нет."
        if re.match(r"(?:открой|покажи)\s+(?:папку\s+нова|рабочую\s+папку|мои\s+файлы)$", t):
            Path(c["work_dir"]).mkdir(parents=True, exist_ok=True); return "Открываю." if self.open_path(c["work_dir"]) else "Не получилось."
        if re.match(r"(?:открой|покажи)\s+(?:папку\s+)?(?:сохран\w+\s+чат\w*|папку\s+чатов)$", t):
            Path(c["autosave_dir"]).mkdir(parents=True, exist_ok=True); return "Открываю." if self.open_path(c["autosave_dir"]) else "Не получилось."
        if re.fullmatch(r"(?:открой|запусти|покажи|открой-ка)\s+(?:мне\s+)?(?:этот|тот|последний|последнюю|его|её|ещё раз)?\s*"
                        r"(?:файл|скриншот|скрин|снимок|картинку|путь|документ|результат|созданный файл)?(?:\s+пожалуйста)?", t) and re.search(
                r"этот|тот|последн|его|её|файл|скриншот|скрин|снимок|картинк|путь|документ|результат", t):
            shot = bool(re.search(r"скриншот|скрин|снимок|картинк", t))
            p = (self.last_shot or "") if shot else (self.last_path or self.last_shot)
            if shot and not p:                                           # после перезапуска: берём самый свежий скриншот из папки
                fs = sorted((known_dir("Pictures") / "Nova").glob("screen_*.png"), reverse=True)
                p = str(fs[0]) if fs else ""
            return ("Открываю." if self.open_path(p) else "Файл не открылся — возможно, его уже удалили.") if p else "Я пока ничего не создавала и не показывала."
        if re.search(r"(?:открой|покажи)\s+(?:файл\s+|путь\s+|картинку\s+|скриншот\s+)?(?:из|в)\s+буфер\w*", t):
            clip = (self.on_main(self.clip) or "").strip()
            m = PATH_RE.search(clip)
            return "Открываю." if m and self.open_path(m[0].rstrip(".,;:)")) else "В буфере обмена нет пути к существующему файлу."
        if re.search(r"(?:опиши|что\s+на|посмотри\s+на)\s+(?:эту\s+)?(?:картинк\w*|фото\w*|изображени\w*|скриншот\w*).*(?:в|из)\s+буфер\w*", t):
            def grab():
                im = QApplication.clipboard().image()
                if im.isNull(): return None
                (HOME / "attach").mkdir(parents=True, exist_ok=True)
                p = HOME / "attach" / time.strftime("clip_%Y%m%d_%H%M%S.png"); im.save(str(p)); return str(p)
            p = self.on_main(grab)
            if not p: return "В буфере обмена нет картинки."
            return self.ask_ai(r_ if len(r_) > 25 else "Подробно опиши, что на этой картинке.", learn=False, att={"img": [p], "file": []})
        if re.search(r"покажи\s+(?:его\s+|файл\s+)?в\s+папке|где\s+(?:он|файл)\s+лежит", t):
            return "Показываю." if self.last_path and self.open_path(self.last_path, True) else "Пока нечего показывать."
        if m := re.match(r"(?:открой|запусти)\s+([a-z]:\\.+)$", t): return "Открываю." if self.open_path(m[1]) else "Такого пути нет."
        if re.fullmatch(r"скопируй\s+(?:этот\s+)?путь", t): self.on_main(lambda: self.copy_text(self.last_path)); return "Путь скопирован."
        if m := re.match(r"скопируй\s+(?:последний\s+)?скриншот(?:\s+(как файл))?$|скопируй\s+(?:этот\s+)?файл$", t):
            p = self.last_shot if "скриншот" in t else self.last_path
            if not p: return "Нечего копировать."
            ok = self.clip_file(p) if ("как файл" in t or "скриншот" not in t) else self.clip_image(p)
            return "Скопировала, вставляй через Ctrl+V." if ok else "Не получилось скопировать."
        # создание и чтение файлов (по умолчанию — папка из настроек, можно «на рабочем столе», «в документах»)
        if (re.search(r"(?:создай|сделай|напиши|сохрани|оформи|подготовь|накидай|запиши)\b.{0,80}?(?:файл|документ|pdf|пдф|docx|ворд|\bword\b|\btxt\b)", t)
                and not re.search(r"сценари|макрос|\bкод\b|скрипт|программ|сайт|страниц|ответ|\bчат|диалог|переписк|(?:создай|сделай)\s+(?:новую\s+)?папк", t)):
            return self.make_docs(r_)
        r2, base = self.where(r_)
        if m := re.match(r"(?:создай|сделай)\s+папку\s+(.+)$", r2, re.I):
            p = unique_path(base / safe_name(m[1])); p.mkdir(parents=True, exist_ok=True); self.last_path = str(p)
            return ("Папка создана.", f"`{p}`")
        if m := re.match(r"(?:создай|сделай)\s+(?:пустой\s+)?(?:текстовый\s+)?(?:файл|документ)\s+(.+?)(?:\s+(?:с\s+текстом|с\s+содержимым|где\s+написано)\s+(.+))?$", r2, re.I | re.S):
            p = base / safe_name(m[1]); p = unique_path(p if p.suffix else p.with_suffix(".txt"))
            p.parent.mkdir(parents=True, exist_ok=True); p.write_text(m[2] or "", "utf-8"); self.last_path = str(p)
            return (f"Файл {p.name} создан.", f"`{p}`")
        if m := re.match(r"допиши\s+в\s+файл\s+([^:]+):\s*(.+)$", r2, re.I | re.S):
            fs = self.find_files(m[1])
            if not fs: return f"Файл «{m[1].strip()}» не нашла."
            with open(fs[0], "a", encoding="utf-8") as f: f.write("\n" + m[2].strip() + "\n")
            self.last_path = fs[0]; return ("Дописала.", f"`{fs[0]}`")
        if m := re.match(r"сохрани\s+(?:последний\s+)?(код|ответ)\s+(?:в\s+файл\s+)?(.+)$", r2, re.I):
            code = m[1].lower() == "код"; body = self.last_code if code else DETAILS_RE.sub("\n", self.last_ai)
            if not body: return "Пока нечего сохранять."
            p = base / safe_name(m[2]); p = unique_path(p if p.suffix else p.with_suffix(".py" if code else ".txt"))
            p.parent.mkdir(parents=True, exist_ok=True); p.write_text(body + "\n", "utf-8"); self.last_path = str(p)
            return (f"Сохранила в {p.name}.", f"`{p}`")
        if m := re.match(r"(?:напиши|создай|сделай)\s+(?:мне\s+)?(?:код|скрипт|программу|страницу|сайт)\s+(.+?)\s+(?:и\s+)?(?:сохрани\s+)?в\s+файл\s+(.+)$", r2, re.I | re.S):
            return self.gen_file(m[1], base / safe_name(m[2]))
        if m := re.match(r"(?:прочитай|покажи\s+содержимое|что\s+в)\s+файл\w*\s+(.+)$", t):
            fs = self.find_files(m[1])
            if not fs: return f"Файл «{m[1]}» не нашла."
            txt = read_file_text(fs[0], 3000); self.last_path = fs[0]
            return ("Вот содержимое файла.", f"`{fs[0]}`\n\n```\n{txt}\n```") if txt else "Этот тип файла я прочитать не могу."
        if m := re.match(r"(?:открой|запусти)\s+файл\s+(.+)$", t):
            fs = self.find_files(m[1]); return "Открываю." if fs and self.open_path(fs[0]) else f"Не нашла файл «{m[1]}»."
        if m := re.match(r"(?:найди|поищи)\s+(?:мой\s+)?файл\w*\s+(.+)$", t):
            fs = self.find_files(m[1])
            if not fs: return f"Файлов «{m[1]}» не нашла."
            self.last_path = fs[0]; return (f"Нашла: {len(fs)}.", "\n".join(f"- `{f}`" for f in fs))
        # зрение и окна
        if m := re.match(r"(?:посмотри|глянь|взгляни)\s+на\s+(?:мой\s+)?экран(?:\s+и\s+(.+))?$", t): return self.look(m[1] or "")
        if (re.search(r"экран\w*|монитор\w*|дисплей\w*|рабоч\w+\s+стол\w*|что\s+ты\s+видишь", t)
                and re.search(r"видиш|вижу|посмотри|глянь|взгляни|опиши|прочитай|что\s+(?:у\s+меня\s+)?(?:сейчас\s+)?(?:на|происходит|там)|что\s+ты\s+видишь", t)
                and not re.search(r"сделай|создай|открой|перейди|переключ|сверни|скриншот|закрой|покажи\s+рабоч", t)):
            return self.look(r_)
        if re.search(r"какие\s+(?:окна|программы|приложения)\s+открыты|что\s+(?:у\s+меня\s+)?открыто|список\s+окон|что\s+запущено", t):
            if os.name != "nt": return "Список окон работает только в Windows."
            here, other = list_windows(); q = lambda s: s[:80].replace("`", "'")
            L = ["**На этом рабочем столе:**"] + [f"- {q(x)}" for x in here[:25]]
            if other: L += ["", "**На других столах:**"] + [f"- {q(x)}" for x in other[:25]]
            return (f"Открыто окон: {len(here)} на этом столе и {len(other)} на других.", "\n".join(L))
        return None

    # ---------- мышь, клавиатура, рабочие столы, система ----------
    def act(self, fn, msg):
        if not self.mem.cfg["allow_control"]: return "Управление мышью и клавиатурой выключено в настройках."
        fn(); return msg

    def type_text(self, s):
        old = self.on_main(self.clip) or ""
        self.on_main(lambda: self.copy_text(s)); time.sleep(0.15)
        key_combo(0x11, 0x56); time.sleep(0.3)
        if old: self.on_main(lambda: self.copy_text(old))

    def desk(self, step): key_combo(0x5B, 0x11, 0x27 if step > 0 else 0x25); time.sleep(0.3)

    def desk_to(self, n):
        for _ in range(12): key_combo(0x5B, 0x11, 0x25); time.sleep(0.12)
        for _ in range(max(0, min(n, 9) - 1)): key_combo(0x5B, 0x11, 0x27); time.sleep(0.2)

    def extra3(self, t, raw):
        c = self.mem.cfg
        if os.name != "nt": return None
        r_ = re.sub(r"^\s*(?:эй\s+)?" + re.escape(c["name"]) + r"[, ]+", "", raw.strip(), flags=re.I)
        # рабочие столы: смена, создание, закрытие, обзор
        if re.fullmatch(r"(?:сверни|скрой)\s+(?:все\s+)?окна|сверни всё|покажи\s+рабочий\s+стол", t): return self.act(lambda: key_combo(0x5B, 0x44), "Свернула всё.")
        if re.search(r"обзор\s+задач|все\s+(?:рабочие\s+)?столы|покажи\s+столы", t): return self.act(lambda: key_combo(0x5B, 0x09), "Показываю все столы.")
        if re.search(r"закрой\s+(?:этот\s+)?(?:виртуальный\s+)?(?:рабочий\s+)?стол\b", t):
            return self.act(lambda: key_combo(0x5B, 0x11, 0x73), "Закрываю рабочий стол.") if self.confirm("Закрыть текущий виртуальный рабочий стол? Окна уедут на соседний.") else "Не закрываю."
        if re.search(r"(?:создай|добавь|открой)\s+(?:новый\s+)?(?:виртуальный\s+)?(?:рабочий\s+)?стол\b|новый\s+(?:виртуальный\s+)?(?:рабочий\s+)?стол\b", t):
            return self.act(lambda: key_combo(0x5B, 0x11, 0x44), "Создала новый рабочий стол.")
        if m := re.search(r"(следующ\w+|предыдущ\w+|прошл\w+|левый|правый)\s+(?:рабочий\s+)?стол\b", t):
            return self.act(lambda: self.desk(1 if m[1].startswith(("след", "прав")) else -1), "Переключаю.")
        if m := re.search(r"(?:свайп\w*|пролистни|переключись|перейди)\s+(?:на\s+)?(?:рабочий\s+стол\s+)?(влево|вправо|назад|вперёд|вперед)", t):
            return self.act(lambda: self.desk(1 if m[1] in ("вправо", "вперёд", "вперед") else -1), "Готово.")
        if m := re.search(r"стол\s+(?:номер\s+)?(\d)\b|\b(\d)(?:-?й)?\s+(?:рабочий\s+)?стол\b", t):
            return self.act(lambda: self.desk_to(int(m[1] or m[2])), f"Перехожу на стол {m[1] or m[2]}.")
        o = {"перв": 1, "втор": 2, "трет": 3, "четв": 4, "пят": 5, "шест": 6}
        if m := re.search(r"(перв|втор|трет|четв|пят|шест)\w*\s+(?:рабочий\s+)?стол\b", t):
            return self.act(lambda: self.desk_to(o[m[1]]), f"Перехожу на стол {o[m[1]]}.")
        # окна
        if re.fullmatch(r"закрой\s+(?:это\s+|текущее\s+)?окно", t): return self.act(lambda: key_combo(0x12, 0x73), "Закрываю окно.")
        if re.fullmatch(r"сверни\s+(?:это\s+)?окно", t): return self.act(lambda: (key_combo(0x5B, 0x28), time.sleep(0.25), key_combo(0x5B, 0x28)), "Свернула.")
        if re.fullmatch(r"разверни\s+(?:это\s+)?окно|окно\s+на\s+весь\s+экран", t): return self.act(lambda: key_combo(0x5B, 0x26), "Развернула.")
        if m := re.search(r"(?:прижми\s+)?окно\s+(влево|вправо)", t): return self.act(lambda: key_combo(0x5B, 0x25 if m[1] == "влево" else 0x27), "Готово.")
        if re.search(r"(?:переключись|перейди)\s+(?:на\s+)?(?:другое|предыдущее|прошлое)\s+окно|альт\s*таб", t): return self.act(lambda: key_combo(0x12, 0x09), "Переключаю.")
        # мышь и клавиатура
        if re.fullmatch(r"(?:кликни|клик|щёлкни|щелкни|нажми)(?:\s+мышкой)?", t): return self.act(lambda: mouse_click(), "Клик.")
        if re.search(r"правый\s+клик|кликни\s+правой|правой\s+кнопкой", t): return self.act(lambda: mouse_click("right"), "Правый клик.")
        if re.search(r"двойной\s+клик|кликни\s+дважды|дважды\s+кликни", t): return self.act(lambda: mouse_click("left", 2), "Двойной клик.")
        if m := re.search(r"(?:подвинь|сдвинь|передвинь|двигай)\s+(?:мышь|мышку|курсор)\s+(вверх|вниз|влево|вправо)(?:\s+на\s+(\d+))?", t):
            n = int(m[2] or 200); dx, dy = {"вверх": (0, -n), "вниз": (0, n), "влево": (-n, 0), "вправо": (n, 0)}[m[1]]
            return self.act(lambda: mouse_move(max(0, mouse_pos()[0] + dx), max(0, mouse_pos()[1] + dy)), "Готово.")
        if m := re.search(r"(?:мышь|мышку|курсор)\s+(?:в|на)\s+(центр|левый верхний угол|правый верхний угол|левый нижний угол|правый нижний угол)", t):
            w, h = screen_size()
            pts = {"центр": (w // 2, h // 2), "левый верхний угол": (5, 5), "правый верхний угол": (w - 5, 5),
                   "левый нижний угол": (5, h - 5), "правый нижний угол": (w - 5, h - 5)}
            return self.act(lambda: mouse_move(*pts[m[1]]), "Готово.")
        if m := re.search(r"(?:кликни|нажми)\s+(?:в|по)\s+(?:точк\w+\s+)?(\d+)[,\s]+(\d+)", t):
            return self.act(lambda: (mouse_move(int(m[1]), int(m[2])), time.sleep(0.1), mouse_click()), "Кликнула.")
        if m := re.search(r"(?:прокрути|скролль|пролистай)\s+(вниз|вверх)(?:\s+на\s+(\d+))?", t):
            return self.act(lambda: mouse_wheel((-120 if m[1] == "вниз" else 120) * int(m[2] or 5)), "Прокручиваю.")
        if re.search(r"где\s+(?:мышь|мышка|курсор)", t): x, y = mouse_pos(); return f"Курсор в точке {x}, {y}."
        if m := re.match(r"(?:напечатай|набери|введи|впиши)\s+(.+)$", r_, re.I | re.S): return self.act(lambda: self.type_text(m[1]), "Напечатала.")
        if m := re.match(r"нажми\s+(.+)$", t):
            names = [x for x in re.split(r"\s*\+\s*|\s+плюс\s+|\s+", re.sub(r"\b(?:кнопку|клавишу|клавиши|на)\b", " ", m[1]).strip()) if x]
            vks = [vk_of(x) for x in names]
            if not names or None in vks:
                bad = names[vks.index(None)] if None in vks else ""
                return f"Не знаю клавишу «{bad}». Клики по надписям на экране я пока не умею — зато могу «кликни в точке 500 300» или «нажми ctrl+shift+esc»."
            return self.act(lambda: key_combo(*vks), "Нажала " + "+".join(names) + ".")
        # система
        if m := re.search(r"(?:громкость|звук)\s+(?:компьютера|системы|на компьютере|windows)\s+(?:на\s+)?(\d+)", t):
            n = max(0, min(100, int(m[1]))); return self.act(lambda: (self.press_key(0xAE, 50), self.press_key(0xAF, round(n / 2))), f"Громкость {n}.")
        if m := re.search(r"яркость\s+(?:экрана\s+)?(?:на\s+)?(\d+)", t):
            n = max(0, min(100, int(m[1])))
            ok = self.ps(f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{n})")
            return f"Яркость {n} процентов." if ok else "Не получилось: яркость так меняется только на ноутбуках."
        if re.search(r"проверь\s+интернет|есть\s+(?:ли\s+)?интернет|пинг", t):
            t0 = time.time()
            try: requests.get("https://www.google.com/generate_204", timeout=5)
            except Exception: return "Интернета нет или он очень нестабильный."
            return f"Интернет работает, отклик около {int((time.time() - t0) * 1000)} миллисекунд."
        if re.search(r"(?:какой|мой|узнай)\s+(?:у\s+меня\s+)?(?:ip|айпи)", t):
            import socket
            try: ext = requests.get("https://api.ipify.org", timeout=6).text.strip()
            except Exception: ext = "не удалось узнать"
            try: loc = socket.gethostbyname(socket.gethostname())
            except Exception: loc = "?"
            return (f"Внешний айпи: {ext}.", f"- **Внешний:** `{ext}`\n- **Локальный:** `{loc}`")
        if re.search(r"к\s+какому\s+(?:wi-?fi|вайфаю|вай-фаю)|какой\s+(?:у\s+меня\s+)?(?:wi-?fi|вайфай)", t):
            try:
                out = subprocess.check_output(["netsh", "wlan", "show", "interfaces"], text=True, errors="ignore", creationflags=0x08000000, timeout=8)
                s = re.search(r"^\s*SSID\s*:\s*(.+)$", out, re.M)
                return f"Ты подключён к сети {s[1].strip()}." if s else "Wi-Fi сейчас не подключён."
            except Exception: return "Не получилось узнать сеть."
        if m := re.match(r"открой\s+настройки\s+(\S+)", t):
            if m[1] in SETTINGS_PAGES: os.startfile("ms-settings:" + SETTINGS_PAGES[m[1]]); return "Открываю настройки."
        if m := re.match(r"(?:закрой|завершить|убей|останови)\s+(?:программу\s+|приложение\s+|процесс\s+)?(.+)$", t):
            name = ALIASES.get(m[1].strip(), m[1].strip()).lower().replace(".exe", "")
            safe = {"explorer", "winlogon", "csrss", "system", "svchost", "lsass", "services", "dwm", "wininit", "smss"}
            procs = [p for p in psutil.process_iter(["name"]) if name in (p.info["name"] or "").lower() and p.pid != os.getpid()
                     and (p.info["name"] or "").lower().replace(".exe", "") not in safe]
            if not procs: return f"Не вижу запущенной программы «{m[1]}»."
            if not c["allow_power"]: return "Закрытие программ выключено в настройках."
            names = sorted({p.info["name"] for p in procs})
            if not self.confirm(f"Закрыть: {', '.join(names)}?\nНесохранённые данные могут пропасть."): return "Хорошо, не закрываю."
            for p in procs:
                try: p.terminate()
                except Exception: pass
            return f"Закрыла: {', '.join(names)}."
        if m := re.search(r"(выключи|перезагрузи)\s+(?:компьютер|пк)(?:\s+через\s+(\d+)\s*(мин\w*|час\w*))?", t):
            if not c["allow_power"]: return "Управление питанием выключено в настройках."
            sec = max(10, int(m[2]) * (3600 if m[3].startswith("час") else 60)) if m[2] else 10
            if not self.confirm(f"{'Выключить' if m[1] == 'выключи' else 'Перезагрузить'} компьютер через {fmt_dur(sec)}?", force=True): return "Хорошо, не трогаю."
            subprocess.run(["shutdown", "/s" if m[1] == "выключи" else "/r", "/t", str(sec)], creationflags=0x08000000)
            return f"Через {fmt_dur(sec)}. Передумаешь — скажи «отмени выключение»."
        if re.search(r"отмени\s+(?:выключение|перезагрузку)", t): subprocess.run(["shutdown", "/a"], creationflags=0x08000000); return "Отменила."
        if re.search(r"спящий\s+режим|усыпи\s+компьютер|режим\s+сна", t):
            if not c["allow_power"]: return "Управление питанием выключено в настройках."
            if not self.confirm("Перевести компьютер в спящий режим?", force=True): return "Хорошо."
            subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]); return "Спокойной ночи."
        if re.search(r"выйди\s+из\s+(?:системы|учётки|учетки)", t):
            if not c["allow_power"]: return "Управление питанием выключено в настройках."
            if not self.confirm("Выйти из учётной записи Windows?", force=True): return "Хорошо."
            subprocess.run(["shutdown", "/l"], creationflags=0x08000000); return "Выхожу."
        if re.search(r"очисти\s+корзину", t):
            if not c["allow_power"]: return "Это выключено в настройках."
            if not self.confirm("Очистить корзину? Файлы удалятся без возможности восстановления.", force=True): return "Хорошо, не трогаю."
            return "Корзина очищена." if self.ps("Clear-RecycleBin -Force -ErrorAction SilentlyContinue") else "Не получилось очистить."
        if m := re.match(r"(?:выполни|запусти)\s+команду\s+(.+)$", r_, re.I | re.S):
            if not c["allow_shell"]: return "Команды терминала выключены. Включи «Разрешить команды терминала» в настройках."
            cmd = m[1].strip()
            if not self.confirm(f"Выполнить команду в терминале?\n\n{cmd}", force=True): return "Не выполняю."
            try: out = subprocess.run(cmd, shell=True, capture_output=True, text=True, errors="ignore", timeout=30, creationflags=0x08000000, cwd=str(Path.home()))
            except subprocess.TimeoutExpired: return "Команда шла дольше 30 секунд — остановила."
            return (f"Готово, код {out.returncode}.", "```\n" + (((out.stdout or "") + (out.stderr or "")).strip() or "(пусто)")[:3000] + "\n```")
        return None

    # ---------- голос ----------
    def do_skip(self):
        self.speaker.skip.set(); self.stop_rec.set()
        try: pygame.mixer.music.stop()
        except Exception: pass

    def say(self, speak, card=None):
        sp = self.speaker; sp.begin()
        try:
            for s in split_long(sentences(speak)): sp.feed(s)
        finally: sp.end(card)

    # ---------- ввод ----------
    def on_enter(self):
        text, att = self.entry.text().strip(), self.att
        if not text and not (att["img"] or att["file"]): return
        self.entry.clear(); self.att = {"img": [], "file": []}; self.refresh_att()
        threading.Thread(target=self.send, args=(text or "Посмотри вложения и расскажи, что в них.", att), daemon=True).start()

    def send(self, text, att=None):
        """Текст из строки ввода: прерывает прослушивание, чтобы напечатанное не потерялось."""
        self.hold = True
        try:
            if self.busy and self.state_ in ("waiting", "listening"):
                self.stop_rec.set()
                for _ in range(40):
                    if not self.busy: break
                    time.sleep(0.1)
            self.pipeline(text, att)
        finally: self.hold = False

    def start_voice(self):
        if self.mem.cfg["wake"] and not self.busy and self.state_ == "waiting":      # клик по шару = «говори сейчас, имя не нужно»
            self.conv_until = time.time() + 15; self.flash("Слушаю — имя говорить не нужно", 4000); return
        threading.Thread(target=self.pipeline, daemon=True).start()

    # ---------- отклик на имя ----------
    def strip_name(self, text):
        c = self.mem.cfg
        names = {c["name"].strip().lower()} | {x.strip().lower() for x in re.split(r"[,;]", c["wake_aliases"]) if x.strip()}
        words = text.split()

        def close(s, n): return s == n or SequenceMatcher(None, s, n).ratio() >= (0.9 if len(n) <= 5 else 0.82)   # «нового» ≠ «нова»
        for i, w in enumerate(words[:3]):
            one = re.sub(r"\W", "", w.lower())
            two = one + re.sub(r"\W", "", words[i + 1].lower()) if i + 1 < len(words) else ""      # «но ва» → «нова»
            for s, used in ((one, 1), (two, 2)):
                if s and any(close(s, n) for n in names if n):
                    return " ".join(words[i + used:]).lstrip(" ,.!?-—:"), True
        return text, False

    @staticmethod
    def chime():
        try:
            import winsound; winsound.Beep(1320, 70); winsound.Beep(1760, 70)
        except Exception: pass

    def wake_loop(self):
        """Фоновое прослушивание одним открытым потоком: фон шума — скользящий минимум, фразы режутся по паузам и
        распознаются в отдельном потоке. Так не теряется начало фразы и ничего не нужно нажимать."""
        while True:
            try:
                if not self.mem.cfg["wake"]: time.sleep(0.3); continue
                self.wake_stream()
            except Exception as e:
                if time.time() - self._werr > 60: self._werr = time.time(); self.ui(self.put, f"Микрофон недоступен: {e}\n\n", "time")
                time.sleep(4)

    def wake_stream(self):
        rate, block = 16000, 800
        pre, frames, floor = deque(maxlen=8), [], deque(maxlen=80)
        started, silent, voiced = False, 0, 0
        if self.state_ == "idle": self.set_state("waiting")
        with sd.InputStream(samplerate=rate, channels=1, dtype="int16", blocksize=block, device=self.mic_index()) as st:
            while self.mem.cfg["wake"]:
                data, _ = st.read(block); x = data[:, 0].copy(); c = self.mem.cfg
                rms = float(np.sqrt(np.mean(x.astype(np.float32) ** 2)))
                if self.busy or self.hold or self.state_ == "speaking" or time.time() - self.last_end < 0.8:
                    pre.clear(); frames, started, silent, voiced = [], False, 0, 0; continue       # пока Нова говорит или думает — не слушаем
                self.level = min(rms / 3000, 1)
                if not started: floor.append(rms)
                thr = max((float(np.percentile(floor, 25)) if len(floor) > 8 else rms) * c["mic_sens"], 300)
                if rms > thr:
                    if not started: frames, started = list(pre), True
                    silent, voiced = 0, voiced + 1
                elif started: silent += 1
                (frames if started else pre).append(x)
                need = max(4, int(c["silence"] * rate / block))
                if started and (silent > need or len(frames) * block / rate > c["max_rec"]):
                    if voiced >= 3:
                        audio = sr.AudioData(np.concatenate(frames).tobytes(), rate, 2)
                        threading.Thread(target=self.pipeline, kwargs=dict(wake=True, audio=audio), daemon=True).start()
                    frames, started, silent, voiced = [], False, 0, 0; pre.clear()

    def mic_index(self):
        name = self.mem.cfg.get("mic")
        if not name or name == MIC_DEFAULT: return None
        try:
            for i, d in enumerate(sd.query_devices()):
                if d["max_input_channels"] > 0 and d["name"] == name: return i
        except Exception: pass
        return None

    def record(self, wait=None):
        c = self.mem.cfg; rate, block = 16000, 800
        wait = wait or c["wait_speech"]
        need_sil = max(4, int(c["silence"] * rate / block))
        pre, frames, noise = deque(maxlen=6), [], []
        started, silent, thr, t0 = False, 0, 400.0, time.time()
        self.stop_rec.clear()
        with sd.InputStream(samplerate=rate, channels=1, dtype="int16", blocksize=block, device=self.mic_index()) as st:
            while not self.stop_rec.is_set():
                data, _ = st.read(block); x = data[:, 0].copy()
                rms = float(np.sqrt(np.mean(x.astype(np.float32) ** 2))); self.level = min(rms / 3000, 1)
                if len(noise) < 6: noise.append(rms); thr = max(np.mean(noise) * c["mic_sens"], 350); continue
                if rms > thr:
                    if not started: frames = list(pre)
                    started, silent = True, 0
                elif started: silent += 1
                (frames if started else pre).append(x)
                if started and silent > need_sil: break
                if not started and time.time() - t0 > wait: frames = []; break
                if time.time() - t0 > c["max_rec"]: break
        self.level = 0
        if self.stop_rec.is_set() or not frames: return None
        return sr.AudioData(np.concatenate(frames).tobytes(), rate, 2)

    def pipeline(self, text=None, att=None, wake=False, audio=None):
        if not self.take(): return                # атомарная проверка: две фразы подряд больше не запускают два конвейера
        voice = text is None; failed = False; c = self.mem.cfg
        self.silent = not voice and not c["speak_typed"]
        try:
            if voice:
                if audio is None:
                    self.set_state("waiting" if wake and time.time() >= self.conv_until else "listening")
                    audio = self.record(wait=4 if wake else None)
                    if audio is None: return
                self.set_state("thinking")
                try: text = self.rec.recognize_google(audio, language=c["lang"])
                except sr.UnknownValueError:
                    if not wake: self.say("Не расслышала, повтори, пожалуйста.")
                    return
                except sr.RequestError:
                    if wake: time.sleep(3)
                    else: self.say("Нет связи с сервисом распознавания речи.")
                    return
                if wake:
                    text, hit = self.strip_name(text)
                    if not hit and time.time() >= self.conv_until: return          # это не мне — молчим
                    if hit and c["wake_chime"]: self.chime()
                    if not text.strip():
                        self.ui(self.user_msg, c["name"] + "?"); self.say("Слушаю."); return
            self.ui(self.user_msg, text, att); self.mem.request(text); self.set_state("thinking")
            has_att = bool(att and (att["img"] or att["file"]))
            res = self.ask_ai(text, att=att) if has_att else self.route(text)
            if isinstance(res, tuple): self.say(*res)
            elif res: self.say(res)
        except Exception as e:
            failed = True
            if not wake or time.time() - self._werr > 60:
                self._werr = time.time(); self.ui(self.put, f"Ошибка: {e}\n\n", "time")
            if wake: time.sleep(3)
        finally:
            self.busy = False; self.silent = False
            self.set_state("waiting" if c["wake"] else "idle")
            if voice and not failed and (wake or c["auto"]) and c["conv_window"] > 0 and self.last_end >= time.time() - 5:
                self.conv_until = time.time() + c["conv_window"]       # после ответа можно продолжать без имени
            if voice and not wake and not failed and c["auto"] and not self.stop_rec.is_set():
                self.ui(self.after, 300, self.start_voice)

    # ---------- команды ----------
    def tweak(self, key, delta, lo, hi, msg):
        self.cfg_set(key, max(lo, min(hi, int(self.mem.cfg[key]) + delta))); return msg

    def route(self, raw):
        n = re.escape(self.mem.cfg["name"].lower())
        t = re.sub(rf"^({n}|эй {n}|слушай)[, ]+", "", raw.lower().strip(" .!?,"))
        d = self.mem.d
        if m := re.match(r"меня зовут\s+(\w+)", t):
            self.mem.fact("Зовут " + m[1].title()); return f"Приятно познакомиться, {m[1].title()}! Запомнила."
        if m := re.match(r"запомни,?\s*(?:что\s+)?(.+)", t): self.mem.fact(m[1]); return "Запомнила."
        if re.match(r"забудь\s+(всё|все|обо мне)", t):
            d["facts"], d["requests"], d["history"] = [], [], []; self.mem.save(); return "Всё стёрла. Начинаем с чистого листа."
        if m := re.match(r"забудь\s+(.+)", t):
            d["facts"] = [f for f in d["facts"] if m[1] not in f.lower()]; self.mem.save(); return "Готово, забыла."
        if re.search(r"что ты (обо мне )?(знаешь|помнишь)", t):
            return ("Вот что я о тебе знаю.", "\n".join("- " + f for f in d["facts"])) if d["facts"] else \
                "Пока почти ничего. Расскажи о себе или скажи «запомни, что…»."
        if re.search(r"что я (просил|спрашивал)", t):
            r = d["requests"][-6:-1]
            return ("Вот твои последние запросы.", "\n".join("- " + x for x in r)) if r else "Пока это твой первый запрос."
        # быстрые настройки голосом
        if re.search(r"говори быстрее|быстрее говори", t): return self.tweak("rate", 10, -50, 80, "Говорю быстрее.")
        if re.search(r"говори медленнее|медленнее говори", t): return self.tweak("rate", -10, -50, 80, "Говорю медленнее.")
        if re.fullmatch(r"(сделай )?громче", t): return self.tweak("volume", 15, 0, 100, "Громче.")
        if re.fullmatch(r"(сделай )?тише", t): return self.tweak("volume", -15, 0, 100, "Тише.")
        if re.search(r"(выключи|отключи) озвучку", t): self.cfg_set("tts", False); return "Озвучка выключена, отвечаю текстом."
        if re.search(r"включи озвучку", t): self.cfg_set("tts", True); return "Озвучка включена."
        if re.search(r"настройки\s+нов", t): self.ui(self.open_settings); return "Открываю настройки."
        for handler in (self.extra, self.extra2, self.extra3):      # таймеры/медиа/обновления → файлы/зрение → мышь/столы/система
            if (r := handler(t, raw)) is not None: return r         # (extra идёт первым: иначе «останови музыку» ловило «закрой программу»)
        if re.search(r"диагностик|проверь (пк|комп)|состояни. (пк|комп)|характеристик|тормозит", t): return self.diag()
        if m := re.match(r"(включи|поставь|запусти)\s+(музык\w*|песн\w*|трек)\s*(.*)", t):
            q = m[3] or "музыка для работы"
            webbrowser.open("https://www.youtube.com/results?search_query=" + quote(q)); return f"Включаю: {q}."
        if m := re.match(r"(найди|загугли|поищи)\s+(.+)", t):
            webbrowser.open("https://www.google.com/search?q=" + quote(m[2])); return f"Ищу: {m[2]}."
        if m := re.match(r"(открой|запусти|включи|зайди на)\s+(.+)", t):
            return self.open_any(re.sub(r"^(сайт|приложение|программу|программа)\s+", "", m[2]).strip())
        if re.search(r"который час|сколько (сейчас )?времени|скажи время", t): return time.strftime("Сейчас %H:%M.")
        if re.search(r"какое (сегодня )?число|какая (сегодня )?дата|какой (сегодня )?день", t):
            n_ = time.localtime(); return f"Сегодня {DAYS[n_.tm_wday]}, {n_.tm_mday} {MONTHS[n_.tm_mon - 1]}."
        if re.search(r"что ты умеешь|^помощь$", t):
            return ("Я проверяю компьютер, открываю сайты и программы, ищу в Google, включаю музыку, помню тебя и отвечаю как ИИ.",
                    "- **Диагностика:** «проверь компьютер»\n- **Программы и сайты:** «открой дискорд», «открой ютуб»\n"
                    "- **Поиск и музыка:** «найди …», «включи музыку …»\n- **Память:** «запомни, что …», «что ты обо мне знаешь», «забудь всё»\n"
                    "- **Голос:** «говори быстрее/медленнее», «громче/тише», «выключи озвучку», «настройки нова»\n"
                    "- **Таймеры:** «таймер на 5 минут», «напомни через час позвонить»\n"
                    "- **Заметки:** «запиши заметку …», «покажи заметки»\n"
                    "- **Полезное:** «посчитай 25 умножить на 4», «погода в Москве», «курс доллара», «брось кубик», «сделай скриншот»\n"
                    "- **Буфер и выделение:** «прочитай буфер», «объясни выделенное», «скопируй код», «сохрани чат»\n"
                    "- **Музыка на ПК:** «пауза», «следующий трек», «компьютер громче»\n"
                    "- **Обновления:** «проверь обновления», «обнови себя», «какая у тебя версия»\n"
                    "- **Всё остальное:** спроси как у ИИ")
        return self.ask_ai(raw)

    def open_any(self, n):
        if n in SITES or re.match(r"^[\w-]+\.[a-z]{2,}", n):
            webbrowser.open("https://" + SITES.get(n, n.replace(" ", ""))); return f"Открываю {n}."
        if os.name != "nt": return "Запуск программ пока работает только в Windows."
        if n in SYSTEM_ARGS: os.startfile(SYSTEM_ARGS[n]); return f"Открываю {n}."
        key = ALIASES.get(n, n); apps = dict(self.apps)
        hit = next((k for k in apps if k == key), None) or next((k for k in apps if key in k), None) \
            or next(iter(difflib.get_close_matches(key, apps, 1, 0.6)), None)
        if hit: os.startfile(apps[hit]); return f"Запускаю {hit.title()}."
        return f"Не нашла программу «{n}». Могу поискать в Google — скажи «найди {n}»."

    # ---------- ИИ: потоковый ответ, озвучка начинается с первого предложения ----------
    def post_ai(self, msgs, stream=False):
        c = self.mem.cfg
        return requests.post(AI_URL, json={"model": c["ai_model"], "messages": msgs, "stream": stream},
                             timeout=(8, c["ai_timeout"]), stream=stream)

    def emit_ai(self, full, pos, final):
        m = DETAILS_RE.search(full)
        chunk = (full[:m.start()] if m else full)[pos:]
        if final or m: k = len(chunk)
        else:
            ends = [x.end() for x in re.finditer(r"[.!?…]\s|\n", chunk)]
            if not ends: return pos
            k = ends[-1]
        for s in split_long(sentences(chunk[:k])): self.speaker.feed(s)
        return pos + k

    def user_content(self, text, att):
        """(текст для истории, содержимое сообщения для ИИ): файлы вставляются текстом, фото — как картинки."""
        c, att = self.mem.cfg, att or {"img": [], "file": []}
        notes = []
        for p in att["file"]:
            body = read_file_text(p)
            notes.append(f"[Файл «{Path(p).name}»]\n{body}" if body is not None else
                         f"[Файл «{Path(p).name}» приложен, но его содержимое прочитать нельзя; путь: {p}]")
        full = text + ("\n\n" + "\n\n".join(notes)[:60000] if notes else "")
        names = [Path(p).name for p in att["img"] + att["file"]]
        hist = text + (f" [вложения: {', '.join(names)}]" if names else "")
        if not att["img"]: return hist, full, 0
        if not c["vision"]: return hist, full + "\n\n(Фото приложены, но зрение выключено в настройках.)", 0
        parts = [{"type": "text", "text": full}]
        for p in att["img"]:
            u = img_b64(p, int(c["img_side"]))
            if u: parts.append({"type": "image_url", "image_url": {"url": u}})
        return hist, parts, len(parts) - 1

    def ask_ai(self, text, learn=True, att=None):
        d, c = self.mem.d, self.mem.cfg
        if not c["ai"]: return "ИИ отключён в настройках."
        hist, content, n_img = self.user_content(text, att)
        h = d["history"]; h.append({"role": "user", "content": hist})
        sysm = (f"Ты {c['name']}. {PERSONAS.get(c['persona'], PERSONAS['Дружелюбная'])} Говоришь по-русски. Сначала дай устный ответ "
                f"({STYLES.get(c['ai_style'], STYLES['Коротко'])}, без markdown и эмодзи). Если нужны списки, шаги, код или подробности — "
                "после ответа поставь отдельную строку --- и оформи подробности в markdown (**жирный**, - списки, `код`, блоки ```). "
                "Эта часть не озвучивается. Сейчас " + time.strftime("%d.%m.%Y %H:%M") + ".")
        if d["facts"]: sysm += " Известные факты о пользователе: " + "; ".join(d["facts"]) + "."
        if len(d["requests"]) > 1: sysm += " Его недавние запросы: " + "; ".join(d["requests"][-8:-1]) + "."
        msgs = [{"role": "system", "content": sysm}] + h[-int(c["history_len"]):-1] + [{"role": "user", "content": content}]
        sp, full, pos = self.speaker, "", 0
        sp.begin()
        try:
            try:
                r = self.post_ai(msgs, True); r.raise_for_status(); r.encoding = "utf-8"
                for line in r.iter_lines(chunk_size=None, decode_unicode=True):
                    if isinstance(line, bytes): line = line.decode("utf-8", "ignore")
                    if not line or not line.startswith("data:"): continue
                    p = line[5:].strip()
                    if p == "[DONE]": break
                    try: full += json.loads(p)["choices"][0]["delta"].get("content") or ""
                    except Exception: continue
                    pos = self.emit_ai(full, pos, False)
            except Exception:
                if not full.strip():                              # стрим не получился — обычный запрос
                    full = self.post_ai(msgs).json()["choices"][0]["message"]["content"]
            full = full.strip()
            if not full: raise RuntimeError("пустой ответ")
            self.emit_ai(full, pos, True)
            m = DETAILS_RE.search(full)
            card = full[m.end():].strip(" -\n") if m else None
        except Exception:
            h.pop(); sp.end()
            if n_img: return "Не получилось отправить фото ИИ — возможно, выбранная модель не умеет смотреть картинки или нет связи."
            return "Не смогла связаться с ИИ. Команды вроде диагностики и запуска программ работают и без него."
        h.append({"role": "assistant", "content": full}); d["history"] = h[-30:]; self.mem.save()
        self.last_ai = full
        if c["learn"] and learn: threading.Thread(target=self.learn, args=(text,), daemon=True).start()
        sp.end(card or None)
        return ""          # "" = «ответ уже озвучен»; None означало бы «команда не распознана» и вызвало бы второй запрос к ИИ

    def learn(self, text):
        if len(text) < 12 or not re.search(r"\b(я|меня|мой|моя|моё|мое|мои|мне|люблю|работаю|живу|учусь)\b", text.lower()): return
        try:
            p = ("Выдели из сообщения только устойчивые факты о пользователе (имя, возраст, город, работа, увлечения, проекты, "
                 "предпочтения). Ответь только JSON-массивом коротких фраз на русском, например [\"Увлекается Unity\"]. "
                 "Если фактов нет — []. Сообщение: " + text)
            r = self.post_ai([{"role": "user", "content": p}])
            arr = json.loads(re.search(r"\[.*\]", r.json()["choices"][0]["message"]["content"], re.S)[0])
            for f in arr[:4]:
                if isinstance(f, str): self.mem.fact(f)
        except Exception: pass

    # ---------- диагностика ----------
    def diag(self):
        cpu = psutil.cpu_percent(interval=0.5); vm = psutil.virtual_memory(); disk = psutil.disk_usage(os.path.abspath(os.sep))
        if self._gpu is None:
            self._gpu = ""
            if os.name == "nt":
                try:
                    self._gpu = subprocess.check_output(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_VideoController).Name"],
                                                        text=True, creationflags=0x08000000, timeout=8).strip().replace("\n", ", ")
                except Exception: pass
        agg = {}
        for p in psutil.process_iter(["name", "memory_info"]):
            mi = p.info["memory_info"]
            if mi: agg[p.info["name"] or "?"] = agg.get(p.info["name"] or "?", 0) + mi.rss
        top = [(n, v / 1e9) for n, v in sorted(agg.items(), key=lambda x: -x[1])[:3]]
        bat = psutil.sensors_battery(); up = (time.time() - psutil.boot_time()) / 3600
        L = [f"**Процессор:** {psutil.cpu_count(logical=False)} ядер / {psutil.cpu_count()} потоков, загрузка {cpu:.0f}%",
             f"**Память:** {vm.used / 1e9:.1f} из {vm.total / 1e9:.1f} ГБ ({vm.percent:.0f}%)",
             f"**Диск:** свободно {disk.free / 1e9:.0f} из {disk.total / 1e9:.0f} ГБ"]
        if self._gpu: L.append("**Видеокарта:** " + self._gpu)
        if bat: L.append(f"**Батарея:** {bat.percent:.0f}%" + (" (заряжается)" if bat.power_plugged else ""))
        L.append(f"**Без перезагрузки:** {up:.1f} ч")
        if top: L.append("**Больше всего памяти:** " + ", ".join(f"`{n}` {g:.1f} ГБ" for n, g in top))
        speak = f"Процессор загружен на {cpu:.0f} процентов, память занята на {vm.percent:.0f}, на диске свободно {disk.free / 1e9:.0f} гигабайт."
        if top: speak += f" Больше всего памяти ест {top[0][0].replace('.exe', '')}."
        if cpu > 85 or vm.percent > 85: speak += " Нагрузка высокая, стоит закрыть лишнее."
        return speak, "\n".join("- " + x for x in L)

    # ---------- окно настроек ----------
    def open_settings(self):
        if self.win is not None and self.win.isVisible(): self.win.raise_(); self.win.activateWindow(); return
        c = self.mem.cfg
        w = self.win = QDialog(self); w.setWindowTitle("Настройки"); w.resize(540, 800)
        outer = QVBoxLayout(w); outer.setContentsMargins(0, 0, 0, 0)
        sa = QScrollArea(); sa.setWidgetResizable(True); sa.setFrameShape(QFrame.Shape.NoFrame); outer.addWidget(sa)
        body = QWidget(); body.setObjectName("body"); sa.setWidget(body)
        col = QVBoxLayout(body); col.setSpacing(8); col.setContentsMargins(16, 6, 22, 18)

        def sec(t):
            l = QLabel(t); l.setStyleSheet(f"color:{CYAN};font-size:15px;font-weight:700;margin-top:14px;"); col.addWidget(l)

        def line(label, widget, stretch=False):
            row = QHBoxLayout(); lb = QLabel(label); lb.setWordWrap(True); row.addWidget(lb, 1); row.addWidget(widget, 1 if stretch else 0); col.addLayout(row)

        def slider(label, key, lo, hi, fmt="{:.0f}", scale=1):
            s = QSlider(Qt.Orientation.Horizontal); s.setRange(int(lo * scale), int(hi * scale)); s.setValue(int(round(c[key] * scale))); s.setFixedWidth(170)
            val = QLabel(fmt.format(c[key])); val.setFixedWidth(46); val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            def cb(v):
                x = round(v / scale, 1) if scale != 1 else v
                self.cfg_set(key, x); val.setText(fmt.format(x))
            s.valueChanged.connect(cb)
            row = QHBoxLayout(); lb = QLabel(label); lb.setWordWrap(True); row.addWidget(lb, 1); row.addWidget(s); row.addWidget(val); col.addLayout(row)

        def switch(label, key, color=VIO, slot=None):
            t = Toggle(color); t.setChecked(bool(c[key])); t.toggled.connect(slot or (lambda v: self.cfg_set(key, bool(v))))
            row = QHBoxLayout(); row.addWidget(t); lb = QLabel(label); lb.setWordWrap(True); row.addWidget(lb, 1); col.addLayout(row)

        def menu(label, key, values, show=lambda v: v, store=lambda v: v):
            m = QComboBox(); m.addItems(values); m.setCurrentText(show(c[key])); m.setFixedWidth(230)
            m.currentTextChanged.connect(lambda v: self.cfg_set(key, store(v))); line(label, m)

        def entry(label, key):
            e = QLineEdit(str(c[key])); e.setFixedWidth(230); e.setStyleSheet("min-height:30px;border-radius:15px;")
            e.editingFinished.connect(lambda: self.cfg_set(key, e.text().strip() or DEFAULT_CFG[key])); line(label, e); return e

        def folder(label, key):
            e = entry(label, key)

            def pick():
                p = QFileDialog.getExistingDirectory(w, label, c[key] if os.path.isdir(c[key]) else "")
                if p: p = os.path.normpath(p); e.setText(p); self.cfg_set(key, p)
            b = QPushButton("Выбрать папку…"); b.setStyleSheet("min-height:28px;"); b.clicked.connect(pick); col.addWidget(b, 0, Qt.AlignmentFlag.AlignRight)

        def btn(text, fn):
            b = QPushButton(text); b.clicked.connect(lambda _=False: fn()); col.addWidget(b)

        sec("Озвучка")
        switch("Озвучивать ответы", "tts")
        switch("Текст появляется синхронно со словами", "sync_text")
        slider("Темп, %", "rate", -50, 80)
        slider("Тон, Гц", "pitch", -40, 40)
        slider("Громкость, %", "volume", 0, 100)
        btn("Проверить голос", lambda: threading.Thread(target=self.test_voice, daemon=True).start())

        sec("Микрофон и распознавание")
        mics = mic_names()
        menu("Микрофон", "mic", mics, show=lambda v: v if v in mics else MIC_DEFAULT)
        menu("Язык речи", "lang", list(LANGS), show=lambda v: next((k for k, x in LANGS.items() if x == v), "Русский"), store=LANGS.get)
        slider("Чувствительность (меньше = чувствительнее)", "mic_sens", 1.5, 5, "{:.1f}", 10)
        slider("Пауза до конца фразы, с", "silence", 0.4, 2.0, "{:.1f}", 10)
        slider("Ждать начала речи, с", "wait_speech", 3, 20)
        slider("Макс. длина записи, с", "max_rec", 5, 60)

        sec("ИИ")
        switch("Отвечать через ИИ", "ai")
        switch("Запоминать факты обо мне автоматически", "learn")
        menu("Длина ответа", "ai_style", list(STYLES))
        menu("Характер помощника", "persona", list(PERSONAS))
        entry("Модель", "ai_model")
        slider("Сообщений в контексте", "history_len", 2, 30)
        slider("Таймаут ответа, с", "ai_timeout", 10, 120)

        sec("Интерфейс")
        entry("Имя помощника", "name")
        entry("Город для погоды", "city")
        menu("Цвет шара", "theme", list(THEMES))
        switch("Автокопирование выделенного текста", "copy_on_select")
        switch("Закрытие окна сворачивает в трей", "tray_close")
        slider("Размер шрифта", "font_size", 9, 18)
        slider("Прозрачность окна, %", "opacity", 50, 100)
        switch("Поверх всех окон", "topmost")

        sec("Отклик на имя и диалог")
        switch("Отзываться на своё имя (микрофон слушает всегда)", "wake", CYAN, lambda v: self.wake_t.setChecked(bool(v)))
        entry("Другие варианты имени (через запятую)", "wake_aliases")
        slider("Продолжать без имени после ответа, с (0 — выкл)", "conv_window", 0, 120)
        switch("Короткий сигнал, когда услышала своё имя", "wake_chime")
        switch("Озвучивать ответы на напечатанное", "speak_typed")
        note = QLabel("Распознавание речи идёт через сервис Google, поэтому при включённом отклике на имя звук с микрофона "
                      "отправляется туда. Если это не нужно — выключи переключатель."); note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTE};"); col.addWidget(note)

        sec("Фото, файлы и зрение")
        switch("ИИ может смотреть фото и экран", "vision")
        slider("Размер фото для ИИ, px", "img_side", 512, 2048)

        sec("Управление компьютером")
        switch("Разрешить управление мышью и клавиатурой", "allow_control")
        switch("Разрешить закрывать программы, сон и выключение", "allow_power")
        switch("Разрешить команды терминала", "allow_shell")
        switch("Спрашивать подтверждение у опасных действий", "confirm_actions")
        folder("Папка для создаваемых файлов", "work_dir")

        sec("Автосохранение чата")
        switch("Сохранять чат автоматически", "autosave")
        switch("Показывать прошлый чат при запуске", "restore_chat")
        folder("Папка автосохранения", "autosave_dir")
        menu("Формат файла", "autosave_fmt", ["txt", "md"])
        slider("Как часто, сек", "autosave_sec", 5, 300)
        slider("Сколько файлов хранить", "autosave_keep", 1, 200)
        btn("Сохранить чат сейчас", lambda: (setattr(self, "saved_txt", ""), self.autosave(), self.flash("Чат сохранён")))
        btn("Открыть папку с чатами", lambda: (Path(c["autosave_dir"]).mkdir(parents=True, exist_ok=True), self.open_path(c["autosave_dir"])))

        sec("Обновления и запуск")
        ver = QLabel(f"Версия {VERSION} · репозиторий {REPO}" + (" · exe" if FROZEN else " · скрипт")); ver.setStyleSheet(f"color:{MUTE};"); col.addWidget(ver)
        switch("Проверять обновления автоматически", "auto_update")
        switch("Устанавливать найденные обновления без вопросов", "auto_install")
        slider("Как часто проверять, ч", "update_hours", 1, 48)
        switch("Запускать Нову вместе с Windows", "autostart")

        def check_now():
            def run():
                info, err = self.check_update()
                if err: self.ui(self.put, err + "\n\n", "time")
                elif not info: self.ui(self.put, f"У тебя последняя версия — {VERSION}.\n\n", "time")
                else: self.pending = info; self.ui(self.show_update, info)
            threading.Thread(target=run, daemon=True).start(); self.flash("Проверяю обновления…")
        btn("Проверить обновления сейчас", check_now)

        sec("Данные")
        btn("Сохранить чат в файл…", self.save_chat)
        btn("Очистить историю диалога", lambda: (self.mem.d.update(history=[]), self.mem.save()))
        btn("Очистить кэш озвучки", Speaker.clear_cache)
        btn("Сбросить настройки", self.reset_cfg)
        tip = QLabel("Голос выбирается в главном окне. Имя применится после перезапуска."); tip.setStyleSheet(f"color:{MUTE};"); tip.setWordWrap(True)
        col.addWidget(tip); col.addStretch()
        w.show()

    def reset_cfg(self):
        self.mem.cfg.update(DEFAULT_CFG); self.mem.save(); self.apply_ui(); self.vmenu.setCurrentText(DEFAULT_CFG["voice"])
        for t, k in ((self.auto_t, "auto"), (self.wake_t, "wake")):
            t.blockSignals(True); t.setChecked(bool(DEFAULT_CFG[k])); t.blockSignals(False)
        self.conv_until = 0; set_autostart(False)
        if self.win is not None: self.win.close(); self.win = None
        QTimer.singleShot(150, self.open_settings)

    def test_voice(self):
        if not self.take(): return
        try: self.say("Привет! Так я звучу с текущими настройками.")
        finally: self.busy = False; self.set_state("idle")


def main():
    if os.name == "nt":
        try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("fundreamer365.Nova")   # своя иконка в панели задач
        except Exception: pass
    app = QApplication(sys.argv); app.setStyle("Fusion"); app.setApplicationName("Nova"); app.setQuitOnLastWindowClosed(False)
    if not single_instance(wait=10 if "--restarted" in sys.argv else 0):
        QMessageBox.information(None, "Нова", "Нова уже запущена — посмотри в трее или на панели задач."); return
    w = App(); w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()