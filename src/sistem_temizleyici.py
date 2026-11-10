#!/usr/bin/env python3
"""Sistem Temizleyici / System Cleaner - CachyOS / Arch için grafik arayüzlü disk temizleme aracı."""
import os
import re
import glob
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

from PyQt6.QtCore import QLibraryInfo, QObject, Qt, QThread, QTranslator, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSpinBox,
    QSplitter, QVBoxLayout, QWidget,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from i18n import DECIMAL, LANG, STRINGS, _  # noqa: E402

APP_NAME = _("app_name")
APP_VERSION = "1.1.1"
HOME = os.path.expanduser("~")
CACHE = os.path.join(HOME, ".cache")
TRASH = os.path.join(HOME, ".local/share/Trash")
ENV_C = dict(os.environ, LC_ALL="C", LANG="C")

INSTALLED_HELPER = "/usr/lib/sistem-temizleyici/helper.py"
LOCAL_HELPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helper.py")

# ~/.cache altında silinmesi güvenli bilinen klasörler (varsayılan olarak seçili gelir).
SAFE_APP_CACHES = {
    "google-chrome", "chromium", "BraveSoftware", "vivaldi", "opera", "mozilla",
    "zen", "librewolf", "net.imput.helium", "microsoft-edge", "falkon",
    "pip", "yarn", "go-build", "pnpm", "node-gyp", "typescript", "electron",
    "mesa_shader_cache", "mesa_shader_cache_db", "nvidia", "radv_builtin_shaders",
    "appstream", "discover", "gstreamer-1.0", "fontconfig", "spotify",
    "thumbnails-legacy", "kdenlive", "ZapZap",
}
# Ayrı kategorilerde ele alınanlar
SEPARATE_CACHES = {"thumbnails", "paru", "yay"}
# profile-sync-daemon çökme sonrası kurtarma yedekleri
PSD_GLOBS = [os.path.join(HOME, ".config/*-backup-crashrecovery-*"),
             os.path.join(HOME, ".mozilla/firefox/*-backup-crashrecovery-*")]
PSD_RE = re.compile(r"-backup-crashrecovery-\d{8}_\d{6}$")
SELECTABLE = ("app_cache", "orphans", "aur_cache", "psd_crash")
# AUR yardımcılarının -git paketlerini takip ettiği dosyalar: silinmez.
AUR_KEEP = {"vcs.json", "devel.json", "devel.toml"}
# Bunlardan biri çalışırken temizlik başlatılmaz.
PACMAN_LOCK = "/var/lib/pacman/db.lck"
PACKAGE_MANAGERS = ("pacman", "paru", "yay", "makepkg", "pamac")


def package_manager_busy():
    """Çalışan paket yöneticisinin adını (ya da 'pacman') döner; yoksa None."""
    if os.path.exists(PACMAN_LOCK):
        return "pacman"
    for name in PACKAGE_MANAGERS:
        if subprocess.run(["pgrep", "-x", name], capture_output=True).returncode == 0:
            return name
    return None


def psd_dirs():
    out = []
    for g in PSD_GLOBS:
        for p in glob.glob(g):
            if PSD_RE.search(p) and os.path.isdir(p) and not os.path.islink(p):
                out.append(p)
    return sorted(out)


# ----------------------------------------------------------------------------
# Yardımcı fonksiyonlar
# ----------------------------------------------------------------------------
def human(n):
    if n is None:
        return "—"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            text = f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
            return text.replace(".", DECIMAL)
        n /= 1024
    return f"{n:.1f} TB".replace(".", DECIMAL)


def parse_size(text):
    """'120.50 MiB' / '44.9M' / '1.2G' gibi ifadeleri bayta çevirir."""
    m = re.search(r"([\d.]+)\s*([KMGT]?)(i?B)?", text)
    if not m:
        return 0
    mult = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}[m.group(2)]
    return int(float(m.group(1)) * mult)


def du(path):
    if not os.path.exists(path):
        return 0
    try:
        out = subprocess.run(["du", "-sB1", path], capture_output=True, text=True)
        return int(out.stdout.split()[0]) if out.stdout else 0
    except Exception:
        return 0


def run_c(cmd, timeout=60):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, env=ENV_C,
                              timeout=timeout, stdin=subprocess.DEVNULL).stdout
    except Exception:
        return ""


