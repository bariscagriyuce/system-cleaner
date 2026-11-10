"""Sistem Temizleyici - dil algılama ve çeviriler.

Desteklenen diller: Türkçe (tr), İngilizce (en), Brezilya Portekizcesi (pt_BR).
Sistem dili bunlardan biri değilse program İngilizce çalışır.
Test için dil SISTEM_TEMIZLEYICI_LANG=tr|en|pt_BR ortam değişkeniyle zorlanabilir.
"""
import os

SUPPORTED = ("tr", "en", "pt_BR")
FALLBACK = "en"


def _normalize(value):
    """'tr_TR.UTF-8' -> 'tr', 'pt_BR.UTF-8' -> 'pt_BR', diğerleri -> None."""
    if not value:
        return None
    code = value.split(".")[0].split("@")[0].replace("-", "_")
    if code in ("C", "POSIX"):
        return "en"
    lang, _, region = code.partition("_")
    if lang == "tr":
        return "tr"
    if lang == "en":
        return "en"
    if lang == "pt" and region.upper() == "BR":
        return "pt_BR"
    return None


def detect_language(env=None):
    """Sistemin arayüz dilini bulur (gettext ile aynı öncelik sırası).

    Kullanıcının birincil dili desteklenmiyorsa İngilizce döner.
    """
    env = os.environ if env is None else env
    forced = _normalize(env.get("SISTEM_TEMIZLEYICI_LANG", ""))
    if forced:
        return forced
    language = env.get("LANGUAGE", "").split(":")[0]
    for value in (env.get("LC_ALL"), language, env.get("LC_MESSAGES"), env.get("LANG")):
        if value:
            return _normalize(value) or FALLBACK
    return FALLBACK


LANG = detect_language()

