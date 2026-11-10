# Sistem Temizleyici

[English](README.md) | **Türkçe** | [Português (Brasil)](README.pt-BR.md)

CachyOS / Arch Linux için fare ile kullanılan, grafik arayüzlü disk temizleme aracı (PyQt6).
`paru -Scc`, `paccache`, `journalctl --vacuum-size` gibi komutları terminal açmadan çalıştırır.

![Ekran görüntüsü](docs/ekran-goruntusu.png)

## Diller
Program sistem dilini otomatik algılar: **Türkçe**, **English**, **Português (Brasil)**.
Sistem dili bunlardan biri değilse program İngilizce açılır.
Dili elle seçmek için: `SISTEM_TEMIZLEYICI_LANG=tr sistem-temizleyici` (`tr`, `en` veya `pt_BR`).

## Kurulum (bir kez)
    git clone https://github.com/bariscagriyuce/system-cleaner.git
    cd system-cleaner
    sh kur.sh
Paket olarak kurulur (pacman tarafından takip edilir). Ardından uygulama menüsünde **Sistem Temizleyici**.

## Kaldırma
    sh kaldir.sh

## Neleri temizler
| Kategori | Karşılığı | Yetki |
|---|---|---|
| Paket önbelleği | `paccache -rk N` | 🔒 |
| Kaldırılmış paket önbelleği | `paccache -ruk0` | 🔒 |
| Yarım kalmış indirmeler | `/var/cache/pacman/pkg/download-*` | 🔒 |
| AUR derleme önbelleği | `~/.cache/paru`, `~/.cache/yay` (`paru -Scc`) | |
| Sistem günlükleri | `journalctl --vacuum-size` | 🔒 |
| Çökme dökümleri | `/var/lib/systemd/coredump` | 🔒 |
| Küçük resimler | `~/.cache/thumbnails` | |
| Uygulama/tarayıcı önbellekleri | `~/.cache/*` (seçilebilir) | |
| Kullanılmayan Flatpak | `flatpak uninstall --unused` | |
| Tarayıcı kurtarma yedekleri | `~/.config/*-backup-crashrecovery-*` (profile-sync-daemon) | |
| Çöp kutusu | `~/.local/share/Trash` | |
| Yetim paketler | `pacman -Rns $(pacman -Qdtq)` (seçilebilir) | 🔒 |

Tarayıcı önbellekleri oturumlarınızı, şifrelerinizi, çerezlerinizi ve geçmişinizi **içermez** —
bunlar `~/.config` altındadır ve program bunlara hiç dokunmaz.

🔒 işlemler tek bir pkexec şifre penceresiyle, yalnızca beyaz listedeki komutları çalıştıran
`helper.py` üzerinden yapılır.

## Gereksinimler
`python`, `python-pyqt6`, `pacman-contrib`, `polkit` (kurulum betiği bağımlılıkları kendisi kurar).

## Lisans
MIT
