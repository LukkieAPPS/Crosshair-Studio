import json, sys, os, time, colorsys, shutil, math, urllib.request, urllib.error, hashlib, tempfile, subprocess, re, uuid
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, QObject, Signal, QThread
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QPixmap, QImage, QKeySequence, QShortcut, QImageReader,
    QLinearGradient, QPainterPath
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QSlider,
    QComboBox, QColorDialog, QVBoxLayout, QHBoxLayout, QFrame, QCheckBox,
    QMessageBox, QFileDialog, QInputDialog, QListWidget, QDialog,
    QLineEdit, QDialogButtonBox, QScrollArea
)
from PySide6.QtSvg import QSvgRenderer

HERE = Path(__file__).resolve().parent
APP_VERSION = "1.0.3"
GITHUB_RELEASE_API = "https://api.github.com/repos/LukkieAPPS/Crosshair-Studio/releases/latest"
SUPABASE_URL = "https://ywlsosxhlcpommmfxvge.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_oNJxRC9sU3PMHCflRNeKKw_W9gJKxom"

class UpdateWorker(QThread):
    checked = Signal(object)
    downloaded = Signal(str)
    failed = Signal(str)

    def __init__(self, download_url=None, checksum_url=None, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.checksum_url = checksum_url

    def run(self):
        try:
            request = urllib.request.Request(GITHUB_RELEASE_API, headers={"User-Agent": "Crosshair-Studio-Updater"})
            with urllib.request.urlopen(request, timeout=8) as response:
                release = json.loads(response.read().decode("utf-8"))
            if not self.download_url:
                tag = str(release.get("tag_name", "")).lstrip("vV")
                match = re.match(r"^(\d+)\.(\d+)\.(\d+)", tag)
                current = tuple(map(int, APP_VERSION.split(".")))
                latest = tuple(map(int, match.groups())) if match else current
                assets = release.get("assets", [])
                installer = next((a for a in assets if a.get("name") == "CrosshairStudio_Setup.exe"), None)
                checksum = next((a for a in assets if a.get("name") == "CrosshairStudio_Setup.exe.sha256"), None)
                if latest > current and installer and checksum:
                    self.checked.emit({"version": tag, "installer": installer.get("browser_download_url"), "checksum": checksum.get("browser_download_url"), "notes": str(release.get("body", ""))[:1200]})
                else:
                    self.checked.emit(None)
                return
            def fetch(url):
                req = urllib.request.Request(url, headers={"User-Agent": "Crosshair-Studio-Updater"})
                with urllib.request.urlopen(req, timeout=45) as response:
                    return response.read()
            installer_data = fetch(self.download_url)
            checksum_text = fetch(self.checksum_url).decode("utf-8", errors="replace")
            expected = re.search(r"\b([a-fA-F0-9]{64})\b", checksum_text)
            if not expected:
                raise ValueError("The release checksum file is invalid.")
            actual = hashlib.sha256(installer_data).hexdigest()
            if actual.lower() != expected.group(1).lower():
                raise ValueError("The installer checksum did not match. The update was cancelled.")
            target = Path(tempfile.gettempdir()) / "CrosshairStudio_Update_Setup.exe"
            target.write_bytes(installer_data)
            self.downloaded.emit(str(target))
        except Exception as exc:
            self.failed.emit(str(exc))



class PremiumWorker(QThread):
    result = Signal(str, object, str)

    def __init__(self, operation, payload, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.payload = payload

    def run(self):
        try:
            rpc_name = "check_premium" if self.operation == "status" else "redeem_premium_code"
            url = SUPABASE_URL + "/rest/v1/rpc/" + rpc_name
            request = urllib.request.Request(
                url,
                data=json.dumps(self.payload).encode("utf-8"),
                headers={
                    "apikey": SUPABASE_PUBLISHABLE_KEY,
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=12) as response:
                data = json.loads(response.read().decode("utf-8"))
            self.result.emit(self.operation, data, "")
        except Exception as exc:
            self.result.emit(self.operation, None, str(exc))


# Store writable user data outside the installation directory. Windows protects
# Program Files, so writing JSON files beside an installed EXE can fail.
_APPDATA_ROOT = Path(os.environ.get("APPDATA") or (Path.home() / ".config"))
DATA_DIR = _APPDATA_ROOT / "Crosshair Studio"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Migrate existing portable-build data once, without overwriting newer AppData files.
for _data_name in ("settings.json", "presets.json", "profiles.json"):
    _old_file = HERE / _data_name
    _new_file = DATA_DIR / _data_name
    if _old_file.is_file() and not _new_file.exists():
        try:
            shutil.copy2(_old_file, _new_file)
        except OSError:
            pass

SETTINGS_FILE = DATA_DIR / "settings.json"
PRESETS_FILE = DATA_DIR / "presets.json"
PROFILES_FILE = DATA_DIR / "profiles.json"

DEFAULT = {
    "style": "Plus", "color": "#ffffff", "color2": "#00d9ff",
    "gradient": False, "animated": False, "size": 24, "thickness": 3,
    "gap": 5, "opacity": 100, "visible": True, "image_path": "",
    "dynamic_enabled": False, "dynamic_spread": 0.0, "dynamic_strength": 9,
    "crosshair_animation": "Off", "effect_phase": 0.0
}
BUILTINS = {
    "Classic Plus": {"style":"Plus","color":"#ffffff","size":24,"thickness":3,"gap":5,"opacity":100},
    "Tiny Dot": {"style":"Dot","color":"#ffffff","size":12,"thickness":2,"gap":3,"opacity":100},
    "Open Cross": {"style":"Cross","color":"#00ff88","size":18,"thickness":2,"gap":0,"opacity":100},
    "Small Circle": {"style":"Circle","color":"#ffffff","size":18,"thickness":2,"gap":4,"opacity":100},
    "Tactical T": {"style":"T","color":"#ff4444","size":22,"thickness":3,"gap":4,"opacity":95},
}
PREMIUM_PRESETS = {
    "Shotgun · Spread Read": {"style":"Shotgun","color":"#7CFFCB","color2":"#FFFFFF","size":44,"thickness":3,"gap":8,"opacity":100},
    "Shotgun · Tight Pump": {"style":"Shotgun","color":"#FFFFFF","color2":"#7CFFCB","size":28,"thickness":3,"gap":4,"opacity":100},
    "Shotgun · Box Fight": {"style":"Shotgun","color":"#00E5FF","color2":"#B7FF00","size":36,"thickness":3,"gap":6,"opacity":100,"gradient":True},
    "Shotgun · Wide Bloom": {"style":"Shotgun","color":"#FFCF4A","color2":"#FF6B6B","size":58,"thickness":3,"gap":12,"opacity":95},
    "AR · Precision": {"style":"Plus","color":"#B8FF4A","size":18,"thickness":2,"gap":3,"opacity":100},
    "SMG · Tracking": {"style":"Cross","color":"#00E5FF","size":13,"thickness":2,"gap":0,"opacity":100},
    "Sniper · Pinpoint": {"style":"Dot","color":"#FFFFFF","size":8,"thickness":2,"gap":0,"opacity":100},
    "Flick · Diamond": {"style":"Diamond","color":"#FF5CE1","size":26,"thickness":2,"gap":4,"opacity":100},
    "Edit · Reset T": {"style":"T","color":"#FFFFFF","size":24,"thickness":3,"gap":4,"opacity":100},
    "Low Vis · Lime": {"style":"Plus","color":"#B7FF00","size":20,"thickness":2,"gap":5,"opacity":90},
    "Clean · Micro Dot": {"style":"Dot","color":"#00FF9C","size":6,"thickness":2,"gap":0,"opacity":100},
    "Tracking · Open Ring": {"style":"Circle","color":"#7CFFCB","size":30,"thickness":2,"gap":0,"opacity":100},
}

def read(path, fallback):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(fallback)) else fallback
    except Exception:
        return fallback

def write(path, value):
    """Write JSON safely so a close/crash cannot leave a half-written settings file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    os.replace(temp_path, path)

def premium_enabled():
    return bool(read(SETTINGS_FILE, {}).get("premium_test_active", False))

class KeyBridge(QObject):
    profile_requested = Signal(str)
    movement_requested = Signal(bool)


class BindDialog(QDialog):
    """Small capture window for one keyboard key or mouse button."""
    captured = Signal(str)

    def __init__(self, current_bind="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set profile bind")
        self.setFixedWidth(340)
        self.keyboard_listener = None
        self.mouse_listener = None
        self.waiting = False
        self.done_with_bind = ""
        layout = QVBoxLayout(self)
        title = QLabel("PROFILE BIND")
        title.setStyleSheet("font-size:15px;font-weight:800")
        layout.addWidget(title)
        self.status = QLabel(f"Current bind: {self.describe_bind(current_bind) if current_bind else 'Not set'}")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(QLabel("Activate profile when:"))
        self.trigger_mode = QComboBox()
        self.trigger_mode.addItem("Button is pressed", "press")
        self.trigger_mode.addItem("Button is released", "release")
        if current_bind.endswith(":release"):
            self.trigger_mode.setCurrentIndex(1)
        layout.addWidget(self.trigger_mode)
        self.bind_button = QPushButton("Set bind")
        self.bind_button.clicked.connect(self.begin_capture)
        layout.addWidget(self.bind_button)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button)
        self.captured.connect(self.finish_capture)

    @staticmethod
    def describe_bind(bind):
        parts = bind.split(":")
        if len(parts) >= 3 and parts[-1] in ("press", "release"):
            return f"{parts[0]} — {parts[1]} ({parts[-1]})"
        return bind.replace(":", " — ") + " (press)"

    def begin_capture(self):
        try:
            from pynput import keyboard, mouse
        except ImportError:
            QMessageBox.warning(self, "Missing package", "The keyboard/mouse listener is missing. Close the app and run Start_Crosshair_Studio.bat once to install the required components automatically.")
            return
        self.waiting = True
        self.bind_button.setEnabled(False)
        self.status.setText("Setting bind...\nPress any keyboard key, mouse button, or scroll the wheel up/down.")

        def key_pressed(key):
            if not self.waiting:
                return False
            if self.trigger_mode.currentData() != "press":
                return
            try:
                value = key.char.lower()
            except AttributeError:
                value = str(key).replace("Key.", "").lower()
            self.captured.emit(f"key:{value}:press")
            return False

        def key_released(key):
            if not self.waiting or self.trigger_mode.currentData() != "release":
                return
            try:
                value = key.char.lower()
            except AttributeError:
                value = str(key).replace("Key.", "").lower()
            self.captured.emit(f"key:{value}:release")
            return False

        def mouse_clicked(x, y, button, pressed):
            if self.waiting and ((pressed and self.trigger_mode.currentData() == "press") or
                                 (not pressed and self.trigger_mode.currentData() == "release")):
                value = str(button).replace("Button.", "").lower()
                mode = self.trigger_mode.currentData()
                self.captured.emit(f"mouse:{value}:{mode}")
                return False

        def mouse_scrolled(x, y, dx, dy):
            if self.waiting and dy:
                direction = "scroll_up" if dy > 0 else "scroll_down"
                self.captured.emit(f"mouse:{direction}:press")
                return False

        self.keyboard_listener = keyboard.Listener(on_press=key_pressed, on_release=key_released)
        self.mouse_listener = mouse.Listener(on_click=mouse_clicked, on_scroll=mouse_scrolled)
        self.keyboard_listener.daemon = True
        self.mouse_listener.daemon = True
        self.keyboard_listener.start()
        self.mouse_listener.start()

    def finish_capture(self, bind):
        if not self.waiting:
            return
        self.waiting = False
        self.stop_listeners()
        self.status.setText(f"Bind captured: {self.describe_bind(bind)}")
        self.done_with_bind = bind
        self.accept()

    def stop_listeners(self):
        for listener in (self.keyboard_listener, self.mouse_listener):
            if listener:
                try:
                    listener.stop()
                except Exception:
                    pass
        self.keyboard_listener = None
        self.mouse_listener = None

    def reject(self):
        self.waiting = False
        self.stop_listeners()
        super().reject()

    def closeEvent(self, event):
        self.waiting = False
        self.stop_listeners()
        super().closeEvent(event)

class Crosshair(QWidget):
    def __init__(self, settings, overlay=False):
        super().__init__()
        self.settings = settings
        self.overlay = overlay
        self.pix = QPixmap()
        self._image_path = None
        self._scaled_cache = {}
        self.contrast_background = None
        self.phase = 0
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        if overlay:
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            screen = QApplication.primaryScreen()
            if screen:
                # Keep the transparent overlay small instead of covering the whole
                # desktop. Its centre remains aligned with the screen centre.
                self.setGeometry(self.overlay_geometry(screen))
        else:
            self.setMinimumSize(240, 190)
        self.load_image()

    @staticmethod
    def overlay_geometry(screen):
        area = screen.geometry()
        side = 256
        return area.__class__(
            area.x() + (area.width() - side) // 2,
            area.y() + (area.height() - side) // 2,
            side,
            side
        )

    def load_image(self):
        raw_path = self.settings.get("image_path", "")
        path = str(Path(raw_path).expanduser().resolve()) if raw_path else ""
        self._image_path = path
        self._scaled_cache.clear()
        self.pix = QPixmap()
        if not path or not Path(path).is_file():
            return False
        if path.lower().endswith(".svg"):
            renderer = QSvgRenderer(path)
            if not renderer.isValid():
                return False
            view = renderer.viewBoxF()
            if view.isEmpty():
                view = QRectF(0, 0, 512, 512)
            scale = min(512 / max(1.0, view.width()), 512 / max(1.0, view.height()))
            w, h = max(1, round(view.width() * scale)), max(1, round(view.height() * scale))
            self.pix = QPixmap(w, h)
            self.pix.fill(Qt.GlobalColor.transparent)
            painter = QPainter(self.pix)
            renderer.render(painter, QRectF(0, 0, w, h))
            painter.end()
            return not self.pix.isNull()
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            return False
        self.pix = QPixmap.fromImage(image)
        return not self.pix.isNull()

    def update_settings(self, settings):
        self.settings = settings
        raw_path = self.settings.get("image_path", "")
        path = str(Path(raw_path).expanduser().resolve()) if raw_path else ""
        # Compare with the cached path, not settings["image_path"]: settings is
        # shared and mutated in-place by the main window.
        if path != self._image_path:
            self.load_image()
        self.update()

    def paintEvent(self, event):
        if not self.settings.get("visible", True):
            return
        contrast_active = self.contrast_background is not None
        target = QPixmap(self.size()) if contrast_active else self
        if contrast_active:
            target.fill(Qt.GlobalColor.transparent)
        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        x, y = self.width()/2, self.height()/2
        # Smooth cosmetic animation and WASD-reactive spread; no game memory or injection.
        phase = float(self.settings.get("effect_phase", 0.0))
        anim = self.settings.get("crosshair_animation", "Off")
        if anim == "Pulse":
            painter.translate(x, y); painter.scale(1.0 + 0.08 * math.sin(phase), 1.0 + 0.08 * math.sin(phase)); painter.translate(-x, -y)
        elif anim == "Rotate":
            painter.translate(x, y); painter.rotate((phase * 3.0) % 360); painter.translate(-x, -y)
        if anim == "Fade":
            painter.setOpacity(0.45 + 0.55 * (0.5 + 0.5 * math.sin(phase)))
        style = self.settings.get("style", "Plus")
        opacity = max(.05, min(1, self.settings.get("opacity", 100)/100))
        if style == "Image" and not self.pix.isNull():
            n = max(8, self.settings.get("size", 24)*2)
            img = self._scaled_cache.get(n)
            if img is None:
                img = self.pix.scaled(n, n, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
                self._scaled_cache[n] = img
            painter.setOpacity(opacity)
            painter.drawPixmap(int(x-img.width()/2), int(y-img.height()/2), img)
            painter.end()
            if contrast_active:
                self._finish_contrast_render(target)
            return

        if self.settings.get("animated"):
            hue = (self.phase * 3) % 360
            c1 = QColor.fromHsv(hue, 255, 255)
            c2 = QColor.fromHsv((hue + 115) % 360, 255, 255)
        else:
            c1 = QColor(self.settings.get("color", "#ffffff"))
            c2 = QColor(self.settings.get("color2", "#00d9ff"))
        c1.setAlphaF(opacity)
        c2.setAlphaF(opacity)
        pen = QPen(c1, self.settings.get("thickness", 3))
        pen.setCapStyle(Qt.PenCapStyle.SquareCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        size = self.settings.get("size", 24)
        gap = self.settings.get("gap", 5) + (float(self.settings.get("dynamic_spread", 0.0)) if self.settings.get("dynamic_enabled") else 0.0)

        def line(a, b):
            if self.settings.get("gradient"):
                grad = QLinearGradient(a, b)
                grad.setColorAt(0, c1)
                grad.setColorAt(1, c2)
                painter.setPen(QPen(grad, self.settings.get("thickness", 3)))
            else:
                painter.setPen(QPen(c1, self.settings.get("thickness", 3)))
            painter.drawLine(a, b)

        if style == "Dot":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(c1))
            d = max(2, self.settings.get("thickness", 3)*1.5)
            painter.drawEllipse(QPointF(x, y), d/2, d/2)
        elif style == "Circle":
            painter.setPen(QPen(c1, self.settings.get("thickness", 3)))
            painter.drawEllipse(QRectF(x-size/2, y-size/2, size, size))
        elif style == "Cross":
            line(QPointF(x-size,y), QPointF(x+size,y))
            line(QPointF(x,y-size), QPointF(x,y+size))
        elif style == "T":
            line(QPointF(x-size,y), QPointF(x+size,y))
            line(QPointF(x,y), QPointF(x,y+size))
        elif style == "Shotgun":
            # Four separated diagonal ticks create a compact spread-style reticle.
            inner = max(3, gap)
            outer = max(inner + 5, size / 2)
            for sx, sy in ((-1,-1),(1,-1),(-1,1),(1,1)):
                a = QPointF(x + sx*inner, y + sy*inner)
                b = QPointF(x + sx*outer, y + sy*outer)
                line(a, b)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(c1))
            painter.drawEllipse(QPointF(x, y), max(1.5, self.settings.get("thickness",3)/1.5), max(1.5, self.settings.get("thickness",3)/1.5))
        elif style == "Diamond":
            line(QPointF(x, y-size/2), QPointF(x+size/2, y))
            line(QPointF(x+size/2, y), QPointF(x, y+size/2))
            line(QPointF(x, y+size/2), QPointF(x-size/2, y))
            line(QPointF(x-size/2, y), QPointF(x, y-size/2))
        else:
            line(QPointF(x-gap-size/2,y), QPointF(x-gap,y))
            line(QPointF(x+gap,y), QPointF(x+gap+size/2,y))
            line(QPointF(x,y-gap-size/2), QPointF(x,y-gap))
            line(QPointF(x,y+gap), QPointF(x,y+gap+size/2))
        painter.end()
        if contrast_active:
            self._finish_contrast_render(target)

    def _finish_contrast_render(self, target):
        """Recolour every visible crosshair pixel from the background directly behind it."""
        background = self.contrast_background
        if background is None or target is None:
            return
        bg = background.scaled(
            self.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation
        ).convertToFormat(QImage.Format.Format_ARGB32)
        image = target.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        width, height = image.width(), image.height()
        for yy in range(height):
            for xx in range(width):
                pixel = image.pixel(xx, yy)
                alpha = (pixel >> 24) & 255
                if alpha == 0:
                    continue
                sample = bg.pixel(xx, yy)
                br = (sample >> 16) & 255
                bgc = (sample >> 8) & 255
                bb = sample & 255
                # Per-pixel inverse: even one continuous stroke can change colour
                # wherever the scenery behind that exact pixel changes.
                image.setPixel(xx, yy, (alpha << 24) | ((255-br) << 16) |
                               ((255-bgc) << 8) | (255-bb))
        final_pixmap = QPixmap.fromImage(image)
        output = QPainter(self)
        output.drawPixmap(0, 0, final_pixmap)
        output.end()

class CreatorCanvas(QWidget):
    """Vector-style canvas: editable strokes/shapes, selection, clipboard and symmetry."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(512, 512)
        self.color = QColor("#ffffff")
        self.thickness = 4
        self.tool = "Freehand"
        self.mirror = "Off"
        self.items = []
        self.selected = set()
        self.undo_stack = []
        self.redo_stack = []
        self.drag_start = None
        self.preview_item = None
        self.drag_offset = None
        self.last_point = None
        self.clipboard = []
        self.setMouseTracking(True)

    def _snapshot(self):
        import copy
        self.undo_stack.append(copy.deepcopy(self.items))
        if len(self.undo_stack) > 80:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            import copy
            self.redo_stack.append(copy.deepcopy(self.items))
            self.items = self.undo_stack.pop()
            self.selected.clear(); self.update()

    def redo(self):
        if self.redo_stack:
            import copy
            self.undo_stack.append(copy.deepcopy(self.items))
            self.items = self.redo_stack.pop()
            self.selected.clear(); self.update()

    def clear(self):
        if self.items:
            self._snapshot(); self.items.clear(); self.selected.clear(); self.update()

    def _mirrors(self, point):
        # Rotational symmetry around canvas centre (256, 256):
        # 2-way = 0° + 180°; 4-way = 0° + 90° + 180° + 270°.
        x, y = point.x() - 256.0, point.y() - 256.0
        angles = [0, 180] if self.mirror == "2-way" else ([0, 90, 180, 270] if self.mirror == "4-way" else [0])
        points = []
        for angle in angles:
            rad = math.radians(angle)
            rx = x * math.cos(rad) - y * math.sin(rad) + 256.0
            ry = x * math.sin(rad) + y * math.cos(rad) + 256.0
            points.append((rx, ry))
        return points

    def _new_item(self, kind, a, b, color=None, width=None):
        return {"kind":kind,"a":[a.x(),a.y()],"b":[b.x(),b.y()],
                "color":(color or self.color).name(),"width":int(width or self.thickness)}

    def _mirrored_count(self, point):
        return self._mirrors(point)

    def _add_symmetric(self, item):
        a = QPointF(*item["a"])
        b = QPointF(*item["b"])
        a_points = self._mirrors(a)
        b_points = self._mirrors(b)
        for (ax, ay), (bx, by) in zip(a_points, b_points):
            self.items.append({**item, "a": [ax, ay], "b": [bx, by]})

    def _hit(self, point):
        for i in range(len(self.items)-1,-1,-1):
            it=self.items[i]; ax,ay=it['a']; bx,by=it['b']
            if min(ax,bx)-12 <= point.x() <= max(ax,bx)+12 and min(ay,by)-12 <= point.y() <= max(ay,by)+12:
                return i
        return None

    def mousePressEvent(self, event):
        if event.button()!=Qt.MouseButton.LeftButton: return
        pos=event.position()
        if self.tool=="Select":
            idx=self._hit(pos)
            if idx is None:
                self.selected.clear(); self.drag_offset=None
            else:
                if idx not in self.selected: self.selected={idx}
                self._snapshot(); self.drag_offset=pos
            self.update(); return
        self._snapshot(); self.drag_start=pos
        if self.tool=="Freehand":
            self.last_point=pos

    def mouseMoveEvent(self, event):
        pos=event.position()
        if self.tool=="Select" and self.drag_offset is not None and self.selected:
            delta=pos-self.drag_offset
            for i in self.selected:
                it=self.items[i]
                it['a']=[it['a'][0]+delta.x(),it['a'][1]+delta.y()]
                it['b']=[it['b'][0]+delta.x(),it['b'][1]+delta.y()]
            self.drag_offset=pos; self.update(); return
        if self.drag_start is None: return
        if self.tool=="Freehand" and self.last_point is not None:
            segment=self._new_item("Line",self.last_point,pos)
            if self.mirror!="Off": self._add_symmetric(segment)
            else: self.items.append(segment)
            self.last_point=pos
            self.update()
        elif self.tool not in ("Select",):
            self.preview_item=self._new_item(self.tool,self.drag_start,pos)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button()!=Qt.MouseButton.LeftButton: return
        pos=event.position()
        if self.drag_start is not None:
            if self.tool=="Freehand":
                if self.last_point is not None and (pos-self.last_point).manhattanLength() > 0:
                    segment=self._new_item("Line",self.last_point,pos)
                    if self.mirror!="Off": self._add_symmetric(segment)
                    else: self.items.append(segment)
                self.last_point=None
            elif self.tool!="Select":
                item=self._new_item(self.tool,self.drag_start,pos)
                if self.mirror!="Off": self._add_symmetric(item)
                else: self.items.append(item)
            self.drag_start=None; self.preview_item=None; self.update()
        self.drag_offset=None

    def copy_selected(self):
        import copy
        self.clipboard=copy.deepcopy([self.items[i] for i in sorted(self.selected)])

    def paste(self):
        if not self.clipboard: return
        self._snapshot(); start=len(self.items)
        for item in self.clipboard:
            it={**item,"a":[item['a'][0]+16,item['a'][1]+16],"b":[item['b'][0]+16,item['b'][1]+16]}
            self.items.append(it)
        self.selected=set(range(start,len(self.items))); self.update()

    def delete_selected(self):
        if not self.selected: return
        self._snapshot(); self.items=[it for i,it in enumerate(self.items) if i not in self.selected]
        self.selected.clear(); self.update()

    def _draw_item(self, painter, item):
        a=QPointF(*item['a']); b=QPointF(*item['b'])
        pen=QPen(QColor(item['color']),item['width'],Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen); painter.setBrush(Qt.BrushStyle.NoBrush)
        kind=item['kind']
        if kind in ('Freehand','Line'): painter.drawLine(a,b)
        elif kind=='Circle':
            r=max(1,(b-a).manhattanLength()/2); center=(a+b)/2
            painter.drawEllipse(center,r,r)
        elif kind=='Square': painter.drawRect(QRectF(a,b).normalized())
        elif kind=='Triangle':
            path=QPainterPath(); rect=QRectF(a,b).normalized()
            path.moveTo(rect.center().x(),rect.top()); path.lineTo(rect.right(),rect.bottom()); path.lineTo(rect.left(),rect.bottom()); path.closeSubpath(); painter.drawPath(path)
        elif kind=='Arrow':
            painter.drawLine(a,b); import math
            ang=math.atan2(b.y()-a.y(),b.x()-a.x()); length=max(8,item['width']*4)
            for off in (-0.55,0.55):
                q=QPointF(b.x()-length*math.cos(ang+off),b.y()-length*math.sin(ang+off)); painter.drawLine(b,q)
        elif kind=='Dot': painter.setBrush(QBrush(QColor(item['color']))); painter.drawEllipse(a,max(2,item['width']),max(2,item['width']))

    def paintEvent(self, event):
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(),QColor('#292929'))
        for i,it in enumerate(self.items):
            self._draw_item(painter,it)
            if i in self.selected:
                painter.setPen(QPen(QColor('#58a6ff'),1,Qt.PenStyle.DashLine)); painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRectF(QPointF(*it['a']),QPointF(*it['b'])).normalized().adjusted(-6,-6,6,6))
        if self.preview_item: self._draw_item(painter,self.preview_item)
        painter.setPen(QPen(QColor('#555'),1,Qt.PenStyle.DashLine))
        painter.drawLine(256,0,256,512); painter.drawLine(0,256,512,256)

    def render_image(self):
        image=QPixmap(512,512); image.fill(Qt.GlobalColor.transparent)
        painter=QPainter(image); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for item in self.items: self._draw_item(painter,item)
        painter.end(); return image