def clear_dir_contents(path, log, keep=()):
    """Klasörün kendisini bırakıp içini boşaltır (keep içindeki adlar korunur).
    Silinen bayt miktarını döner."""
    if not os.path.isdir(path):
        return 0
    before = du(path)
    for name in os.listdir(path):
        if name in keep:
            continue
        p = os.path.join(path, name)
        try:
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                os.remove(p)
        except OSError as exc:
            log(_("log.skipped", p=p, e=exc.strerror))
    return max(0, before - du(path))


def disk_usage():
    u = shutil.disk_usage("/")
    return u.total, u.used, u.free


# ----------------------------------------------------------------------------
# Kategoriler
# ----------------------------------------------------------------------------
@dataclass
class Item:
    key: str
    label: str
    size: int | None
    checked: bool = True


@dataclass
class Category:
    key: str
    title: str
    desc: str
    icon: str
    root: bool = False
    default: bool = True
    warn: str = ""
    option: tuple | None = None  # (etiket, min, max, varsayılan, sonek)
    size: int | None = None
    info: str = ""
    items: list = field(default_factory=list)
    option_value: int = 0

    def selected_items(self):
        return [i for i in self.items if i.checked]

    def effective_size(self):
        if self.items and self.key in SELECTABLE:
            return sum(i.size or 0 for i in self.selected_items())
        return self.size


def make_categories():
    def cat(key, icon, **kw):
        if "option" in kw:
            kw["option"] = (_(f"{key}.option"),) + kw["option"]
        warn = f"{key}.warn"
        return Category(key, _(f"{key}.title"), _(f"{key}.desc"), icon,
                        warn=_(warn) if warn in STRINGS else "", **kw)

    cats = [
        cat("pkg_cache", "package-x-generic", root=True, option=(0, 3, 1, "")),
        cat("pkg_uninstalled", "edit-delete", root=True),
        cat("pkg_partial", "folder-download", root=True),
        cat("aur_cache", "folder-build"),
        cat("journal", "text-x-log", root=True, option=(50, 2000, 100, " MB")),
        cat("coredump", "tools-report-bug", root=True),
        cat("thumbnails", "image-x-generic"),
        cat("app_cache", "applications-internet"),
        cat("psd_crash", "document-revert", default=False),
        cat("flatpak", "flatpak-discover"),
        cat("trash", "user-trash-full", default=False),
        cat("orphans", "dialog-warning", root=True, default=False),
    ]
    for c in cats:
        if c.option:
            c.option_value = c.option[3]
    return cats


# ---- tarama fonksiyonları ---------------------------------------------------
def scan_category(c):
    c.items, c.info, c.size = [], "", 0
    k = c.key
    if k == "pkg_cache":
        out = run_c(["paccache", "-d", "-k", str(c.option_value)])
        m = re.search(r"(\d+) candidates? \(disk space saved: ([^)]+)\)", out)
        if m:
            c.size, c.info = parse_size(m.group(2)), _("info.files", n=m.group(1))
        else:
            c.info = _("info.clean")
    elif k == "pkg_uninstalled":
        out = run_c(["paccache", "-d", "-u", "-k", "0"])
        m = re.search(r"(\d+) candidates? \(disk space saved: ([^)]+)\)", out)
        if m:
            c.size, c.info = parse_size(m.group(2)), _("info.files", n=m.group(1))
        else:
            c.info = _("info.clean")
    elif k == "pkg_partial":
        try:
            n = sum(1 for x in os.listdir("/var/cache/pacman/pkg") if x.startswith("download-"))
        except OSError:
            n = 0
        c.size = None if n else 0
        c.info = _("info.partial", n=n) if n else _("info.clean")
    elif k == "aur_cache":
        for name in ("paru", "yay"):
            p = os.path.join(CACHE, name)
            if os.path.isdir(p):
                c.items.append(Item(name, f"~/.cache/{name}", du(p)))
        c.size = sum(i.size for i in c.items)
    elif k == "journal":
        out = run_c(["journalctl", "--disk-usage"])
        m = re.search(r"take up ([\d.]+[KMGT]?)", out)
        used = parse_size(m.group(1)) if m else 0
        c.size = max(0, used - c.option_value * 1024**2)
        c.info = _("info.now", size=human(used))
    elif k == "coredump":
        c.size = du("/var/lib/systemd/coredump")
    elif k == "thumbnails":
        c.size = du(os.path.join(CACHE, "thumbnails"))
    elif k == "app_cache":
        if os.path.isdir(CACHE):
            for name in sorted(os.listdir(CACHE)):
                p = os.path.join(CACHE, name)
                if name in SEPARATE_CACHES or not os.path.isdir(p) or os.path.islink(p):
                    continue
                size = du(p)
                if size < 1024 * 1024:  # 1 MB altını listeleme
                    continue
                c.items.append(Item(name, name, size, checked=name in SAFE_APP_CACHES))
            c.items.sort(key=lambda i: -(i.size or 0))
        c.size = sum(i.size for i in c.items)
    elif k == "psd_crash":
        for p in psd_dirs():
            label = p.replace(HOME, "~", 1)
            c.items.append(Item(p, label, du(p)))
        c.size = sum(i.size for i in c.items)
        c.info = "" if c.items else _("info.none")
    elif k == "flatpak":
        if shutil.which("flatpak"):
            try:
                out = subprocess.run(["flatpak", "uninstall", "--unused"], input="n\n",
                                     capture_output=True, text=True, env=ENV_C, timeout=60).stdout
            except Exception:
                out = ""
            refs = re.findall(r"^\s*\d+\.\s+\S", out, re.M)
            if "Nothing unused" in out or not refs:
                c.size, c.info = 0, _("info.clean")
            else:
                c.size, c.info = None, _("info.components", n=len(refs))
        else:
            c.info = _("info.no_flatpak")
    elif k == "trash":
        c.size = du(os.path.join(TRASH, "files")) + du(os.path.join(TRASH, "info"))
    elif k == "orphans":
        names = run_c(["pacman", "-Qdtq"]).split()
        if names:
            info = run_c(["pacman", "-Qi", *names])
            sizes = {}
            cur = None
            for line in info.splitlines():
                if line.startswith("Name"):
                    cur = line.split(":", 1)[1].strip()
                elif line.startswith("Installed Size") and cur:
                    sizes[cur] = parse_size(line.split(":", 1)[1])
            for n in names:
                c.items.append(Item(n, n, sizes.get(n, 0)))
        c.size = sum(i.size for i in c.items)
        c.info = _("info.packages", n=len(names)) if names else _("info.none")
    return c


