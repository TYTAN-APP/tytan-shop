#!/usr/bin/env python3
"""
Tytan OS App Shop / Package Manager
====================================
Autor: TYTANKOMP
Wersja: 2.0.0 PROFESSIONAL

Instalacja (wymaga sudo):
    sudo python3 tytan_store.py --install

Użycie:
    tytan-store                 -> pomoc (nie wymaga sudo)
    tytan-store help            -> pomoc (nie wymaga sudo)
    tytan-store repo            -> wyświetla sklep z apkami (nie wymaga sudo)
    sudo app install neofetch   -> pobiera z paskiem postępu i linkuje globalnie
    sudo tytan-store uninstall  -> całkowicie czyści system z programu i pakietów
"""

from __future__ import annotations

import os
import re
import sys
import stat
import shutil
import platform
import subprocess
import threading
import time
import itertools
import urllib.request
import urllib.error
from pathlib import Path

VERSION = "2.0.0 PROFESSIONAL"
AUTHOR = "TYTANKOMP"

# ---------------------------------------------------------------------------
# Stałe ścieżki systemowe (Izolacja Tytan OS)
# ---------------------------------------------------------------------------
SYSTEM_BIN_DIR = Path("/usr/local/bin")
APP_DIR = Path("/var/lib/tytan-store")
REPO_FILE = APP_DIR / "repo.txt"
INSTALL_DIR = APP_DIR / "apps"

SCRIPT_COPY = SYSTEM_BIN_DIR / "tytan-store"
APP_SYMLINK = SYSTEM_BIN_DIR / "app"

MAX_SEARCH_DEPTH = 3

DEFAULT_REPO_CONTENT = """{
  app=1
  name_app[neofetch]
  command=git clone https://github.com/dylanaraps/neofetch.git
  type=script
}
{
  app=2
  name_app[htop]
  command=git clone https://github.com/htop-dev/htop.git
  type=source
}
{
  app=3
  name_app[xorg]
  command=git clone https://gitlab.freedesktop.org/xorg/xserver.git
  type=source
}
{
  app=4
  name_app[openbox]
  command=git clone https://github.com/danakj/openbox.git
  type=source
}
{
  app=5
  name_app[xterm]
  command=git clone https://github.com/ThomasDickey/xterm-snapshots.git
  type=source
}
"""

# ---------------------------------------------------------------------------
# Kolory ANSI i GUI
# ---------------------------------------------------------------------------
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"

def supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("TERM", "") != "dumb"

def col(text: str, *codes: str) -> str:
    if not supports_color():
        return text
    return "".join(codes) + text + C.RESET

WIDTH = 41

def frame_top(): return col("┌" + "─" * WIDTH + "┐", C.BLUE, C.BOLD)
def frame_mid(): return col("├" + "─" * WIDTH + "┤", C.BLUE, C.BOLD)
def frame_bottom(): return col("└" + "─" * WIDTH + "┘", C.BLUE, C.BOLD)

def frame_title(text: str):
    inner = text.center(WIDTH)
    return col("│", C.BLUE, C.BOLD) + col(inner, C.GREEN, C.BOLD) + col("│", C.BLUE, C.BOLD)

def frame_footer():
    inner = "© 2026 TYTANKOMP | OpenSecure License".center(WIDTH)
    return col("│", C.BLUE, C.BOLD) + col(inner, C.YELLOW, C.BOLD) + col("│", C.BLUE, C.BOLD)

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def require_root():
    if os.geteuid() != 0:
        print(col("[BŁĄD] Ta operacja narusza system plików!", C.RED, C.BOLD))
        print(col("       Użyj 'sudo' przed komendą.", C.YELLOW))
        sys.exit(1)