class CrosshairCreator(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Premium Crosshair Creator")
        self.resize(720,650)
        layout=QVBoxLayout(self); layout.addWidget(QLabel("DRAW YOUR CROSSHAIR"))
        self.canvas=CreatorCanvas(); layout.addWidget(self.canvas,alignment=Qt.AlignmentFlag.AlignCenter)
        tools=QHBoxLayout(); self.tool=QComboBox(); self.tool.addItems(["Select","Freehand","Line","Circle","Square","Triangle","Arrow","Dot"])
        self.tool.currentTextChanged.connect(lambda v:setattr(self.canvas,"tool",v)); tools.addWidget(self.tool)
        self.mirror=QComboBox(); self.mirror.addItems(["Off","2-way","4-way"]); self.mirror.currentTextChanged.connect(lambda v:setattr(self.canvas,"mirror",v)); tools.addWidget(QLabel("Mirror")); tools.addWidget(self.mirror)
        colour=QPushButton("Colour"); colour.clicked.connect(self.choose_colour); tools.addWidget(colour)
        tools.addWidget(QLabel("Thickness")); self.width=QSlider(Qt.Orientation.Horizontal); self.width.setRange(1,24); self.width.setValue(4); self.width.valueChanged.connect(lambda v:setattr(self.canvas,"thickness",v)); tools.addWidget(self.width)
        layout.addLayout(tools)
        actions=QHBoxLayout()
        for label,fn in [("Undo",self.canvas.undo),("Redo",self.canvas.redo),("Copy",self.canvas.copy_selected),("Paste",self.canvas.paste),("Delete",self.canvas.delete_selected),("Clear",self.canvas.clear)]:
            b=QPushButton(label); b.clicked.connect(fn); actions.addWidget(b)
        layout.addLayout(actions)
        save=QPushButton("Save & use crosshair"); save.clicked.connect(self.save_image); layout.addWidget(save)

    def choose_colour(self):
        colour=QColorDialog.getColor(self.canvas.color,self,"Drawing colour")
        if colour.isValid(): self.canvas.color=colour

    def save_image(self):
        folder=HERE/"custom_crosshairs"; folder.mkdir(parents=True,exist_ok=True)
        path,_=QFileDialog.getSaveFileName(self,"Save custom crosshair",str(folder/"my_crosshair.png"),"PNG image (*.png)")
        if path:
            if not path.lower().endswith('.png'): path+='.png'
            if self.canvas.render_image().save(path,"PNG"):
                self.parent().s['image_path']=path; self.parent().style.setCurrentText('Image'); self.parent().refresh(); self.accept()
            else: QMessageBox.warning(self,"Save failed","Could not save this crosshair image.")

class ContrastWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Contrast Mode")
        self.setMinimumWidth(390)
        layout = QVBoxLayout(self)
        title = QLabel("AUTO CONTRAST")
        title.setStyleSheet("font-size:17px;font-weight:800")
        layout.addWidget(title)
        self.status = QLabel("Starting screen capture…")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        note = QLabel("Windowed Fullscreen is recommended. Exclusive Fullscreen may prevent Windows from providing a usable screen sample. Close this window to stop Contrast Mode.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#c9a66b;font-size:11px")
        layout.addWidget(note)
        close = QPushButton("Close Contrast Mode")
        close.clicked.connect(self.reject)
        layout.addWidget(close)


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        saved = read(SETTINGS_FILE, {})
        self.s = {**DEFAULT, **{key: value for key, value in saved.items() if key in DEFAULT}}
        # Premium is verified online; local JSON flags are never treated as proof.
        self.device_id = str(saved.get("premium_device_id") or uuid.uuid4())
        self.premium_test_active = False
        self.premium_status_checked = False
        self.premium_workers = []
        self.pending_premium_settings = {
            key: saved[key] for key in (
                "gradient", "animated", "dynamic_enabled",
                "crosshair_animation", "style"
            ) if key in saved
        }
        self.s["gradient"] = False
        self.s["animated"] = False
        self.s["dynamic_enabled"] = False
        self.s["crosshair_animation"] = "Off"
        if self.s.get("style") in ("Shotgun", "Diamond", "Image"):
            self.s["style"] = "Plus"
        saved["premium_device_id"] = self.device_id
        write(SETTINGS_FILE, saved)
        self.presets = read(PRESETS_FILE, {})
        self.profiles = read(PROFILES_FILE, {})
        if not isinstance(self.profiles, dict):
            self.profiles = {}
        self.current_profile = ""
        self.key_map = {}  # key -> profile name; pynput listener is optional
        self.keyboard_listener = None
        self.mouse_listener = None
        self.key_bridge = KeyBridge(self)
        self.key_bridge.profile_requested.connect(self.activate_profile_by_name)
        self.key_bridge.movement_requested.connect(self.set_movement_active)
        self.movement_active = False
        self.effect_timer = QTimer(self)
        self.effect_timer.timeout.connect(self.tick_effects)
        if self.premium_test_active and self.s.get("crosshair_animation", "Off") != "Off":
            self.effect_timer.start(33)
        self.dynamic_timer = QTimer(self)
        self.dynamic_timer.timeout.connect(self.update_dynamic_spread)
        if self.premium_test_active and self.s.get("dynamic_enabled"):
            self.dynamic_timer.start(16)
        self.setWindowTitle("Crosshair Studio")
        self.setMinimumSize(900, 700)
        self.setStyleSheet("""
            QMainWindow,QWidget{background:#111;color:#f2f2f2;font-family:Segoe UI}
            QFrame#panel{background:#191919;border:1px solid #303030;border-radius:12px}
            QPushButton{background:#eee;color:#111;border:0;border-radius:7px;padding:8px 11px;font-weight:600}
            QPushButton:hover{background:#d4d4d4}
            QPushButton:disabled{background:#444;color:#888}
            QComboBox,QListWidget,QLineEdit{background:#222;border:1px solid #444;border-radius:6px;padding:7px}
            QSlider::groove:horizontal{background:#393939;height:5px;border-radius:2px}
            QSlider::handle:horizontal{background:#eee;width:14px;margin:-5px 0;border-radius:7px}
            QCheckBox{spacing:7px}
            QScrollArea{border:0;background:transparent}
            QScrollBar:vertical{background:#202020;width:11px;margin:3px 1px 3px 1px;border-radius:5px}
            QScrollBar::handle:vertical{background:#777;border-radius:5px;min-height:28px}
            QScrollBar::handle:vertical:hover{background:#aaa}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0}
        """)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(24, 20, 24, 20)
        head = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("CROSSHAIR STUDIO")
        title.setStyleSheet("font-size:22px;font-weight:800;letter-spacing:2px")
        subtitle = QLabel("Custom crosshairs. Built for your setup.")
        subtitle.setStyleSheet("color:#999;font-size:12px")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        head.addLayout(titles)
        head.addStretch()
        self.status = QLabel("OVERLAY OFF")
        self.status.setStyleSheet("color:#999;font-size:11px;font-weight:700")
        head.addWidget(self.status)
        self.premium_button = QPushButton()
        self.premium_button.clicked.connect(self.show_premium)
        head.addWidget(self.premium_button)
        outer.addLayout(head)

        body = QHBoxLayout()
        outer.addLayout(body, 1)
        preview_panel = QFrame(objectName="panel")
        pv = QVBoxLayout(preview_panel)
        pv.addWidget(self.label("LIVE PREVIEW"))
        self.preview = Crosshair(self.s)
        self.preview.setStyleSheet("background:#252525;border-radius:8px")
        pv.addWidget(self.preview, 1)
        pv.addWidget(self.muted("Preview only · overlay appears at screen centre"))
        body.addWidget(preview_panel, 3)

        panel = QFrame(objectName="panel")
        c = QVBoxLayout(panel)
        c.addWidget(self.label("CUSTOMIZE"))
        c.addWidget(self.muted("Style"))
        self.style = QComboBox()
        self.style.addItems(["Plus", "Cross", "Dot", "Circle", "T", "Shotgun", "Diamond", "Image"])
        self.style.setCurrentText(self.s["style"])
        self.style.currentTextChanged.connect(self.on_style_changed)
        c.addWidget(self.style)
        self.color_btn = QPushButton("Choose primary colour")
        self.color_btn.clicked.connect(self.choose_color)
        c.addWidget(self.color_btn)
        self.color2_btn = QPushButton("Choose second colour")
        self.color2_btn.clicked.connect(self.choose_color2)
        c.addWidget(self.color2_btn)
        self.gradient_box = QCheckBox("Gradient colours (Premium)")
        self.gradient_box.setChecked(self.s.get("gradient", False))
        self.gradient_box.stateChanged.connect(self.set_gradient)
        c.addWidget(self.gradient_box)
        self.animation_box = QCheckBox("Animated RGB (Premium)")
        self.animation_box.setChecked(self.s.get("animated", False))
        self.animation_box.stateChanged.connect(self.set_animated)
        c.addWidget(self.animation_box)
        imp = QPushButton("Import Image · PNG / JPG / SVG")
        imp.clicked.connect(self.import_image)
        c.addWidget(imp)
        creator = QPushButton("Open Crosshair Creator · Premium")
        self.creator_button = creator
        creator.clicked.connect(self.open_creator)
        c.addWidget(creator)
        contrast = QPushButton("Enable Contrast Mode · Premium")
        contrast.clicked.connect(self.open_contrast)
        c.addWidget(contrast)
        effects = QFrame()
        effects_layout = QVBoxLayout(effects)
        effects_layout.setContentsMargins(0, 8, 0, 4)
        effects_layout.addWidget(self.label("PREMIUM EFFECTS"))
        self.dynamic_box = QCheckBox("Dynamic Crosshair · WASD spread")
        self.dynamic_box.setChecked(bool(self.s.get("dynamic_enabled", False)))
        self.dynamic_box.stateChanged.connect(self.set_dynamic)
        effects_layout.addWidget(self.dynamic_box)
        effects_layout.addWidget(self.muted("Spread amount"))
        self.dynamic_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.dynamic_strength_slider.setRange(2, 20)
        self.dynamic_strength_slider.setValue(int(self.s.get("dynamic_strength", 9)))
        self.dynamic_strength_slider.valueChanged.connect(self.set_dynamic_strength)
        effects_layout.addWidget(self.dynamic_strength_slider)
        self.crosshair_anim = QComboBox()
        self.crosshair_anim.addItems(["Off", "Pulse", "Rotate", "Fade"])
        self.crosshair_anim.setCurrentText(self.s.get("crosshair_animation", "Off"))
        self.crosshair_anim.currentTextChanged.connect(self.set_crosshair_animation)
        effects_layout.addWidget(self.crosshair_anim)
        c.addWidget(effects)
        self.sliders = {}
        for key, label, lo, hi in [
            ("size","Size",4,100),("thickness","Thickness",1,12),
            ("gap","Centre gap",0,35),("opacity","Opacity",10,100)
        ]:
            c.addWidget(self.muted(label))
            row = QHBoxLayout()
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(lo, hi)
            slider.setValue(self.s[key])
            val = QLabel(str(self.s[key]))
            val.setMinimumWidth(28)
            slider.valueChanged.connect(lambda n,k=key,v=val: self.setval(k,n,v))
            row.addWidget(slider, 1)
            row.addWidget(val)
            c.addLayout(row)
            self.sliders[key] = slider
        self.visible = QCheckBox("Show crosshair")
        self.visible.setChecked(self.s["visible"])
        self.visible.stateChanged.connect(self.visibility)
        c.addWidget(self.visible)

        c.addWidget(self.label("PRESETS"))
        self.list = QListWidget()
        self.list.setMaximumHeight(125)
        c.addWidget(self.list)
        self.reload_presets()
        row = QHBoxLayout()
        for text, fn in [("Save as...",self.save_preset),("Apply",self.apply_preset),("Update / copy",self.update_selected_preset),("Delete",self.delete_preset)]:
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        c.addLayout(row)
        c.addStretch()
        # The Customize column is taller than the available window on smaller
        # displays. Put the whole panel in a real scroll area so every control
        # remains reachable and the scrollbar is visible when needed.
        customize_scroll = QScrollArea()
        customize_scroll.setWidgetResizable(True)
        customize_scroll.setFrameShape(QFrame.Shape.NoFrame)
        customize_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        customize_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        customize_scroll.setWidget(panel)
        customize_scroll.setMinimumWidth(300)
        body.addWidget(customize_scroll, 2)

        profile_panel = QFrame(objectName="panel")
        pr = QVBoxLayout(profile_panel)
        pr.addWidget(self.label("PROFILES"))
        self.profile_list = QListWidget()
        self.profile_list.setMaximumHeight(90)
        pr.addWidget(self.profile_list)
        row = QHBoxLayout()
        for text, fn in [("Save profile",self.save_profile),("Load",self.load_profile),("Delete",self.delete_profile)]:
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        pr.addLayout(row)
        row = QHBoxLayout()
        hotkey = QPushButton("Set key / mouse bind · Premium")
        hotkey.clicked.connect(self.set_key_trigger)
        game = QPushButton("Set game trigger · Premium")
        game.clicked.connect(self.set_game_trigger)
        row.addWidget(hotkey)
        row.addWidget(game)
        pr.addLayout(row)
        export = QPushButton("Export / backup profiles")
        export.clicked.connect(self.export_profiles)
        pr.addWidget(export)
        self.profile_help = self.muted("Save and load profiles for free. Premium is required to assign keyboard/mouse hotkeys or automatic game triggers.")
        pr.addWidget(self.profile_help)
        outer.addWidget(profile_panel)

        bottom = QHBoxLayout()
        self.toggle = QPushButton("Enable overlay")
        self.toggle.clicked.connect(self.toggle_overlay)
        bottom.addWidget(self.toggle)
        save = QPushButton("Save settings")
        save.clicked.connect(self.save)
        bottom.addWidget(save)
        reset = QPushButton("Reset")
        reset.clicked.connect(self.reset)
        bottom.addWidget(reset)
        outer.addLayout(bottom)
        outer.addWidget(self.muted("Ctrl+O toggles overlay and Ctrl+S saves settings while this app is focused. Game compatibility varies; use Windowed Fullscreen if needed."))

        self.overlay = Crosshair(self.s, True)
        self.contrast_timer = QTimer(self)
        self.contrast_timer.timeout.connect(self.sample_contrast)
        self.contrast_window = None
        self.contrast_original_color = None
        self.update_premium_button()
        self.apply_premium_gates()
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.animate)
        # No background timer when RGB animation is disabled.
        if self.premium_test_active and self.s.get("animated"):
            self.animation_timer.start(40)
        self.game_timer = QTimer(self)
        self.game_timer.timeout.connect(self.check_game_profile)
        if self.premium_test_active and any(d.get("game") for d in self.profiles.values()):
            self.game_timer.start(1200)
        self.load_profile_metadata()
        # Start global input listeners after the UI and profile data are ready.
        # Previously they only started after the user rebound a key.
        if any(data.get("key") for data in self.profiles.values()) or self.s.get("dynamic_enabled"):
            QTimer.singleShot(250, self.start_key_listener)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.toggle_overlay)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save)
        self.refresh()
        QTimer.singleShot(350, lambda: self.start_premium_request(
            "status", {"p_device_id": self.device_id}
        ))
        # Check for a newer release after the main window has appeared.
        QTimer.singleShot(1800, self.check_for_updates)

    def start_premium_request(self, operation, payload):
        worker = PremiumWorker(operation, payload, self)
        worker.result.connect(self.on_premium_result)
        self.premium_workers.append(worker)
        worker.start()

    def on_premium_result(self, operation, data, error):
        if operation == "status":
            self.premium_status_checked = not bool(error)
            self.premium_test_active = bool(data) if not error else False
            if self.premium_test_active:
                self.s.update(self.pending_premium_settings)
                self.style.setCurrentText(self.s.get("style", "Plus"))
                self.gradient_box.setChecked(bool(self.s.get("gradient", False)))
                self.animation_box.setChecked(bool(self.s.get("animated", False)))
                self.dynamic_box.setChecked(bool(self.s.get("dynamic_enabled", False)))
                self.crosshair_anim.setCurrentText(self.s.get("crosshair_animation", "Off"))
                self.refresh()
            else:
                self.s["gradient"] = False
                self.s["animated"] = False
                self.s["dynamic_enabled"] = False
                self.s["crosshair_animation"] = "Off"
                if self.style.currentText() in ("Shotgun", "Diamond", "Image"):
                    self.style.setCurrentText("Plus")
                self.gradient_box.setChecked(False)
                self.animation_box.setChecked(False)
                self.dynamic_box.setChecked(False)
                self.crosshair_anim.setCurrentText("Off")
                self.refresh()
            self.update_premium_button()
            self.apply_premium_gates()
            if self.premium_test_active:
                if self.s.get("animated") and not self.animation_timer.isActive():
                    self.animation_timer.start(40)
                if self.s.get("crosshair_animation", "Off") != "Off":
                    self.effect_timer.start(33)
                if self.s.get("dynamic_enabled"):
                    self.dynamic_timer.start(16)
                if any(d.get("game") for d in self.profiles.values()):
                    self.game_timer.start(1200)
            return

        try:
            self.premium_redeem_button.setEnabled(True)
        except (AttributeError, RuntimeError):
            pass
        if error:
            QMessageBox.warning(
                self, "Premium verification unavailable",
                "Crosshair Studio couldn't contact the Premium server. Check your internet connection and try again.\n\n"
                + error
            )
            return
        if isinstance(data, dict) and data.get("ok"):
            self.premium_test_active = True
            self.update_premium_button()
            self.apply_premium_gates()
            if self.s.get("crosshair_animation", "Off") != "Off":
                self.effect_timer.start(33)
            if self.s.get("dynamic_enabled"):
                self.dynamic_timer.start(16)
            if any(d.get("game") for d in self.profiles.values()):
                self.game_timer.start(1200)
            QMessageBox.information(
                self, "Premium activated",
                "Crosshair Studio Premium is now active on this device."
            )
        else:
            message = data.get("message", "That code is invalid or has already been redeemed.") if isinstance(data, dict) else "That code is invalid or has already been redeemed."
            QMessageBox.warning(self, "Code not accepted", message)

    def redeem_premium_code(self, code):
        cleaned = str(code or "").strip()
        if not cleaned:
            QMessageBox.information(self, "Enter a code", "Type your Premium code first.")
            return
        if self.premium_test_active:
            QMessageBox.information(self, "Premium active", "Premium is already active on this device.")
            return
        if hasattr(self, "premium_redeem_button"):
            self.premium_redeem_button.setEnabled(False)
        self.start_premium_request(
            "redeem",
            {"p_code": cleaned, "p_device_id": self.device_id}
        )

    def check_for_updates(self):
        if getattr(self, "update_worker", None) and self.update_worker.isRunning():
            return
        self.update_worker = UpdateWorker(parent=self)
        self.update_worker.checked.connect(self.on_update_check_result)
        self.update_worker.failed.connect(lambda _message: None)
        self.update_worker.start()

    def on_update_check_result(self, info):
        if not info:
            return
        answer = QMessageBox.question(
            self, "Crosshair Studio update available",
            f"Version {info['version']} is available. You have {APP_VERSION}.\n\n"
            "Download and install this update now? Your saved profiles and settings are kept.\n\n"
            "The installer is verified with SHA-256 before it runs.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.update_worker = UpdateWorker(info["installer"], info["checksum"], self)
        self.update_worker.downloaded.connect(self.launch_verified_update)
        self.update_worker.failed.connect(lambda message: QMessageBox.warning(self, "Update failed", message))
        self.update_worker.start()

    def launch_verified_update(self, installer_path):
        if not getattr(sys, "frozen", False):
            QMessageBox.information(self, "Update downloaded", "The installer was downloaded and verified. Close the source version and run the installer manually.")
            return
        app_exe = Path(sys.executable).resolve()
        installer = Path(installer_path).resolve()
        script = Path(tempfile.gettempdir()) / "CrosshairStudio_Update_Install.bat"
        pid = os.getpid()
        script.write_text(
            "@echo off\r\n"
            f":wait\r\ntasklist /FI \"PID eq {pid}\" | find \"{pid}\" >nul\r\n"
            "if not errorlevel 1 (timeout /t 1 /nobreak >nul & goto wait)\r\n"
            f'start /wait "" "{installer}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART\r\n'
            f'start "" "{app_exe}"\r\n'
            'del "%~f0"\r\n', encoding="utf-8"
        )
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(["cmd.exe", "/c", str(script)], creationflags=flags)
        QApplication.quit()

    def on_style_changed(self, value):
        if value in ("Shotgun", "Diamond", "Image") and not self.require_premium():
            self.style.blockSignals(True)
            self.style.setCurrentText("Plus")
            self.style.blockSignals(False)
            self.s["style"] = "Plus"
            self.refresh()
            return
        self.refresh()

    def open_creator(self):
        if not self.require_premium():
            return
        CrosshairCreator(self).exec()

    def open_contrast(self):
        if not self.require_premium():
            return
        if self.contrast_timer.isActive():
            self.stop_contrast()
            return
        self.contrast_original_color = self.s.get("color", "#ffffff")
        self.contrast_window = ContrastWindow(self)
        self.contrast_window.finished.connect(lambda _result: self.stop_contrast())
        self.contrast_window.show()
        # Screen capture is frame-limited; the overlay recolours every visible pixel independently.
        self.contrast_timer.start(50)
        self.sample_contrast()

    def sample_contrast(self):
        screen = QApplication.primaryScreen()
        if not screen:
            if self.contrast_window:
                self.contrast_window.status.setText("Screen capture unavailable: Windows did not report a display.")
            return
        geometry = screen.geometry()
        cx = geometry.x() + geometry.width() // 2
        cy = geometry.y() + geometry.height() // 2
        # The overlay is a 256x256 window centred on the display. Capturing this
        # entire footprint lets each crosshair pixel use its own local background.
        capture = screen.grabWindow(0, cx - 128, cy - 128, 256, 256).toImage()
        if capture.isNull():
            if self.contrast_window:
                self.contrast_window.status.setText("Screen capture unavailable. Switch Fortnite to Windowed Fullscreen and try again.")
            return
        self.overlay.contrast_background = capture
        self.preview.contrast_background = capture
        self.preview.update()
        self.overlay.update()
        if self.contrast_window:
            self.contrast_window.status.setText(
                "Per-pixel contrast active · each visible crosshair pixel adapts to the background directly behind it. "
                "Windowed Fullscreen is recommended."
            )

    def stop_contrast(self):
        if self.contrast_timer.isActive():
            self.contrast_timer.stop()
        self.preview.contrast_background = None
        self.overlay.contrast_background = None
        if self.contrast_original_color:
            self.s["color"] = self.contrast_original_color
            self.contrast_original_color = None
            self.preview.update_settings(self.s)
            self.overlay.update_settings(self.s)
        window = self.contrast_window
        self.contrast_window = None
        if window and window.isVisible():
            window.blockSignals(True)
            window.close()

    def label(self, text):
        l = QLabel(text)
        l.setStyleSheet("font-size:10px;color:#999;font-weight:700")
        return l

    def muted(self, text):
        l = QLabel(text)
        l.setStyleSheet("color:#888;font-size:10px")
        l.setWordWrap(True)
        return l

    def require_premium(self):
        if self.premium_test_active:
            return True
        QMessageBox.information(self, "Premium feature", "This feature requires Crosshair Studio Premium. Open Get Premium and redeem a valid one-time code.")
        return False

    def apply_premium_gates(self):
        enabled = self.premium_test_active
        for widget in (self.color2_btn, self.gradient_box, self.animation_box):
            widget.setEnabled(enabled)
        self.profile_list.setEnabled(True)
        # The preset library is intentionally fully free.
        self.creator_button.setEnabled(True) if hasattr(self, "creator_button") else None
        for widget_name in ("dynamic_box", "dynamic_strength_slider", "crosshair_anim"):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.setEnabled(enabled)

    def update_premium_button(self):
        self.premium_button.setText("PREMIUM ACTIVE" if self.premium_test_active else "Get Premium · €3")

    def show_premium(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Crosshair Studio Premium")
        dialog.setMinimumWidth(520)
        layout = QVBoxLayout(dialog)
        title = QLabel("CROSSHAIR STUDIO PREMIUM")
        title.setStyleSheet("font-size:19px;font-weight:800")
        layout.addWidget(title)
        price = QLabel("€3 — ONE-TIME PAYMENT")
        price.setStyleSheet("font-size:17px;font-weight:800;color:#7ee787")
        layout.addWidget(price)
        desc = QLabel("PREMIUM FEATURES\n\n• Advanced Drawing Studio: freehand, lines, premade shapes, selection, move, copy/paste, rotational 2-way and 4-way mirror, undo/redo\n• Per-pixel Auto Contrast Mode: every visible crosshair pixel adapts to the background directly behind it\n• Dynamic Crosshair: smooth WASD-reactive spread (input-based approximation)\n• Crosshair animations: pulse, rotate, fade and smooth transitions\n• RGB and gradient colours\n• PNG/JPG/SVG image uploads and custom image crosshairs\n• Advanced reticle styles\n• Keyboard/mouse profile hotkeys (press or release)\n• Automatic game profile switching\n• Profile export and backup\n\nALL PRESETS ARE FREE. Free users can save and load profiles, but assigning hotkeys requires Premium.\n\nDynamic spread reacts to WASD key input, not Fortnite weapon state.")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        note = QLabel("Redeem a one-time Premium code below. A successful code is consumed globally and activates Premium on this device. Online checkout is not connected yet.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#c9a66b;font-size:11px")
        layout.addWidget(note)
        code_label = QLabel("PREMIUM REDEMPTION CODE")
        code_label.setStyleSheet("font-size:10px;color:#999;font-weight:700")
        layout.addWidget(code_label)
        code_input = QLineEdit()
        code_input.setPlaceholderText("Enter your Premium code")
        code_input.setMaxLength(100)
        layout.addWidget(code_input)
        self.premium_redeem_button = QPushButton("Redeem code")
        self.premium_redeem_button.clicked.connect(
            lambda: self.redeem_premium_code(code_input.text())
        )
        layout.addWidget(self.premium_redeem_button)
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def set_dynamic(self, state):
        if state and not self.require_premium():
            self.dynamic_box.setChecked(False); return
        self.s["dynamic_enabled"] = bool(state)
        if state:
            self.dynamic_timer.start(16)
            if not (self.keyboard_listener or self.mouse_listener): self.start_key_listener()
        else:
            self.dynamic_timer.stop()
            self.movement_active = False
            self.s["dynamic_spread"] = 0.0
        self.refresh()

    def set_crosshair_animation(self, value):
        if value != "Off" and not self.require_premium():
            self.crosshair_anim.setCurrentText("Off"); return
        self.s["crosshair_animation"] = value
        if value == "Off": self.effect_timer.stop()
        elif not self.effect_timer.isActive(): self.effect_timer.start(33)
        self.refresh()

    def set_dynamic_strength(self, value):
        self.s["dynamic_strength"] = int(value)

    def set_movement_active(self, active):
        self.movement_active = bool(active)

    def update_dynamic_spread(self):
        target = float(self.s.get("dynamic_strength", 9)) if self.movement_active and self.s.get("dynamic_enabled") else 0.0
        current = float(self.s.get("dynamic_spread", 0.0))
        nxt = current + (target-current)*0.22
        if abs(nxt-current) > 0.08:
            self.s["dynamic_spread"] = nxt
            self.preview.update(); self.overlay.update()

    def tick_effects(self):
        anim = self.s.get("crosshair_animation", "Off")
        if anim != "Off":
            self.s["effect_phase"] = (float(self.s.get("effect_phase", 0.0)) + 0.12) % (math.pi*2)
            self.preview.update(); self.overlay.update()

    def setval(self, key, value, label):
        self.s[key] = value
        label.setText(str(value))
        self.refresh()

    def choose_color(self):
        col = QColorDialog.getColor(QColor(self.s["color"]), self, "Choose primary colour")
        if col.isValid():
            self.s["color"] = col.name()
            self.refresh()

    def choose_color2(self):
        if not self.require_premium():
            return
        col = QColorDialog.getColor(QColor(self.s.get("color2", "#00d9ff")), self, "Choose second colour")
        if col.isValid():
            self.s["color2"] = col.name()
            self.refresh()

    def set_gradient(self, state):
        if state and not self.require_premium():
            self.gradient_box.setChecked(False)
            return
        self.s["gradient"] = bool(state)
        self.refresh()

    def set_animated(self, state):
        if state and not self.require_premium():
            self.animation_box.setChecked(False)
            return
        self.s["animated"] = bool(state)
        if self.s["animated"]:
            if not self.animation_timer.isActive():
                self.animation_timer.start(40)
        else:
            self.animation_timer.stop()
        self.refresh()

    def animate(self):
        if self.s.get("animated"):
            self.preview.phase = (self.preview.phase + 1) % 120
            self.overlay.phase = (self.overlay.phase + 1) % 120
            self.preview.update()
            self.overlay.update()

    def import_image(self):
        if not self.require_premium():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Choose crosshair image", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp *.svg)")
        if path:
            if path.lower().endswith(".svg"):
                valid = QSvgRenderer(path).isValid()
            else:
                reader = QImageReader(path)
                reader.setAutoTransform(True)
                valid = not reader.read().isNull()
            if not valid:
                QMessageBox.warning(
                    self, "Image error",
                    "This image could not be read. Choose a valid PNG, JPG, JPEG, BMP, WEBP or SVG file."
                )
                return
            self.s["image_path"] = str(Path(path).expanduser().resolve())
            self.style.setCurrentText("Image")
            self.refresh()

    def visibility(self, state):
        self.s["visible"] = (state == Qt.CheckState.Checked.value)
        self.refresh()

    def refresh(self):
        if self.premium_status_checked and not self.premium_test_active:
            self.s["gradient"] = False
            self.s["animated"] = False
            if self.style.currentText() in ("Shotgun", "Diamond", "Image"):
                self.style.blockSignals(True)
                self.style.setCurrentText("Plus")
                self.style.blockSignals(False)
        self.s["style"] = self.style.currentText()
        self.preview.update_settings(self.s)
        self.overlay.update_settings(self.s)
        self.color_btn.setText("Primary: " + self.s["color"])
        self.color2_btn.setText("Second: " + self.s.get("color2", "#00d9ff"))

    def toggle_overlay(self):
        if self.overlay.isVisible():
            self.overlay.hide()
            self.toggle.setText("Enable overlay")
            self.status.setText("OVERLAY OFF")
        else:
            screen = QApplication.primaryScreen()
            if screen:
                self.overlay.setGeometry(self.overlay.overlay_geometry(screen))
            self.overlay.show()
            self.toggle.setText("Disable overlay")
            self.status.setText("OVERLAY ON")

    def save(self):
        self.s["style"] = self.style.currentText()
        data = dict(self.s)
        data["premium_device_id"] = self.device_id
        write(SETTINGS_FILE, data)
        QMessageBox.information(self, "Saved", "Settings saved on this PC.")

    def reload_presets(self):
        self.list.clear()
        names = list(BUILTINS) + list(PREMIUM_PRESETS) + list(self.presets)
        for name in names:
            self.list.addItem(name)

    def save_preset(self):
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:")
        if ok and name.strip():
            self.presets[name.strip()] = {k:self.s[k] for k in DEFAULT if k in self.s}
            write(PRESETS_FILE, self.presets)
            self.reload_presets()

    def update_selected_preset(self):
        item = self.list.currentItem()
        if not item:
            QMessageBox.information(self, "Select preset", "Select a preset first, then adjust its size, thickness, gap or colours.")
            return
        name = item.text()
        snapshot = {k:self.s.get(k) for k in DEFAULT}
        if name in self.presets:
            self.presets[name] = snapshot
            write(PRESETS_FILE, self.presets)
            QMessageBox.information(self, "Preset updated", f"'{name}' was updated with your current settings.")
        else:
            suggested = name + " Custom"
            new_name, ok = QInputDialog.getText(self, "Save edited preset", "Save your adjusted copy as:", text=suggested)
            if ok and new_name.strip():
                self.presets[new_name.strip()] = snapshot
                write(PRESETS_FILE, self.presets)
                self.reload_presets()
                QMessageBox.information(self, "Preset saved", "Your customized preset is now in your preset list.")

    def apply_preset(self):
        item = self.list.currentItem()
        if not item:
            return
        data = BUILTINS.get(item.text(), PREMIUM_PRESETS.get(item.text(), self.presets.get(item.text())))
        if data:
            self.s.update(data)
            self.style.setCurrentText(self.s["style"])
            for key, slider in self.sliders.items():
                slider.setValue(self.s[key])
            self.visible.setChecked(self.s["visible"])
            self.gradient_box.setChecked(self.s.get("gradient", False))
            self.animation_box.setChecked(self.s.get("animated", False))
            self.refresh()

    def delete_preset(self):
        item = self.list.currentItem()
        if item and item.text() in self.presets:
            del self.presets[item.text()]
            write(PRESETS_FILE, self.presets)
            self.reload_presets()

    def save_profile(self):
        name, ok = QInputDialog.getText(self, "Save profile", "Profile name:")
        if not ok:
            return

        name = name.strip()
        if not name:
            QMessageBox.information(self, "Profile name required", "Enter a name for this profile, then press Save profile again.")
            return

        previous = self.profiles.get(name, {})
        self.profiles[name] = {
            "settings": {k: self.s.get(k) for k in DEFAULT},
            "key": previous.get("key", "") if isinstance(previous, dict) else "",
            "game": previous.get("game", "") if isinstance(previous, dict) else ""
        }
        try:
            write(PROFILES_FILE, self.profiles)
        except Exception as exc:
            QMessageBox.critical(
                self, "Could not save profile",
                "Crosshair Studio could not write your profile file. "
                f"Data location: {PROFILES_FILE}\\n\\nError: {exc}"
            )
            return

        self.load_profile_metadata()
        for row_index in range(self.profile_list.count()):
            if self.profile_list.item(row_index).text().split("  [", 1)[0] == name:
                self.profile_list.setCurrentRow(row_index)
                break
        self.current_profile = name
        QMessageBox.information(
            self, "Profile saved",
            f'"{name}" was saved successfully.\\n\\nProfiles are stored in your Windows AppData folder and will remain available after restarting the app.'
        )

    def load_profile_metadata(self):
        self.profile_list.clear()
        for name, data in self.profiles.items():
            key = data.get("key", "")
            game = data.get("game", "")
            suffix = f"  [key: {key}]" if key else ""
            suffix += f"  [game: {game}]" if game else ""
            self.profile_list.addItem(name + suffix)

    def selected_profile_name(self):
        item = self.profile_list.currentItem()
        if not item:
            return ""
        return item.text().split("  [", 1)[0]

    def load_profile(self):
        name = self.selected_profile_name()
        if not name:
            return
        data = self.profiles.get(name, {}).get("settings", {})
        self.s.update(data)
        self.style.setCurrentText(self.s.get("style", "Plus"))
        for key, slider in self.sliders.items():
            slider.setValue(self.s.get(key, DEFAULT[key]))
        self.visible.setChecked(self.s.get("visible", True))
        self.gradient_box.setChecked(self.s.get("gradient", False))
        self.animation_box.setChecked(self.s.get("animated", False))
        self.current_profile = name
        self.refresh()

    def delete_profile(self):
        name = self.selected_profile_name()
        if name and name in self.profiles:
            del self.profiles[name]
            write(PROFILES_FILE, self.profiles)
            self.load_profile_metadata()

    def set_key_trigger(self):
        if not self.require_premium():
            return
        name = self.selected_profile_name()
        if not name:
            QMessageBox.information(self, "Select profile", "Select a saved profile first.")
            return
        current = self.profiles.get(name, {}).get("key", "")
        dialog = BindDialog(current, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and getattr(dialog, "done_with_bind", ""):
            bind = dialog.done_with_bind
            for profile in self.profiles.values():
                if profile.get("key") == bind:
                    profile["key"] = ""
            self.profiles[name]["key"] = bind
            write(PROFILES_FILE, self.profiles)
            self.start_key_listener()
            self.load_profile_metadata()

    def start_key_listener(self):
        # Stop any previous listeners before starting replacements.
        for attr in ("keyboard_listener", "mouse_listener"):
            listener = getattr(self, attr, None)
            if listener:
                try:
                    listener.stop()
                    listener.join(timeout=0.5)
                except Exception:
                    pass
                setattr(self, attr, None)

        # Avoid creating global listeners if no profile has a bind.
        need_effect_listener = bool(self.s.get("dynamic_enabled"))
        if not any(data.get("key") for data in self.profiles.values()) and not need_effect_listener:
            self.profile_help.setText(
                "No profile binds are set yet. Save a profile and assign a key or mouse bind."
            )
            return

        try:
            from pynput import keyboard, mouse

            def activate_for(device, value, mode):
                event_bind = f"{device}:{value}:{mode}".lower()
                legacy_bind = f"{device}:{value}".lower()
                for profile_name, data in self.profiles.items():
                    saved_bind = data.get("key", "").lower()
                    # Older saved binds had no mode suffix; treat them as press binds.
                    if saved_bind == event_bind or (mode == "press" and saved_bind == legacy_bind):
                        self.key_bridge.profile_requested.emit(profile_name)
                        break

            def key_value(key):
                try:
                    return key.char.lower()
                except AttributeError:
                    return str(key).replace("Key.", "").lower()

            movement_keys = {"w", "a", "s", "d"}
            movement_down = set()
            def on_press(key):
                value = key_value(key)
                activate_for("key", value, "press")
                if value in movement_keys and self.s.get("dynamic_enabled"):
                    movement_down.add(value)
                    self.key_bridge.movement_requested.emit(True)

            def on_release(key):
                value = key_value(key)
                activate_for("key", value, "release")
                if value in movement_down:
                    movement_down.discard(value)
                    self.key_bridge.movement_requested.emit(bool(movement_down))

            def on_click(x, y, button, pressed):
                value = str(button).replace("Button.", "").lower()
                activate_for("mouse", value, "press" if pressed else "release")

            def on_scroll(x, y, dx, dy):
                if dy:
                    direction = "scroll_up" if dy > 0 else "scroll_down"
                    activate_for("mouse", direction, "press")

            self.keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self.mouse_listener = mouse.Listener(
                on_click=on_click, on_scroll=on_scroll
            )
            self.keyboard_listener.daemon = True
            self.mouse_listener.daemon = True
            self.keyboard_listener.start()
            self.mouse_listener.start()
            self.profile_help.setText(
                "Input listener active. Profile binds work as configured; WASD drives Dynamic Crosshair."
            )
        except Exception as exc:
            self.keyboard_listener = None
            self.mouse_listener = None
            self.profile_help.setText(
                "Input listener unavailable. Check that pynput is installed."
            )
            print("Crosshair Studio input listener error:", exc)

    def activate_profile_by_name(self, name):
        if name not in self.profiles:
            return
        data = self.profiles[name].get("settings", {})
        self.s.update(data)
        self.style.setCurrentText(self.s.get("style", "Plus"))
        for key, slider in self.sliders.items():
            slider.setValue(self.s.get(key, DEFAULT[key]))
        self.visible.setChecked(self.s.get("visible", True))
        self.gradient_box.setChecked(self.s.get("gradient", False))
        self.animation_box.setChecked(self.s.get("animated", False))
        self.current_profile = name
        self.refresh()

    def set_game_trigger(self):
        if not self.require_premium():
            return
        name = self.selected_profile_name()
        if not name:
            QMessageBox.information(self, "Select profile", "Select a saved profile first.")
            return
        exe, ok = QInputDialog.getText(self, "Game profile", "Game executable name (example: FortniteClient-Win64-Shipping.exe):")
        if ok and exe.strip():
            self.profiles[name]["game"] = Path(exe.strip()).name.lower()
            write(PROFILES_FILE, self.profiles)
            self.load_profile_metadata()

    def foreground_process_name(self):
        if os.name != "nt":
            return ""
        try:
            import ctypes
            from ctypes import wintypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            pid = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
            if not handle:
                return ""
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buf))
            ok = ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
            ctypes.windll.kernel32.CloseHandle(handle)
            return Path(buf.value).name.lower() if ok else ""
        except Exception:
            return ""

    def check_game_profile(self):
        if not self.premium_test_active:
            return
        exe = self.foreground_process_name()
        if not exe:
            return
        for name, data in self.profiles.items():
            if data.get("game", "").lower() == exe and self.current_profile != name:
                self.activate_profile_by_name(name)
                break

    def export_profiles(self):
        if not self.require_premium():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export profiles", "crosshair_profiles_backup.json", "JSON files (*.json)")
        if path:
            write(Path(path), self.profiles)
            QMessageBox.information(self, "Export complete", "Your profile backup was exported.")

    def reset(self):
        self.s = DEFAULT.copy()
        self.style.setCurrentText(self.s["style"])
        for key, slider in self.sliders.items():
            slider.setValue(self.s[key])
        self.visible.setChecked(True)
        self.gradient_box.setChecked(False)
        self.animation_box.setChecked(False)
        self.refresh()

    def closeEvent(self, event):
        self.stop_contrast()
        for timer_name in ("effect_timer", "dynamic_timer"):
            timer = getattr(self, timer_name, None)
            if timer and timer.isActive(): timer.stop()
        self.overlay.hide()
        for listener_name in ("keyboard_listener", "mouse_listener"):
            listener = getattr(self, listener_name, None)
            if listener:
                try:
                    listener.stop()
                except Exception:
                    pass
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Crosshair Studio")
    window = Main()
    window.show()
    sys.exit(app.exec())