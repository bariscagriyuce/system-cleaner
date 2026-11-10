#!/usr/bin/env python3
"""Sistem Temizleyici - CachyOS / Arch için grafik arayüzlü disk temizleme aracı."""
import os
import re
import glob
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSpinBox,
    QSplitter, QVBoxLayout, QWidget,
)

APP_NAME = "Sistem Temizleyici"
APP_VERSION = "1.0.0"
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
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


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


def clear_dir_contents(path, log):
    """Klasörün kendisini bırakıp içini boşaltır. Silinen bayt miktarını döner."""
    if not os.path.isdir(path):
        return 0
    before = du(path)
    for name in os.listdir(path):
        p = os.path.join(path, name)
        try:
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                os.remove(p)
        except OSError as exc:
            log(f"  atlandı: {p} ({exc.strerror})")
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
    cats = [
        Category("pkg_cache", "Paket önbelleği (pacman)",
                 "Güncellemelerden kalan eski paket dosyaları. Her paketin son birkaç sürümü geri dönüş için saklanır.",
                 "package-x-generic", root=True,
                 option=("Saklanacak sürüm", 0, 3, 1, "")),
        Category("pkg_uninstalled", "Kaldırılmış paketlerin önbelleği",
                 "Artık sistemde kurulu olmayan paketlerin önbellekteki dosyaları.",
                 "edit-delete", root=True),
        Category("pkg_partial", "Yarım kalmış indirmeler",
                 "Kesilen güncellemelerden kalan geçici 'download-*' klasörleri.",
                 "folder-download", root=True),
        Category("aur_cache", "AUR derleme önbelleği (paru / yay)",
                 "AUR paketlerini derlemek için indirilen kaynak kodları ve derleme dosyaları ('paru -Scc' ile aynı).",
                 "folder-build", root=False),
        Category("journal", "Sistem günlükleri (journal)",
                 "Eski sistem kayıtları belirtilen boyuta küçültülür.",
                 "text-x-log", root=True,
                 option=("Saklanacak boyut", 50, 2000, 100, " MB")),
        Category("coredump", "Çökme dökümleri",
                 "Çöken programların bıraktığı hata ayıklama dosyaları.",
                 "tools-report-bug", root=True),
        Category("thumbnails", "Küçük resim önbelleği",
                 "Dosya yöneticisinin ürettiği önizleme resimleri. Gerektiğinde yeniden oluşturulur.",
                 "image-x-generic"),
        Category("app_cache", "Uygulama ve tarayıcı önbellekleri",
                 "~/.cache içindeki önbellekler. 'Ayrıntılar' ile hangilerinin silineceğini seçebilirsiniz.",
                 "applications-internet",
                 warn="Silmeden önce tarayıcıları kapatmanız önerilir."),
        Category("psd_crash", "Tarayıcı kurtarma yedekleri",
                 "profile-sync-daemon'ın bir çökmeden sonra bıraktığı eski tarayıcı profili kopyaları. Tarayıcılarınız düzgün çalışıyorsa gerekmez.",
                 "document-revert", default=False,
                 warn="Bir tarayıcıda oturum, yer imi vb. kaybolduysa önce bu yedeklerden geri alın; silindikten sonra geri getirilemez."),
        Category("flatpak", "Kullanılmayan Flatpak bileşenleri",
                 "Hiçbir uygulamanın kullanmadığı Flatpak çalışma ortamları.",
                 "flatpak-discover"),
        Category("trash", "Çöp kutusu",
                 "Çöp kutusundaki dosyalar kalıcı olarak silinir.",
                 "user-trash-full", default=False),
        Category("orphans", "Yetim paketler",
                 "Bağımlılık olarak kurulmuş ama artık hiçbir paketin ihtiyaç duymadığı paketler.",
                 "dialog-warning", root=True, default=False,
                 warn="Listeyi 'Ayrıntılar'dan kontrol edin; ihtiyaç duyduğunuz bir paket varsa işaretini kaldırın."),
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
            c.size, c.info = parse_size(m.group(2)), f"{m.group(1)} dosya"
        else:
            c.info = "Temiz"
    elif k == "pkg_uninstalled":
        out = run_c(["paccache", "-d", "-u", "-k", "0"])
        m = re.search(r"(\d+) candidates? \(disk space saved: ([^)]+)\)", out)
        if m:
            c.size, c.info = parse_size(m.group(2)), f"{m.group(1)} dosya"
        else:
            c.info = "Temiz"
    elif k == "pkg_partial":
        try:
            n = sum(1 for x in os.listdir("/var/cache/pacman/pkg") if x.startswith("download-"))
        except OSError:
            n = 0
        c.size = None if n else 0
        c.info = f"{n} klasör (boyut yetki gerektirir)" if n else "Temiz"
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
        c.info = f"Şu an {human(used)}"
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
        c.info = "" if c.items else "Yok"
    elif k == "flatpak":
        if shutil.which("flatpak"):
            try:
                out = subprocess.run(["flatpak", "uninstall", "--unused"], input="n\n",
                                     capture_output=True, text=True, env=ENV_C, timeout=60).stdout
            except Exception:
                out = ""
            refs = re.findall(r"^\s*\d+\.\s+\S", out, re.M)
            if "Nothing unused" in out or not refs:
                c.size, c.info = 0, "Temiz"
            else:
                c.size, c.info = None, f"{len(refs)} bileşen"
        else:
            c.info = "Flatpak kurulu değil"
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
        c.info = f"{len(names)} paket" if names else "Yok"
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
            self.progress.emit(f"Taranıyor: {c.title}")
            try:
                scan_category(c)
            except Exception as exc:  # noqa: BLE001
                c.info = f"Hata: {exc}"
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
                self.log.emit(f"  HATA: {exc}")
                ok = False

        if root_args:
            helper = INSTALLED_HELPER if os.path.exists(INSTALLED_HELPER) else LOCAL_HELPER
            self.log.emit("### Yönetici yetkisi isteniyor (şifre penceresi açılacak)…")
            try:
                proc = subprocess.Popen(["pkexec", sys.executable if helper == LOCAL_HELPER else helper,
                                         *([helper] if helper == LOCAL_HELPER else []), *root_args],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout:
                    self.log.emit(line.rstrip())
                rc = proc.wait()
                if rc in (126, 127):
                    self.log.emit("Yetki verilmedi; sistem dosyaları temizlenmedi.")
                    ok = False
                elif rc != 0:
                    ok = False
            except FileNotFoundError:
                self.log.emit("pkexec bulunamadı.")
                ok = False
        self.finished.emit(ok)

    def clean_user(self, c):
        log = self.log.emit
        if c.key == "aur_cache":
            for i in c.selected_items():
                freed = clear_dir_contents(os.path.join(CACHE, i.key), log)
                log(f"  ~/.cache/{i.key}: {human(freed)} boşaltıldı")
        elif c.key == "thumbnails":
            freed = clear_dir_contents(os.path.join(CACHE, "thumbnails"), log)
            log(f"  {human(freed)} boşaltıldı")
        elif c.key == "app_cache":
            for i in c.selected_items():
                freed = clear_dir_contents(os.path.join(CACHE, i.key), log)
                log(f"  {i.key}: {human(freed)} boşaltıldı")
        elif c.key == "psd_crash":
            allowed = set(psd_dirs())
            for i in c.selected_items():
                if i.key not in allowed:
                    log(f"  atlandı (artık yok): {i.label}")
                    continue
                size = du(i.key)
                shutil.rmtree(i.key, ignore_errors=True)
                log(f"  {i.label}: {human(size if not os.path.exists(i.key) else 0)} silindi")
        elif c.key == "trash":
            freed = 0
            for sub in ("files", "info", "expunged"):
                freed += clear_dir_contents(os.path.join(TRASH, sub), log)
            log(f"  {human(freed)} boşaltıldı")
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


class DetailsDialog(QDialog):
    def __init__(self, cat, parent=None):
        super().__init__(parent)
        self.cat = cat
        self.setWindowTitle(f"Ayrıntılar — {cat.title}")
        self.resize(520, 520)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Silinecek öğeleri işaretleyin:"))
        self.list = QListWidget()
        for it in cat.items:
            w = QListWidgetItem(f"{it.label}    —    {human(it.size)}")
            w.setFlags(w.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            w.setCheckState(Qt.CheckState.Checked if it.checked else Qt.CheckState.Unchecked)
            self.list.addItem(w)
        lay.addWidget(self.list)
        row = QHBoxLayout()
        b_all = QPushButton("Tümünü seç")
        b_none = QPushButton("Hiçbirini seçme")
        b_all.clicked.connect(lambda: self._set_all(True))
        b_none.clicked.connect(lambda: self._set_all(False))
        row.addWidget(b_all)
        row.addWidget(b_none)
        row.addStretch()
        lay.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
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
        t.setToolTip("Yönetici şifresi gerektirir" if cat.root else "")
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
            label, lo, hi, _, suffix = cat.option
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
        self.details = QPushButton("Ayrıntılar")
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
            info = f"{len(c.selected_items())}/{len(c.items)} seçili"
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
        h = QLabel("Sistem diski ( / )")
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
        self.log_box.setPlaceholderText("İşlem kayıtları burada görünecek…")
        self.log_box.setFont(QFont("monospace", 9))
        splitter.addWidget(self.log_box)
        splitter.setSizes([600, 140])
        root.addWidget(splitter, 1)

        # Alt çubuk
        bottom = QHBoxLayout()
        self.status = QLabel("")
        bottom.addWidget(self.status, 1)
        self.scan_btn = QPushButton(QIcon.fromTheme("view-refresh"), "Yeniden Tara")
        self.scan_btn.clicked.connect(self.scan_all)
        bottom.addWidget(self.scan_btn)
        self.clean_btn = QPushButton(QIcon.fromTheme("edit-clear-all"), "Seçilenleri Temizle")
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
        self.disk_lbl.setText(f"{human(used)} kullanılıyor  •  {human(free)} boş  •  toplam {human(total)}  (%{used / total * 100:.0f})")
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
        self.total_lbl.setText(f"Kazanılacak alan\n{human(total)}{' +' if unknown else ''}")

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
            self.status.setText("Tarama tamamlandı.")
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
        chosen = [c for c in self.cats if self.cards[c.key].is_checked()]
        chosen = [c for c in chosen if not (c.items and c.key in SELECTABLE and not c.selected_items())]
        if not chosen:
            QMessageBox.information(self, APP_NAME, "Temizlenecek bir şey seçilmedi.")
            return
        lines = "\n".join(f"• {c.title}  ({human(c.effective_size()) if c.effective_size() is not None else '?'})" for c in chosen)
        extra = ""
        if any(c.root for c in chosen):
            extra = "\n\n🔒 Bazı işlemler için yönetici şifreniz istenecek."
        if any(c.key == "orphans" for c in chosen):
            names = ", ".join(i.key for i in self.cards["orphans"].cat.selected_items())
            extra += f"\n\nKaldırılacak paketler: {names}"
        if QMessageBox.question(self, "Temizliği onayla",
                                f"Aşağıdakiler kalıcı olarak silinecek:\n\n{lines}{extra}\n\nDevam edilsin mi?") \
                != QMessageBox.StandardButton.Yes:
            return

        self.free_before = disk_usage()[2]
        self.log_box.clear()
        self.busy(True)
        self.status.setText("Temizleniyor…")
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
        msg = f"Temizlik bitti. Kazanılan alan: {human(gained)}"
        self.log("")
        self.log(msg + ("" if ok else "  (bazı adımlar tamamlanamadı, kayıtlara bakın)"))
        self.busy(False)
        self.status.setText(msg)
        QMessageBox.information(self, APP_NAME, msg + ("" if ok else "\n\nBazı adımlar tamamlanamadı; ayrıntılar kayıt penceresinde."))
        self.scan_all()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setDesktopFileName("sistem-temizleyici")
    app.setStyleSheet(STYLE)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