# anahtar: (tr, en, pt_BR)
STRINGS = {
    "app_name": ("Sistem Temizleyici", "System Cleaner", "Limpador do Sistema"),

    # --- kategoriler ---
    "pkg_cache.title": ("Paket önbelleği (pacman)", "Package cache (pacman)", "Cache de pacotes (pacman)"),
    "pkg_cache.desc": (
        "Güncellemelerden kalan eski paket dosyaları. Her paketin son birkaç sürümü geri dönüş için saklanır.",
        "Old package files left over from updates. The last few versions of each package are kept so you can roll back.",
        "Arquivos de pacotes antigos que sobraram das atualizações. As últimas versões de cada pacote são mantidas para permitir reverter.",
    ),
    "pkg_cache.option": ("Saklanacak sürüm", "Versions to keep", "Versões a manter"),

    "pkg_uninstalled.title": ("Kaldırılmış paketlerin önbelleği", "Cache of removed packages", "Cache de pacotes removidos"),
    "pkg_uninstalled.desc": (
        "Artık sistemde kurulu olmayan paketlerin önbellekteki dosyaları.",
        "Cached files of packages that are no longer installed.",
        "Arquivos em cache de pacotes que não estão mais instalados.",
    ),

    "pkg_partial.title": ("Yarım kalmış indirmeler", "Incomplete downloads", "Downloads incompletos"),
    "pkg_partial.desc": (
        "Kesilen güncellemelerden kalan geçici 'download-*' klasörleri.",
        "Temporary 'download-*' folders left behind by interrupted updates.",
        "Pastas temporárias 'download-*' deixadas por atualizações interrompidas.",
    ),

    "aur_cache.title": ("AUR derleme önbelleği (paru / yay)", "AUR build cache (paru / yay)", "Cache de compilação do AUR (paru / yay)"),
    "aur_cache.desc": (
        "AUR paketlerini derlemek için indirilen kaynak kodları ve derleme dosyaları ('paru -Scc' ile aynı).",
        "Source code and build files downloaded to build AUR packages (same as 'paru -Scc').",
        "Código-fonte e arquivos de compilação baixados para compilar pacotes do AUR (igual a 'paru -Scc').",
    ),

    "journal.title": ("Sistem günlükleri (journal)", "System logs (journal)", "Logs do sistema (journal)"),
    "journal.desc": (
        "Eski sistem kayıtları belirtilen boyuta küçültülür.",
        "Old system logs are shrunk down to the size you choose.",
        "Os logs antigos do sistema são reduzidos ao tamanho escolhido.",
    ),
    "journal.option": ("Saklanacak boyut", "Size to keep", "Tamanho a manter"),

    "coredump.title": ("Çökme dökümleri", "Crash dumps", "Despejos de falhas"),
    "coredump.desc": (
        "Çöken programların bıraktığı hata ayıklama dosyaları.",
        "Debugging files left behind by programs that crashed.",
        "Arquivos de depuração deixados por programas que travaram.",
    ),

    "thumbnails.title": ("Küçük resim önbelleği", "Thumbnail cache", "Cache de miniaturas"),
    "thumbnails.desc": (
        "Dosya yöneticisinin ürettiği önizleme resimleri. Gerektiğinde yeniden oluşturulur.",
        "Preview images made by the file manager. They are recreated when needed.",
        "Imagens de pré-visualização geradas pelo gerenciador de arquivos. São recriadas quando necessário.",
    ),

    "app_cache.title": ("Uygulama ve tarayıcı önbellekleri", "Application and browser caches", "Caches de aplicativos e navegadores"),
    "app_cache.desc": (
        "~/.cache içindeki önbellekler. 'Ayrıntılar' ile hangilerinin silineceğini seçebilirsiniz.",
        "Caches inside ~/.cache. Use 'Details' to choose which ones to delete.",
        "Caches dentro de ~/.cache. Use 'Detalhes' para escolher quais apagar.",
    ),
    "app_cache.warn": (
        "Silmeden önce tarayıcıları kapatmanız önerilir.",
        "Closing your browsers before cleaning is recommended.",
        "Recomenda-se fechar os navegadores antes de limpar.",
    ),

    "psd_crash.title": ("Tarayıcı kurtarma yedekleri", "Browser recovery backups", "Backups de recuperação do navegador"),
    "psd_crash.desc": (
        "profile-sync-daemon'ın bir çökmeden sonra bıraktığı eski tarayıcı profili kopyaları. Tarayıcılarınız düzgün çalışıyorsa gerekmez.",
        "Old browser profile copies left by profile-sync-daemon after a crash. Not needed if your browsers work fine.",
        "Cópias antigas de perfis de navegador deixadas pelo profile-sync-daemon após uma falha. Desnecessárias se seus navegadores funcionam bem.",
    ),
    "psd_crash.warn": (
        "Bir tarayıcıda oturum, yer imi vb. kaybolduysa önce bu yedeklerden geri alın; silindikten sonra geri getirilemez.",
        "If a browser lost sessions, bookmarks etc., restore them from these backups first; they cannot be recovered once deleted.",
        "Se um navegador perdeu sessões, favoritos etc., restaure-os destes backups primeiro; depois de apagados não podem ser recuperados.",
    ),

    "flatpak.title": ("Kullanılmayan Flatpak bileşenleri", "Unused Flatpak components", "Componentes Flatpak não utilizados"),
    "flatpak.desc": (
        "Hiçbir uygulamanın kullanmadığı Flatpak çalışma ortamları.",
        "Flatpak runtimes that no application uses.",
        "Runtimes Flatpak que nenhum aplicativo usa.",
    ),

    "trash.title": ("Çöp kutusu", "Trash", "Lixeira"),
    "trash.desc": (
        "Çöp kutusundaki dosyalar kalıcı olarak silinir.",
        "Files in the trash are deleted permanently.",
        "Os arquivos na lixeira são apagados permanentemente.",
    ),

    "orphans.title": ("Yetim paketler", "Orphan packages", "Pacotes órfãos"),
    "orphans.desc": (
        "Bağımlılık olarak kurulmuş ama artık hiçbir paketin ihtiyaç duymadığı paketler.",
        "Packages installed as dependencies that no other package needs anymore.",
        "Pacotes instalados como dependências que nenhum outro pacote precisa mais.",
    ),
    "orphans.warn": (
        "Listeyi 'Ayrıntılar'dan kontrol edin; ihtiyaç duyduğunuz bir paket varsa işaretini kaldırın.",
        "Check the list under 'Details'; untick any package you still need.",
        "Confira a lista em 'Detalhes'; desmarque qualquer pacote de que ainda precise.",
    ),

    # --- tarama bilgileri ---
    "info.files": ("{n} dosya", "{n} files", "{n} arquivos"),
    "info.clean": ("Temiz", "Clean", "Limpo"),
    "info.partial": ("{n} klasör (boyut yetki gerektirir)", "{n} folders (size needs admin rights)", "{n} pastas (tamanho requer administrador)"),
    "info.now": ("Şu an {size}", "Currently {size}", "Atualmente {size}"),
    "info.none": ("Yok", "None", "Nenhum"),
    "info.components": ("{n} bileşen", "{n} components", "{n} componentes"),
    "info.no_flatpak": ("Flatpak kurulu değil", "Flatpak is not installed", "Flatpak não está instalado"),
    "info.packages": ("{n} paket", "{n} packages", "{n} pacotes"),
    "info.selected": ("{a}/{b} seçili", "{a}/{b} selected", "{a}/{b} selecionados"),
    "info.error": ("Hata: {e}", "Error: {e}", "Erro: {e}"),

    # --- işlem kayıtları ---
    "log.scanning": ("Taranıyor: {t}", "Scanning: {t}", "Verificando: {t}"),
    "log.error": ("  HATA: {e}", "  ERROR: {e}", "  ERRO: {e}"),
    "log.asking_admin": (
        "### Yönetici yetkisi isteniyor (şifre penceresi açılacak)…",
        "### Requesting administrator rights (a password window will open)…",
        "### Solicitando permissão de administrador (uma janela de senha será aberta)…",
    ),
    "log.denied": (
        "Yetki verilmedi; sistem dosyaları temizlenmedi.",
        "Permission was not granted; system files were not cleaned.",
        "A permissão não foi concedida; os arquivos do sistema não foram limpos.",
    ),
    "log.no_pkexec": ("pkexec bulunamadı.", "pkexec was not found.", "pkexec não foi encontrado."),
    "log.skipped": ("  atlandı: {p} ({e})", "  skipped: {p} ({e})", "  ignorado: {p} ({e})"),
    "log.skipped_gone": ("  atlandı (artık yok): {p}", "  skipped (no longer exists): {p}", "  ignorado (não existe mais): {p}"),
    "log.freed": ("{size} boşaltıldı", "{size} freed", "{size} liberados"),
    "log.removed": ("{size} silindi", "{size} removed", "{size} removidos"),

    # --- arayüz ---
    "ui.ok": ("Tamam", "OK", "OK"),
    "ui.pm_running": (
        "Şu anda bir paket işlemi sürüyor ({name}). Güncelleme ya da kurulum bitince tekrar deneyin.",
        "A package operation is currently running ({name}). Please try again after the update or installation finishes.",
        "Uma operação de pacotes está em andamento ({name}). Tente novamente quando a atualização ou instalação terminar.",
    ),
    "ui.cancel": ("Vazgeç", "Cancel", "Cancelar"),
    "ui.yes_clean": ("Evet, temizle", "Yes, clean", "Sim, limpar"),
    "ui.details": ("Ayrıntılar", "Details", "Detalhes"),
    "ui.details_title": ("Ayrıntılar — {t}", "Details — {t}", "Detalhes — {t}"),
    "ui.details_prompt": ("Silinecek öğeleri işaretleyin:", "Tick the items to delete:", "Marque os itens a apagar:"),
    "ui.select_all": ("Tümünü seç", "Select all", "Selecionar tudo"),
    "ui.select_none": ("Hiçbirini seçme", "Select none", "Desmarcar tudo"),
    "ui.needs_admin": ("Yönetici şifresi gerektirir", "Requires the administrator password", "Requer a senha de administrador"),
    "ui.system_disk": ("Sistem diski ( / )", "System disk ( / )", "Disco do sistema ( / )"),
    "ui.disk_line": (
        "{used} kullanılıyor  •  {free} boş  •  toplam {total}  (%{pct})",
        "{used} used  •  {free} free  •  {total} total  ({pct}%)",
        "{used} em uso  •  {free} livres  •  {total} no total  ({pct}%)",
    ),
    "ui.to_gain": ("Kazanılacak alan", "Space to free", "Espaço a liberar"),
    "ui.log_placeholder": ("İşlem kayıtları burada görünecek…", "The activity log will appear here…", "O registro de atividades aparecerá aqui…"),
    "ui.rescan": ("Yeniden Tara", "Scan Again", "Verificar Novamente"),
    "ui.clean": ("Seçilenleri Temizle", "Clean Selected", "Limpar Selecionados"),
    "ui.scan_done": ("Tarama tamamlandı.", "Scan finished.", "Verificação concluída."),
    "ui.cleaning": ("Temizleniyor…", "Cleaning…", "Limpando…"),
    "ui.nothing_selected": ("Temizlenecek bir şey seçilmedi.", "Nothing is selected for cleaning.", "Nada foi selecionado para limpeza."),
    "ui.confirm_title": ("Temizliği onayla", "Confirm cleaning", "Confirmar limpeza"),
    "ui.confirm_body": (
        "Aşağıdakiler kalıcı olarak silinecek:\n\n{lines}{extra}\n\nDevam edilsin mi?",
        "The following will be deleted permanently:\n\n{lines}{extra}\n\nContinue?",
        "Os itens a seguir serão apagados permanentemente:\n\n{lines}{extra}\n\nContinuar?",
    ),
    "ui.confirm_admin": (
        "🔒 Bazı işlemler için yönetici şifreniz istenecek.",
        "🔒 Some steps will ask for your administrator password.",
        "🔒 Algumas etapas pedirão sua senha de administrador.",
    ),
    "ui.confirm_packages": ("Kaldırılacak paketler: {names}", "Packages to remove: {names}", "Pacotes a remover: {names}"),
    "ui.done": ("Temizlik bitti. Kazanılan alan: {size}", "Cleaning finished. Space freed: {size}", "Limpeza concluída. Espaço liberado: {size}"),
    "ui.some_failed_log": (
        "  (bazı adımlar tamamlanamadı, kayıtlara bakın)",
        "  (some steps could not be completed, see the log)",
        "  (algumas etapas não puderam ser concluídas, veja o registro)",
    ),
    "ui.some_failed_box": (
        "Bazı adımlar tamamlanamadı; ayrıntılar kayıt penceresinde.",
        "Some steps could not be completed; details are in the log panel.",
        "Algumas etapas não puderam ser concluídas; os detalhes estão no painel de registro.",
    ),
}

_INDEX = SUPPORTED.index(LANG)
DECIMAL = "," if LANG in ("tr", "pt_BR") else "."


def _(key, **kwargs):
    text = STRINGS[key][_INDEX]
    return text.format(**kwargs) if kwargs else text
