# debug_runner.py — Layihe diaqnostika aleti
# Ishletmek: python debug_runner.py  (backend qovluguna qoy)

import sys, io, os, ast, re, traceback, json, importlib.util

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def safe(t): return str(t).encode('ascii', errors='replace').decode('ascii')

SKIP_DIRS  = {".git","__pycache__","node_modules",".venv","venv","dist","build",".next",".idea"}
SKIP_FILES = {"debug_runner.py", "xeta_tapma.py"}

def find_root():
    cur = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(cur) if os.path.basename(cur).lower() in ("backend","src") else cur

def all_py_files(root):
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for f in fns:
            if f.endswith(".py") and f not in SKIP_FILES:
                yield os.path.join(dp, f)

def rel(root, path):
    return os.path.relpath(path, root).replace("\\","/")

# ─────────────────────────────────────────────────────────
# 1. ENCODING — Yalniz backend .py fayllarinda REAL xeta
#
# QAYDA:
#   - Azerbaycan herfleri (e, i, u, o, s, c, g ve s.) .py
#     faylinda string/sherh icinde olmamalidir
#   - AMMA: ensure_ascii=False ile JSON-a gedirse, o string
#     HTTP body-e dushur ve requests UTF-8 encode edir → PROBLEM YOX
#   - PROBLEM OLAN: HTTP HEADER-e dushan string (API key, Authorization)
#   - .env-de YALNIZ deyerleri yoxla, sherhler (#) ile bashlayan
#     satirlari atla
# ─────────────────────────────────────────────────────────
def check_encoding(root):
    print("\n[1] ENCODING YOXLAMASI")
    print("    Qayda: .py fayllarinda STRING/SHEREHDE Azerbaycan herfi olmamalidir")
    print("    (ensure_ascii=False icindeki deyerler bu yoxlamaya daxil deyil)")
    found = False
    backend = os.path.join(root, "backend")
    target_dir = backend if os.path.exists(backend) else root

    for fpath in all_py_files(target_dir):
        r = rel(root, fpath)
        try:
            lines = open(fpath, encoding="utf-8", errors="replace").readlines()
        except:
            continue
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Sherehlerle bashlayan satirlari atla (bunlar sadece izah ucundur)
            if stripped.startswith("#"):
                continue
            bad = [(j+1, c, hex(ord(c))) for j,c in enumerate(line.rstrip("\n")) if ord(c) > 127]
            if not bad:
                continue
            # ensure_ascii=False icindeki string literal icinde olan herfler
            # HTTP body-e gedir, problem yaratmir — atla
            if 'ensure_ascii=False' in line:
                continue
            found = True
            print(f"\n  [XETA] {r}  —  Setir {i}")
            print(f"         Metn : {safe(line.rstrip()[:90])}")
            for pos, char, code in bad:
                print(f"         --> Movqe {pos}: '{safe(char)}'  ({code})")
                if code in ('0x259','0x131','0x11f','0x15f','0x18f','0x130','0xfc','0xf6','0xe7','0xc7'):
                    print(f"             Bu Azerbaycan herfidir — ASCII qarshiligi ile evez edin")

    # .env — YALNIZ deyerleri yoxla (sherhler normal)
    for ef in [os.path.join(root,".env"), os.path.join(os.path.join(root,"backend"),".env")]:
        if not os.path.exists(ef):
            continue
        r = rel(root, ef)
        for i, line in enumerate(open(ef, encoding="utf-8", errors="replace"), 1):
            line = line.rstrip("\n")
            if line.startswith("#") or "=" not in line:
                continue  # sherhler normaldir, atla
            _, _, val = line.partition("=")
            val = val.strip().strip('"').strip("'")
            bad = [(j+1,c,hex(ord(c))) for j,c in enumerate(val) if ord(c) > 127]
            if bad:
                found = True
                key = line.split("=")[0].strip()
                print(f"\n  [XETA] {r} — '{key}' DEYERINDE xususi herf!")
                for pos, char, code in bad:
                    print(f"         Movqe {pos}: '{safe(char)}'  ({code})")
                print(f"         Həll: Bu key-i silib Groq saytindan yeniden kopyalayin")

    if not found:
        print("  [OK] Encoding problemi tapilmadi.")