# ---------------------------------------------------------------------------
# Wykrywanie i Parsowanie
# ---------------------------------------------------------------------------
def detect_architecture() -> tuple[str, str]:
    machine = platform.machine().strip().lower()
    if machine in ("aarch64", "arm64"): return "ARM64", "arm64"
    if machine.startswith("armv7") or machine.startswith("armv6") or machine == "arm": return "ARM32", "armv7"
    if machine in ("x86_64", "amd64"): return "AMD64", "amd64"
    if machine in ("i386", "i686", "x86"): return "x86", "x86"
    return machine.upper() if machine else "UNKNOWN", (machine or "unknown")

class RepoParseError(Exception): pass

def parse_repo(repo_path: Path):
    if not repo_path.exists():
        raise RepoParseError(f"Plik repo nie istnieje: {repo_path}")
    try:
        content = repo_path.read_text(encoding="utf-8")
    except OSError as e:
        raise RepoParseError(f"Nie można odczytać {repo_path}: {e}")

    blocks = re.findall(r"\{(.*?)\}", content, flags=re.DOTALL)
    apps = []
    for idx, block in enumerate(blocks, start=1):
        data: dict[str, str] = {}
        name_match = re.search(r"name_app\[\s*([^\]]+?)\s*\]", block)
        if name_match: data["name"] = name_match.group(1).strip()
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("name_app"): continue
            kv_match = re.match(r"^([A-Za-z0-9_]+)\s*=\s*(.+)$", line)
            if kv_match: data[kv_match.group(1).strip()] = kv_match.group(2).strip()
        if "app" not in data: data["app"] = str(idx)
        if "name" in data:
            data.setdefault("type", "auto")
            apps.append(data)
    return apps

def find_app(apps, name: str):
    clean = name.strip().strip("[]").strip().lower()
    for app in apps:
        if app["name"].lower() == clean: return app
    return None