# ----------------------------------------------------------------------------
# Arka plan işçileri
# ----------------------------------------------------------------------------
class ScanWorker(QObject):
    progress = pyqtSignal(str)
    one_done = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, cats):
        super().__init__()
        self.cats = cats

    def run(self):
        for c in self.cats:
            self.progress.emit(_("log.scanning", t=c.title))
            try:
                scan_category(c)
            except Exception as exc:  # noqa: BLE001
                c.info = _("info.error", e=exc)
            self.one_done.emit(c.key)
        self.finished.emit()


class CleanWorker(QObject):
    log = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, cats):
        super().__init__()
        self.cats = cats

    def run(self):
        ok = True
        root_args = []
        for c in self.cats:
            if c.root:
                if c.key == "pkg_cache":
                    root_args.append(f"pkg-cache:{c.option_value}")
                elif c.key == "pkg_uninstalled":
                    root_args.append("pkg-uninstalled")
                elif c.key == "pkg_partial":
                    root_args.append("pkg-partial")
                elif c.key == "journal":
                    root_args.append(f"journal:{c.option_value}")
                elif c.key == "coredump":
                    root_args.append("coredump")
                elif c.key == "orphans":
                    sel = [i.key for i in c.selected_items()]
                    if sel:
                        root_args.append("orphans:" + ",".join(sel))
                continue
            self.log.emit(f"### {c.title}")
            try:
                self.clean_user(c)
            except Exception as exc:  # noqa: BLE001
                self.log.emit(_("log.error", e=exc))
                ok = False

        if root_args:
            helper = INSTALLED_HELPER if os.path.exists(INSTALLED_HELPER) else LOCAL_HELPER
            self.log.emit(_("log.asking_admin"))
            try:
                cmd = ["pkexec", helper] if helper == INSTALLED_HELPER else ["pkexec", sys.executable, helper]
                proc = subprocess.Popen([*cmd, f"--lang={LANG}", *root_args],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout:
                    self.log.emit(line.rstrip())
                rc = proc.wait()
                if rc in (126, 127):
                    self.log.emit(_("log.denied"))
                    ok = False
                elif rc != 0:
                    ok = False
            except FileNotFoundError:
                self.log.emit(_("log.no_pkexec"))
                ok = False
        self.finished.emit(ok)

    def clean_user(self, c):
        log = self.log.emit
        if c.key == "aur_cache":
            for i in c.selected_items():
                freed = clear_dir_contents(os.path.join(CACHE, i.key), log, keep=AUR_KEEP)
                log(f"  ~/.cache/{i.key}: " + _("log.freed", size=human(freed)))
        elif c.key == "thumbnails":
            freed = clear_dir_contents(os.path.join(CACHE, "thumbnails"), log)
            log("  " + _("log.freed", size=human(freed)))
        elif c.key == "app_cache":
            for i in c.selected_items():
                freed = clear_dir_contents(os.path.join(CACHE, i.key), log)
                log(f"  {i.key}: " + _("log.freed", size=human(freed)))
        elif c.key == "psd_crash":
            allowed = set(psd_dirs())
            for i in c.selected_items():
                if i.key not in allowed:
                    log(_("log.skipped_gone", p=i.label))
                    continue
                size = du(i.key)
                shutil.rmtree(i.key, ignore_errors=True)
                log(f"  {i.label}: " + _("log.removed", size=human(size if not os.path.exists(i.key) else 0)))
        elif c.key == "trash":
            freed = 0
            for sub in ("files", "info", "expunged"):
                freed += clear_dir_contents(os.path.join(TRASH, sub), log)
            log("  " + _("log.freed", size=human(freed)))
        elif c.key == "flatpak":
            proc = subprocess.run(["flatpak", "uninstall", "--unused", "-y", "--noninteractive"],
                                  capture_output=True, text=True, stdin=subprocess.DEVNULL)
            for line in (proc.stdout + proc.stderr).splitlines():
                if line.strip():
                    log("  " + line)


# ----------------------------------------------------------------------------
# Arayüz
# ----------------------------------------------------------------------------
STYLE = """
QFrame#card { border: 1px solid palette(mid); border-radius: 10px; background: palette(base); }
QFrame#card[selected="true"] { border: 2px solid palette(highlight); }
QLabel#title { font-size: 11pt; font-weight: 600; }
QLabel#size { font-size: 12pt; font-weight: 700; }
QLabel#desc, QLabel#info { color: palette(placeholder-text); }
QLabel#warn { color: #d08770; }
QPushButton#primary { font-size: 12pt; font-weight: 700; padding: 10px 22px; }
QProgressBar { border-radius: 6px; height: 18px; text-align: center; }
"""


def info_box(parent, text):
    box = QMessageBox(QMessageBox.Icon.Information, APP_NAME, text, parent=parent)
    box.addButton(_("ui.ok"), QMessageBox.ButtonRole.AcceptRole)
    box.exec()


class DetailsDialog(QDialog):
    def __init__(self, cat, parent=None):
        super().__init__(parent)
        self.cat = cat
        self.setWindowTitle(_("ui.details_title", t=cat.title))
        self.resize(520, 520)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(_("ui.details_prompt")))
        self.list = QListWidget()
        for it in cat.items:
            w = QListWidgetItem(f"{it.label}    —    {human(it.size)}")
            w.setFlags(w.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            w.setCheckState(Qt.CheckState.Checked if it.checked else Qt.CheckState.Unchecked)
            self.list.addItem(w)
        lay.addWidget(self.list)
        row = QHBoxLayout()
        b_all = QPushButton(_("ui.select_all"))
        b_none = QPushButton(_("ui.select_none"))
        b_all.clicked.connect(lambda: self._set_all(True))
        b_none.clicked.connect(lambda: self._set_all(False))
        row.addWidget(b_all)
        row.addWidget(b_none)
        row.addStretch()
        lay.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(_("ui.ok"))
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText(_("ui.cancel"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _set_all(self, v):
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.CheckState.Checked if v else Qt.CheckState.Unchecked)

    def accept(self):
        for i, it in enumerate(self.cat.items):
            it.checked = self.list.item(i).checkState() == Qt.CheckState.Checked
        super().accept()


class CategoryCard(QFrame):
    changed = pyqtSignal()
    option_changed = pyqtSignal(str)

    def __init__(self, cat):
        super().__init__()
        self.cat = cat
        self.setObjectName("card")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)

        self.check = QCheckBox()
        self.check.setChecked(cat.default)
        self.check.toggled.connect(self._toggled)
        lay.addWidget(self.check)

        icon = QLabel()
        icon.setPixmap(QIcon.fromTheme(cat.icon, QIcon.fromTheme("edit-clear")).pixmap(32, 32))
        lay.addWidget(icon)

        mid = QVBoxLayout()
        t = QLabel(cat.title + ("  🔒" if cat.root else ""))
        t.setObjectName("title")
        t.setToolTip(_("ui.needs_admin") if cat.root else "")
        mid.addWidget(t)
        d = QLabel(cat.desc)
        d.setObjectName("desc")
        d.setWordWrap(True)
        mid.addWidget(d)
        if cat.warn:
            w = QLabel("⚠ " + cat.warn)
            w.setObjectName("warn")
            w.setWordWrap(True)
            mid.addWidget(w)
        lay.addLayout(mid, 1)

        if cat.option:
            label, lo, hi, _default, suffix = cat.option
            box = QVBoxLayout()
            box.addWidget(QLabel(label))
            self.spin = QSpinBox()
            self.spin.setRange(lo, hi)
            self.spin.setValue(cat.option_value)
            if suffix:
                self.spin.setSuffix(suffix)
                self.spin.setSingleStep(50)
            self.spin.valueChanged.connect(self._opt)
            box.addWidget(self.spin)
            lay.addLayout(box)

        right = QVBoxLayout()
        self.size_lbl = QLabel("…")
        self.size_lbl.setObjectName("size")
        self.size_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(self.size_lbl)
        self.info_lbl = QLabel("")
        self.info_lbl.setObjectName("info")
        self.info_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(self.info_lbl)
        self.details = QPushButton(_("ui.details"))
        self.details.setVisible(False)
        self.details.clicked.connect(self._details)
        right.addWidget(self.details, alignment=Qt.AlignmentFlag.AlignRight)
        lay.addLayout(right)
        self.setMinimumWidth(560)
        self._toggled(cat.default)

    def _toggled(self, v):
        self.setProperty("selected", "true" if v else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.changed.emit()

    def _opt(self, v):
        self.cat.option_value = v
        self.size_lbl.setText("…")
        self.option_changed.emit(self.cat.key)

    def _details(self):
        if DetailsDialog(self.cat, self).exec():
            self.refresh()
            self.changed.emit()

    def refresh(self):
        c = self.cat
        self.size_lbl.setText(human(c.effective_size()) if c.effective_size() is not None else "?")
        info = c.info
        if c.items and c.key in SELECTABLE:
            info = _("info.selected", a=len(c.selected_items()), b=len(c.items))
        self.info_lbl.setText(info)
        self.details.setVisible(bool(c.items))

    def is_checked(self):
        return self.check.isChecked()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon.fromTheme("edit-clear-all", QIcon.fromTheme("user-trash-full")))
        self.resize(900, 820)
        self.cats = make_categories()
        self.cards = {}
        self.thread = None
        self.free_before = 0

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 12)

        # Disk durumu
        head = QFrame()
        head.setObjectName("card")
        hl = QVBoxLayout(head)
        top = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(QIcon.fromTheme("drive-harddisk").pixmap(40, 40))
        top.addWidget(icon)
        tl = QVBoxLayout()
        h = QLabel(_("ui.system_disk"))
        h.setFont(QFont(h.font().family(), 13, QFont.Weight.Bold))
        tl.addWidget(h)
        self.disk_lbl = QLabel()
        tl.addWidget(self.disk_lbl)
        top.addLayout(tl, 1)
        self.total_lbl = QLabel()
        self.total_lbl.setFont(QFont(h.font().family(), 13, QFont.Weight.Bold))
        self.total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.total_lbl)
        hl.addLayout(top)
        self.disk_bar = QProgressBar()
        self.disk_bar.setRange(0, 1000)
        self.disk_bar.setTextVisible(False)
        hl.addWidget(self.disk_bar)
        root.addWidget(head)

        # Kategoriler
        splitter = QSplitter(Qt.Orientation.Vertical)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        holder = QWidget()
        cl = QVBoxLayout(holder)
        cl.setSpacing(8)
        for c in self.cats:
            card = CategoryCard(c)
            card.changed.connect(self.update_total)
            card.option_changed.connect(self.rescan_one)
            self.cards[c.key] = card
            cl.addWidget(card)
        cl.addStretch()
        scroll.setWidget(holder)
        splitter.addWidget(scroll)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText(_("ui.log_placeholder"))
        self.log_box.setFont(QFont("monospace", 9))
        splitter.addWidget(self.log_box)
        splitter.setSizes([600, 140])
        root.addWidget(splitter, 1)

        # Alt çubuk
        bottom = QHBoxLayout()
        self.status = QLabel("")
        bottom.addWidget(self.status, 1)
        self.scan_btn = QPushButton(QIcon.fromTheme("view-refresh"), _("ui.rescan"))
        self.scan_btn.clicked.connect(self.scan_all)
        bottom.addWidget(self.scan_btn)
        self.clean_btn = QPushButton(QIcon.fromTheme("edit-clear-all"), _("ui.clean"))
        self.clean_btn.setObjectName("primary")
        self.clean_btn.clicked.connect(self.clean)
        bottom.addWidget(self.clean_btn)
        root.addLayout(bottom)

        self.setCentralWidget(central)
        self.update_disk()
        self.scan_all()

    # -- yardımcılar --
    def log(self, text):
        self.log_box.appendPlainText(text)

    def busy(self, b):
        self.scan_btn.setEnabled(not b)
        self.clean_btn.setEnabled(not b)
        for card in self.cards.values():
            card.setEnabled(not b)

    def update_disk(self):
        total, used, free = disk_usage()
        self.disk_bar.setValue(int(used / total * 1000))
        self.disk_lbl.setText(_("ui.disk_line", used=human(used), free=human(free), total=human(total),
                                pct=f"{used / total * 100:.0f}"))
        return free

    def update_total(self):
        total, unknown = 0, False
        for c in self.cats:
            if self.cards[c.key].is_checked():
                s = c.effective_size()
                if s is None:
                    unknown = True
                else:
                    total += s
        self.total_lbl.setText(_("ui.to_gain") + f"\n{human(total)}{' +' if unknown else ''}")

    # -- tarama --
    def _start_scan(self, cats, done_cb=None):
        self.busy(True)
        self.thread = QThread()
        self.worker = ScanWorker(cats)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.status.setText)
        self.worker.one_done.connect(lambda k: (self.cards[k].refresh(), self.update_total()))

        def fin():
            self.thread.quit()
            self.thread.wait()
            self.busy(False)
            self.status.setText(_("ui.scan_done"))
            self.update_total()
            if done_cb:
                done_cb()
        self.worker.finished.connect(fin)
        self.thread.start()

    def scan_all(self):
        for card in self.cards.values():
            card.size_lbl.setText("…")
        self._start_scan(self.cats)

    def rescan_one(self, key):
        if self.thread and self.thread.isRunning():
            return
        self._start_scan([c for c in self.cats if c.key == key])

    # -- temizleme --
    def clean(self):
        busy = package_manager_busy()
        if busy:
            info_box(self, _("ui.pm_running", name=busy))
            return
        chosen = [c for c in self.cats if self.cards[c.key].is_checked()]
        chosen = [c for c in chosen if not (c.items and c.key in SELECTABLE and not c.selected_items())]
        if not chosen:
            info_box(self, _("ui.nothing_selected"))
            return
        lines = "\n".join(f"• {c.title}  ({human(c.effective_size()) if c.effective_size() is not None else '?'})" for c in chosen)
        extra = ""
        if any(c.root for c in chosen):
            extra = "\n\n" + _("ui.confirm_admin")
        if any(c.key == "orphans" for c in chosen):
            names = ", ".join(i.key for i in self.cards["orphans"].cat.selected_items())
            extra += "\n\n" + _("ui.confirm_packages", names=names)
        box = QMessageBox(QMessageBox.Icon.Question, _("ui.confirm_title"),
                          _("ui.confirm_body", lines=lines, extra=extra), parent=self)
        yes = box.addButton(_("ui.yes_clean"), QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(box.addButton(_("ui.cancel"), QMessageBox.ButtonRole.RejectRole))
        box.exec()
        if box.clickedButton() is not yes:
            return

        self.free_before = disk_usage()[2]
        self.log_box.clear()
        self.busy(True)
        self.status.setText(_("ui.cleaning"))
        self.thread = QThread()
        self.cworker = CleanWorker(chosen)
        self.cworker.moveToThread(self.thread)
        self.thread.started.connect(self.cworker.run)
        self.cworker.log.connect(self.log)
        self.cworker.finished.connect(self.clean_done)
        self.thread.start()

    def clean_done(self, ok):
        self.thread.quit()
        self.thread.wait()
        free = self.update_disk()
        gained = max(0, free - self.free_before)
        msg = _("ui.done", size=human(gained))
        self.log("")
        self.log(msg + ("" if ok else _("ui.some_failed_log")))
        self.busy(False)
        self.status.setText(msg)
        info_box(self, msg + ("" if ok else "\n\n" + _("ui.some_failed_box")))
        self.scan_all()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setDesktopFileName("sistem-temizleyici")
    app.setStyleSheet(STYLE)
    # Qt'nin kendi düğmeleri (Evet/Hayır, Tamam/İptal) için çeviri
    translator = QTranslator(app)
    if translator.load(f"qtbase_{LANG}", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