# ─────────────────────────────────────────────────────────
# 2. PYTHON SINTAKSIS
# ─────────────────────────────────────────────────────────
def check_syntax(root):
    print("\n[2] PYTHON SINTAKSIS YOXLAMASI")
    errors = []
    for fpath in all_py_files(root):
        try:
            ast.parse(open(fpath, encoding="utf-8", errors="replace").read())
        except SyntaxError as e:
            errors.append((rel(root,fpath), e))
    if errors:
        for r, e in errors:
            print(f"  [XETA] {r}  —  Setir {e.lineno}: {safe(e.msg)}")
            if e.text: print(f"         Kod: {safe(e.text.rstrip())}")
    else:
        print("  [OK] Butun .py fayllarinin sintaksisi duzgundur.")

# ─────────────────────────────────────────────────────────
# 3. QURASHDIRILMAMISH PAKETLER
# ─────────────────────────────────────────────────────────
def check_imports(root):
    print("\n[3] QURASHDIRILMAMISH PAKET YOXLAMASI")
    backend = os.path.join(root, "backend")
    local_paths = [root, backend, os.path.join(backend,"modules")]
    checked, missing = set(), []

    for fpath in all_py_files(root):
        r = rel(root, fpath)
        try: tree = ast.parse(open(fpath, encoding="utf-8", errors="replace").read())
        except: continue
        for node in ast.walk(tree):
            pkgs = []
            if isinstance(node, ast.Import):
                pkgs = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                pkgs = [node.module.split(".")[0]]
            for pkg in pkgs:
                if pkg in checked: continue
                checked.add(pkg)
                is_local = any(
                    os.path.exists(os.path.join(p, pkg+".py")) or
                    os.path.exists(os.path.join(p, pkg))
                    for p in local_paths
                )
                if is_local: continue
                try: importlib.util.find_spec(pkg)
                except (ModuleNotFoundError, ValueError):
                    missing.append((pkg, r))
    if missing:
        for pkg, r in missing:
            print(f"  [XETA] '{pkg}' tapilmadi  ({r})")
            print(f"         Qurashdirin: pip install {pkg}")
    else:
        print("  [OK] Butun paketler movcuddur.")

# ─────────────────────────────────────────────────────────
# 4. .ENV YOXLAMASI
# ─────────────────────────────────────────────────────────
def check_env(root):
    print("\n[4] .ENV FAYLI YOXLAMASI")
    backend = os.path.join(root, "backend")
    env_path = next((p for p in [os.path.join(root,".env"), os.path.join(backend,".env")] if os.path.exists(p)), None)
    if not env_path:
        print("  [XETA] .env fayli tapilmadi!")
        return
    print(f"  [OK] .env tapildi: {rel(root, env_path)}")
    empty = []
    filled = []
    for i, line in enumerate(open(env_path, encoding="utf-8", errors="replace"), 1):
        line = line.rstrip("\n")
        if not line or line.startswith("#"): continue  # sherhler normaldir
        if "=" not in line:
            print(f"  [XETA] Setir {i}: '=' yoxdur")
            continue
        key, _, val = line.partition("=")
        val = val.strip().strip('"').strip("'")
        if not val:
            empty.append(key.strip())
        else:
            filled.append(key.strip())
    if filled:
        print(f"  [OK] Dolu key-ler: {', '.join(filled)}")
    for k in empty:
        print(f"  [XEBERDARLIQ] '{k}' bosdur — bu key lazim olsa API ishlemeye biler")