# ---------------------------------------------------------------------------
# Spinner i Ukryte Wykonywanie Komend
# ---------------------------------------------------------------------------
def run_with_progress(cmd: str, cwd: Path, loading_msg: str) -> bool:
    """Odpala proces w tle, ukrywa stdout/stderr i rysuje spinner."""
    try:
        process = subprocess.Popen(
            cmd, shell=True, cwd=str(cwd),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except OSError as e:
        print(col(f"\n[BŁĄD] Nie udało się uruchomić: {e}", C.RED))
        return False

    spinner = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
    while process.poll() is None:
        sys.stdout.write(f'\r  {col(next(spinner), C.CYAN)} {loading_msg}...')
        sys.stdout.flush()
        time.sleep(0.1)

    sys.stdout.write('\r\033[K') # Czyszczenie linii
    
    if process.returncode == 0:
        print(f"  {col('[██████████████████████████████] 100% Pomyślnie!', C.GREEN, C.BOLD)}")
        return True
    else:
        print(f"  {col('[BŁĄD] Proces zakończył się niepowodzeniem (kod: ' + str(process.returncode) + ')', C.RED, C.BOLD)}")
        return False

# ---------------------------------------------------------------------------
# Komendy: Zainstaluj / Odinstaluj Tytan Store
# ---------------------------------------------------------------------------
def install_system():
    require_root()
    clear_screen()
    print(col("== Inicjalizacja Tytan OS App Shop ==", C.CYAN, C.BOLD))

    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        SYSTEM_BIN_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[BŁĄD] Brak dostępu do katalogów systemowych: {e}")
        sys.exit(1)
    
    current_file = Path(__file__).resolve()
    try:
        shutil.copy2(current_file, SCRIPT_COPY)
        os.chmod(SCRIPT_COPY, 0o755)
        
        if APP_SYMLINK.exists() or APP_SYMLINK.is_symlink():
            APP_SYMLINK.unlink()
        os.symlink(SCRIPT_COPY, APP_SYMLINK)
        
    except OSError as e:
        print(f"[BŁĄD] Nie można skopiować binarki: {e}")
        sys.exit(1)

    if not REPO_FILE.exists():
        REPO_FILE.write_text(DEFAULT_REPO_CONTENT, encoding="utf-8")

    print(f"  [OK] Baza danych: {APP_DIR}")
    print(f"  [OK] Binarki systemu: {SYSTEM_BIN_DIR}")
    print(f"\n{col('Zainstalowano pomyślnie!', C.GREEN, C.BOLD)}")
    print("Możesz teraz używać komend z dowolnego miejsca:")
    print("  tytan-store repo")
    print("  sudo app install neofetch")

def uninstall_system():
    require_root()
    clear_screen()
    print(col("== Deinstalacja Tytan Store ==", C.RED, C.BOLD))
    
    # Próba usunięcia zainstalowanych binarek, aby nie śmiecić w systemie
    if REPO_FILE.exists():
        try:
            apps = parse_repo(REPO_FILE)
            for app in apps:
                sym = SYSTEM_BIN_DIR / app["name"]
                if sym.exists() or sym.is_symlink():
                    sym.unlink()
                    print(f"  [-] Usunięto dowiązanie: {sym}")
        except: pass

    # Usuwanie skryptów bazowych
    for p in [SCRIPT_COPY, APP_SYMLINK]:
        if p.exists() or p.is_symlink():
            p.unlink()
            print(f"  [-] Usunięto komendę: {p}")

    # Usuwanie całego katalogu bazowego
    if APP_DIR.exists():
        shutil.rmtree(APP_DIR, ignore_errors=True)
        print(f"  [-] Usunięto katalog i aplikacje: {APP_DIR}")

    print(col("\nSystem Tytan OS został całkowicie wyczyszczony.", C.GREEN, C.BOLD))

# ---------------------------------------------------------------------------
# Komendy: Pomoc i Sklep (GUI)
# ---------------------------------------------------------------------------
def cmd_repo():
    clear_screen()
    try:
        apps = parse_repo(REPO_FILE)
    except RepoParseError as e:
        print(col(f"  [BŁĄD] {e}", C.RED))
        print(col("  Uruchom instalację: sudo python3 tytan_store.py --install", C.YELLOW))
        sys.exit(1)

    print(frame_top())
    print(frame_title("TYTAN OS APP SHOP"))
    print(frame_mid())
    
    if apps:
        for app in apps:
            line = f"  » {app['name']}"
            print(col(line.ljust(WIDTH), C.CYAN, C.BOLD))
    else:
        print(col("  Puste repozytorium".center(WIDTH), C.RED))
        
    print(frame_mid())
    print(frame_footer())
    print(frame_bottom())
    print()

def print_help():
    clear_screen()
    arch_label, _ = detect_architecture()
    
    print(frame_top())
    print(frame_title("TYTAN OS APP SHOP - HELP"))
    print(frame_mid())
    print(f" │ {col('Architektura:', C.BLUE)} {col(arch_label, C.CYAN).ljust(35)}│")
    print(f" │ {col('Baza danych:', C.BLUE)}  {col(str(REPO_FILE), C.CYAN).ljust(36)}│")
    print(frame_mid())
    print(col(" │ Dostępne komendy:                       │", C.YELLOW))
    print(f" │   {col('tytan-store repo', C.GREEN)}    - Sklep apek      │")
    print(f" │   {col('app install [nazwa]', C.GREEN)} - Instalacja      │")
    print(f" │   {col('sudo tytan-store uninstall', C.RED)} - Reset│")
    print(frame_bottom())

# ---------------------------------------------------------------------------
# Logika instalacji aplikacji i linkowania
# ---------------------------------------------------------------------------
def make_executable(path: Path):
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

def find_executable(app_dir: Path, app_name: str) -> Path | None:
    base_depth = len(app_dir.resolve().parts)
    candidates = []

    for root, dirs, files in os.walk(app_dir):
        if ".git" in dirs: dirs.remove(".git")
        depth = len(Path(root).resolve().parts) - base_depth
        if depth >= MAX_SEARCH_DEPTH:
            dirs[:] = []
            continue
            
        for fname in files:
            if fname.lower() == app_name.lower() or Path(fname).stem.lower() == app_name.lower():
                candidates.append(Path(root) / fname)

    if not candidates: return None
    candidates.sort(key=lambda p: len(p.parts))
    return candidates[0]

def create_symlink(exe: Path, app_name: str) -> Path:
    symlink_path = SYSTEM_BIN_DIR / app_name
    if symlink_path.exists() or symlink_path.is_symlink():
        symlink_path.unlink()
    os.symlink(exe.resolve(), symlink_path)
    return symlink_path

def cmd_app_install(name: str):
    require_root()
    clear_screen()
    
    try:
        apps = parse_repo(REPO_FILE)
    except RepoParseError:
        print(col("[BŁĄD] System bazy danych nie został zainicjalizowany.", C.RED))
        sys.exit(1)

    app = find_app(apps, name)
    if app is None:
        print(col(f"[BŁĄD] Pakiet '{name}' nie istnieje w repozytorium.", C.RED))
        sys.exit(1)

    app_name = app["name"]
    command = app.get("command")
    
    if not command:
        print(col(f"[BŁĄD] Brak wskaźnika pobierania dla: {app_name}", C.RED))
        sys.exit(1)

    print(col(f"== Instalator Pakietów: {app_name} ==", C.CYAN, C.BOLD))
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    
    # Obsługa błędu 128 (Usuwanie starego folderu)
    app_target_dir = INSTALL_DIR / app_name
    if app_target_dir.exists():
        shutil.rmtree(app_target_dir, ignore_errors=True)

    # Pobieranie paczki z paskiem postępu
    success = run_with_progress(command, INSTALL_DIR, f"Pobieranie i rozpakowywanie pakietu {app_name}")
    
    if not success:
        sys.exit(1)

    # Jeśli git clone utworzył folder o innej nazwie, musimy go znaleźć.
    # W 99% przypadków nazwa folderu zgadza się z repo.
    if not app_target_dir.exists():
        possible_dirs = [d for d in INSTALL_DIR.iterdir() if d.is_dir()]
        if possible_dirs:
            # Sortujemy według najnowszego czasu modyfikacji
            possible_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            app_target_dir = possible_dirs[0]

    # Próba kompilacji (jeśli makefile istnieje) z ukrytym outputem
    if (app_target_dir / "Makefile").exists() or (app_target_dir / "configure").exists():
        if (app_target_dir / "configure").exists():
            make_executable(app_target_dir / "configure")
            run_with_progress("./configure", app_target_dir, "Konfiguracja źródeł")
        if (app_target_dir / "Makefile").exists():
            run_with_progress("make", app_target_dir, "Kompilacja binarnej paczki")

    # Wyszukiwanie pliku wykonywalnego i linkowanie
    exe = find_executable(app_target_dir, app_name)
    if exe:
        try:
            make_executable(exe)
            sym = create_symlink(exe, app_name)
            print(f"  {col('[+]', C.GREEN)} Aktywowano globalnie: {sym}")
        except Exception as e:
            print(col(f"  [BŁĄD] Nie udało się zlinkować pliku: {e}", C.RED))
    else:
        print(col("  [!] Pobrano pomyślnie, ale nie znaleziono pliku wykonywalnego.", C.YELLOW))
        print(f"      Możesz wymagać ręcznej kompilacji w folderze: {app_target_dir}")

# ---------------------------------------------------------------------------
# Router Główny
# ---------------------------------------------------------------------------
def main():
    argv = sys.argv[1:]

    if "--install" in argv:
        install_system()
        return

    if not argv or argv[0] == "help":
        print_help()
        return

    if argv[0] == "uninstall":
        uninstall_system()
        return

    if argv[0] == "repo":
        cmd_repo()
        return

    if argv[0] == "install":
        name = argv[1] if len(argv) > 1 else ""
        if not name:
            print(col("Użycie: app install <nazwa>", C.RED))
            return
        cmd_app_install(name)
        return

    print_help()

if __name__ == "__main__":
    main()
