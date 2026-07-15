# 🛒 Tytan Store

**Tytan Store** to nowoczesny menedżer pakietów dla **Tytan OS**, napisany w czystym Pythonie z wykorzystaniem wyłącznie standardowych bibliotek.

Jest to lekki odpowiednik takich menedżerów jak:

- APT
- DNF
- Pacman
- APK
- Zypper

Tytan Store umożliwia pobieranie, instalowanie oraz zarządzanie aplikacjami z własnego repozytorium.

---

# ✨ Funkcje

- 📦 Instalacja aplikacji z repozytorium
- ⚡ Automatyczne pobieranie źródeł
- 🔨 Automatyczna kompilacja (`configure` + `make`)
- 🔗 Tworzenie globalnych poleceń
- 🖥️ Terminalowe GUI
- 📂 Własne repozytorium pakietów
- 🚀 Automatyczne wykrywanie architektury CPU
- 🧹 Pełna deinstalacja systemu

---

# Instalacja

```bash
sudo python3 tytan-store.py --install
```

Po zakończeniu instalacji dostępne będą komendy:

```bash
tytan-store help
```

```bash
tytan-store repo
```

```bash
sudo app install <nazwa>
```

Przykład:

```bash
sudo app install firefox
```

---

# Repozytorium

Lista aplikacji znajduje się w:

```
/var/lib/tytan-store/repo.txt
```

Każdy wpis wygląda następująco:

```text
{
app=1
name_app[firefox]
command=git clone https://github.com/example/firefox.git
type=source
}
```

Po zapisaniu pliku `repo.txt` polecenie

```bash
tytan-store repo
```

automatycznie pokaże nową aplikację.

Nie jest wymagane ponowne instalowanie programu.

---

# Jak dodać własną aplikację

Dodaj nowy blok do pliku:

```text
{
app=10
name_app[moja-aplikacja]
command=git clone https://github.com/twoje-repo.git
type=source
}
```

Po zapisaniu wykonaj:

```bash
tytan-store repo
```

Nowa aplikacja pojawi się automatycznie.

---

# Jak zainstalować aplikację

```bash
sudo app install nazwa-aplikacji
```

Przykład:

```bash
sudo app install moja-aplikacja
```

---

# Oficjalna strona

🌐 https://tytankomp.pl

---

# Licencja

Projekt udostępniany jest na licencji **GNU GPL v3.0**.