# ─────────────────────────────────────────────────────────
# 5. REAL KOD BUQLARI
# ─────────────────────────────────────────────────────────
def check_bugs(root):
    print("\n[5] REAL KOD BUQLARI")
    found = False
    rules = [
        # (regex, izah, ciddilik)
        (r'\bexcept\s*:',
         "KOR EXCEPT — SystemExit, KeyboardInterrupt de tutur. 'except Exception as e:' yazin",
         "XETA"),
        (r'\bexcept\s+Exception\s*(?!\s+as\b)',
         "AS E YOXDUR — xeta mesajini gormek olmayacaq. 'except Exception as e:' yazin",
         "XETA"),
        (r'open\s*\(["\'][^"\']+["\']\s*,\s*["\'][rwa][b]?["\']\s*\)',
         "ENCODING YOXDUR — open() cagrisinda encoding='utf-8' olmalidir",
         "XEBERDARLIQ"),
        (r'(password|secret)\s*=\s*["\'][^"\']{8,}["\']',
         "HARDCODED SIRR — bu deyeri .env-e kocurun",
         "XETA"),
    ]
    for fpath in all_py_files(root):
        if "frontend" in fpath.replace("\\","/"): continue
        r = rel(root, fpath)
        try: lines = open(fpath, encoding="utf-8", errors="replace").readlines()
        except: continue
        for i, line in enumerate(lines, 1):
            s = line.strip()
            if s.startswith("#"): continue
            for pattern, msg, level in rules:
                if re.search(pattern, line, re.IGNORECASE):
                    found = True
                    print(f"\n  [{level}] {r}  —  Setir {i}")
                    print(f"           Sebeb: {msg}")
                    print(f"           Kod  : {safe(s[:90])}")
                    break
    if not found:
        print("  [OK] Real kod buqu tapilmadi.")

# ─────────────────────────────────────────────────────────
# 6. PARSER TESTI
# ─────────────────────────────────────────────────────────
def run_parser(root):
    print("\n[6] PARSER TESTI")
    try:
        backend = os.path.join(root, "backend")
        for p in [backend, root]:
            if p not in sys.path: sys.path.insert(0, p)
        from parser import parse_soccer_stats
        result = parse_soccer_stats(
            "Manchester United vs Liverpool\nPremier League\n"
            "United evde ortalama 1.8 qol atir.\nOver 2.5 faiz: 65%\n"
        )
        print("  [OK] Parser ugurla isledi!")
        print("  Netice (ilk 3 sahe):", {k:v for k,v in list(result.items())[:3]})
    except Exception as e:
        print("  [XETA] Parser crash etdi!")
        tb = traceback.extract_tb(sys.exc_info()[2])
        for fr in tb:
            r = safe(rel(root, fr.filename))
            if "site-packages" in r: continue
            print(f"         Fayl   : {r}")
            print(f"         Setir  : {fr.lineno}  |  Funksiya: {fr.name}")
            print(f"         Kod    : {safe(str(fr.line))}")
        print(f"  Xeta novu   : {type(e).__name__}")
        print(f"  Xeta mesaji : {safe(e)}")
        s = str(e).lower()
        if "latin-1" in s or "codec" in s:
            print("  SEBEB: .env-deki API key-de xususi herf var. [1]-e baxin.")
        elif "401" in s: print("  SEBEB: API key sehvdir.")
        elif "429" in s or "rate" in s: print("  SEBEB: Rate limit. Gozleyin.")
        elif "timeout" in s or "connection" in s: print("  SEBEB: Internet baglantisi yoxdur.")
        elif "no module" in s: print("  SEBEB: Paket qurashdirilmayib.")

# ─────────────────────────────────────────────────────────
def main():
    root = find_root()
    print("=" * 55)
    print("  LAYIHE DIAQNOSTIKASI")
    print(f"  Kok: {root}")
    print("=" * 55)
    check_encoding(root)
    check_syntax(root)
    check_imports(root)
    check_env(root)
    check_bugs(root)
    run_parser(root)
    print("\n" + "=" * 55)
    print("  DIAQNOSTIKA BITTI")
    print("=" * 55)

if __name__ == "__main__":
    main()