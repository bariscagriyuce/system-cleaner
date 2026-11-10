#!/usr/bin/env python3
"""Sistem Temizleyici - root yardımcı betiği.

Bu betik pkexec ile root olarak çalıştırılır. Yalnızca aşağıdaki
beyaz listedeki işlemleri kabul eder; dışarıdan rastgele komut almaz.

Kullanım:  helper.py ISLEM[:PARAMETRE] [ISLEM[:PARAMETRE] ...]

  pkg-cache:N        Paket önbelleğinde her paketin son N sürümü dışında hepsini sil (0-5)
  pkg-uninstalled    Kaldırılmış paketlerin önbellekteki dosyalarını sil
  pkg-partial        Yarım kalmış indirme klasörlerini (download-*) sil
  orphans[:a,b,c]    Yetim paketleri kaldır (liste verilirse yalnızca onlar)
  journal:MB         Sistem günlüklerini MB boyutuna küçült (50-10000)
  coredump           Çökme dökümlerini sil
"""
import os
import re
import shutil
import subprocess
import sys

ENV = dict(os.environ, LC_ALL="C", LANG="C")
PKG_DIR = "/var/cache/pacman/pkg"
COREDUMP_DIR = "/var/lib/systemd/coredump"
PKG_NAME_RE = re.compile(r"^[a-z0-9@._+-]+$")


def say(msg):
    print(msg, flush=True)


def run(cmd):
    say("$ " + " ".join(cmd))
    proc = subprocess.run(cmd, env=ENV, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout.splitlines():
        if line.strip():
            say("  " + line)
    return proc.returncode


def pkg_cache(param):
    keep = int(param)
    if not 0 <= keep <= 5:
        raise ValueError("geçersiz sürüm sayısı")
    return run(["paccache", "-r", "-k", str(keep)])


def pkg_uninstalled(_):
    return run(["paccache", "-r", "-u", "-k", "0"])


def pkg_partial(_):
    removed = 0
    for name in os.listdir(PKG_DIR):
        path = os.path.join(PKG_DIR, name)
        if name.startswith("download-") and os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
    say(f"  {removed} yarım kalmış indirme klasörü silindi.")
    return 0


def orphans(param):
    out = subprocess.run(["pacman", "-Qdtq"], env=ENV, capture_output=True, text=True)
    current = set(out.stdout.split())
    if param:
        wanted = {p for p in param.split(",") if PKG_NAME_RE.match(p)}
        targets = sorted(wanted & current)
    else:
        targets = sorted(current)
    if not targets:
        say("  Kaldırılacak yetim paket yok.")
        return 0
    return run(["pacman", "-Rns", "--noconfirm", *targets])


def journal(param):
    mb = int(param)
    if not 50 <= mb <= 10000:
        raise ValueError("geçersiz günlük boyutu")
    return run(["journalctl", f"--vacuum-size={mb}M"])


def coredump(_):
    removed = 0
    if os.path.isdir(COREDUMP_DIR):
        for name in os.listdir(COREDUMP_DIR):
            path = os.path.join(COREDUMP_DIR, name)
            if os.path.isfile(path) and not os.path.islink(path):
                os.remove(path)
                removed += 1
    say(f"  {removed} çökme dökümü silindi.")
    return 0


ACTIONS = {
    "pkg-cache": pkg_cache,
    "pkg-uninstalled": pkg_uninstalled,
    "pkg-partial": pkg_partial,
    "orphans": orphans,
    "journal": journal,
    "coredump": coredump,
}


def main(argv):
    if os.geteuid() != 0:
        say("Bu yardımcı root olarak çalıştırılmalı (pkexec).")
        return 2
    failed = 0
    for arg in argv:
        name, _, param = arg.partition(":")
        func = ACTIONS.get(name)
        if func is None:
            say(f"Bilinmeyen işlem reddedildi: {name}")
            failed += 1
            continue
        say(f"### {name}")
        try:
            if func(param) != 0:
                failed += 1
        except Exception as exc:  # noqa: BLE001
            say(f"  HATA: {exc}")
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
