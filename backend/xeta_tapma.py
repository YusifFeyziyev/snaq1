# debug_runner.py — Layihe tam diaqnostika aləti
# Istifade: python debug_runner.py
# Backend qovluguna qoy, ozü root-u tapar

import sys
import io
import os
import ast
import py_compile
import traceback
import importlib
import json
import re
import tokenize

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ─────────────────────────────────────────
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "env", "dist", "build", ".next", ".cache", ".idea", ".mypy_cache"
}
SKIP_FILES = {"debug_runner.py"}
# ─────────────────────────────────────────

def safe(text):
    return str(text).encode('ascii', errors='replace').decode('ascii')

def header(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")

def ok(msg):    print(f"  [OK]    {msg}")
def warn(msg):  print(f"  [XEBERDARLIQ] {msg}")
def err(msg):   print(f"  [XETA]  {msg}")
def info(msg):  print(f"  [INFO]  {msg}")

# ══════════════════════════════════════════
# LAYIHE KOKU
# ══════════════════════════════════════════
def find_root():
    current = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(current).lower() in ("backend", "src"):
        return os.path.dirname(current)
    return current

# ══════════════════════════════════════════
# 1. ENCODING YOXLAMASI
# ══════════════════════════════════════════
def check_encoding(root):
    header("1. ENCODİNG YOXLAMASI (.py, .env, .js, .ts, .jsx, .tsx)")
    found = False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if fname in SKIP_FILES:
                continue
            ext = os.path.splitext(fname)[1].lower()
            is_env = fname.startswith(".env") or fname == ".env"
            if ext not in (".py", ".js", ".ts", ".jsx", ".tsx", ".json") and not is_env:
                continue
            fpath = os.path.join(dirpath, fname)
            rel = os.path.relpath(fpath, root).replace("\\", "/")
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                for i, line in enumerate(lines, 1):
                    bad = [(j, c, hex(ord(c))) for j, c in enumerate(line.rstrip("\n")) if ord(c) > 127]
                    if bad:
                        found = True
                        err(f"{rel}  —  Setir {i}")
                        for pos, char, code in bad:
                            print(f"           Movqe {pos+1}: '{safe(char)}'  ({code})")
                        print(f"           Metn: {safe(line.rstrip())[:80]}")
            except Exception as e:
                err(f"{rel} oxunmadi: {safe(e)}")
    if not found:
        ok("Encoding problemi tapilmadi.")

# ══════════════════════════════════════════
# 2. PYTHON SİNTAKSİS YOXLAMASI
# ══════════════════════════════════════════
def check_syntax(root):
    header("2. PYTHON SİNTAKSİS YOXLAMASI")
    found = False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if not fname.endswith(".py") or fname in SKIP_FILES:
                continue
            fpath = os.path.join(dirpath, fname)
            rel = os.path.relpath(fpath, root).replace("\\", "/")
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    source = f.read()
                ast.parse(source, filename=fpath)
                ok(f"{rel}")
            except SyntaxError as e:
                found = True
                err(f"{rel}  —  Setir {e.lineno}")
                print(f"           Xeta: {safe(e.msg)}")
                if e.text:
                    print(f"           Kod : {safe(e.text.rstrip())}")
            except Exception as e:
                err(f"{rel}: {safe(e)}")
    if not found:
        ok("Sintaksis xetasi tapilmadi.")

# ══════════════════════════════════════════
# 3. İMPORT YOXLAMASI
# ══════════════════════════════════════════
def check_imports(root):
    header("3. İMPORT YOXLAMASI (quraşdırılmamış paketlər)")
    backend = os.path.join(root, "backend")
    search_paths = [root, backend] if os.path.exists(backend) else [root]

    found = False
    checked = set()

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if not fname.endswith(".py") or fname in SKIP_FILES:
                continue
            fpath = os.path.join(dirpath, fname)
            rel = os.path.relpath(fpath, root).replace("\\", "/")
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    source = f.read()
                tree = ast.parse(source)
            except:
                continue

            for node in ast.walk(tree):
                pkg = None
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        pkg = alias.name.split(".")[0]
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        pkg = node.module.split(".")[0]

                if pkg and pkg not in checked:
                    checked.add(pkg)
                    # Oz lokal modullari atla
                    local = any(
                        os.path.exists(os.path.join(p, pkg + ".py")) or
                        os.path.exists(os.path.join(p, pkg))
                        for p in search_paths
                    )
                    if local:
                        continue
                    try:
                        importlib.util.find_spec(pkg)
                    except (ModuleNotFoundError, ValueError):
                        found = True
                        err(f"'{pkg}'  —  tapilmadi  ({rel} faylinda istifade olunur)")
                        print(f"           Qurashdirin: pip install {pkg}")

    if not found:
        ok("Butun importlar movcuddur.")

# ══════════════════════════════════════════
# 4. .ENV YOXLAMASI
# ══════════════════════════════════════════
def check_env(root):
    header("4. .ENV FAYLI YOXLAMASI")
    env_path = None
    for candidate in [
        os.path.join(root, ".env"),
        os.path.join(root, "backend", ".env"),
    ]:
        if os.path.exists(candidate):
            env_path = candidate
            break

    if not env_path:
        warn(".env fayli tapilmadi! (root və ya backend qovlugunda axtarildi)")
        return

    info(f".env tapildi: {os.path.relpath(env_path, root)}")
    empty_keys = []
    ok_keys = []

    with open(env_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    for i, line in enumerate(lines, 1):
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            warn(f"Setir {i}: '=' yoxdur -> {safe(line)}")
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")

        # Non-ASCII yoxla
        bad = [(j, c, hex(ord(c))) for j, c in enumerate(val) if ord(c) > 127]
        if bad:
            err(f"Setir {i}: '{key}' — deyerde xususi herf var!")
            for pos, char, code in bad:
                print(f"           Movqe {pos+1}: '{safe(char)}'  ({code})")
        elif not val:
            empty_keys.append((i, key))
            warn(f"Setir {i}: '{key}' — bos deger!")
        else:
            ok_keys.append(key)

    if ok_keys:
        ok(f"Dolu key-ler: {', '.join(ok_keys)}")
    if empty_keys:
        for lineno, k in empty_keys:
            warn(f"Setir {lineno}: '{k}' bos — API call-lar ishlemeyecek")

# ══════════════════════════════════════════
# 5. UMUMİ KOD PROBLEMLERI
# ══════════════════════════════════════════
def check_common_issues(root):
    header("5. UMUMİ KOD PROBLEMLERİ")
    found = False

    patterns = [
        # (regex, mesaj, ciddilik)
        (r'open\s*\([^)]+\)(?!\s*as)',
         "open() istifade olunub amma 'with' yoxdur — fayl baglanmaya biler", "warn"),
        (r'open\s*\(["\'][^"\']+["\']\s*,\s*["\'][rwa]["\'](?!\s*,\s*encoding)',
         "open() cagririsinda encoding=\'utf-8\' yoxdur", "warn"),
        (r'except\s*:',
         "Cildirmis 'except:' — butun xetalari yutur, debug chetinleshir", "warn"),
        (r'except\s+Exception\s*:',
         "'except Exception:' — xeta mesaji itir, 'as e' elave edin", "warn"),
        (r'print\s*\(',
         "print() tapildi — production-da log sistemi islede bilersiniz", "info"),
        (r'TODO|FIXME|HACK|XXX',
         "Tamamlanmamish qeyd tapildi", "warn"),
        (r'password\s*=\s*["\'][^"\']{3,}["\']',
         "Kodun icinde hardcoded parol gorunur!", "err"),
        (r'api_key\s*=\s*["\'][^"\']{10,}["\']',
         "Kodun icinde hardcoded API key gorunur!", "err"),
        (r'0\.0\.0\.0|localhost|127\.0\.0\.1',
         "Hardcoded host adresi — production-da problem ola biler", "info"),
        (r'time\.sleep\s*\(\s*[5-9]\d*\s*\)',
         "Uzun sleep() tapildi — performansa tesir ede biler", "warn"),
    ]

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if not fname.endswith(".py") or fname in SKIP_FILES:
                continue
            fpath = os.path.join(dirpath, fname)
            rel = os.path.relpath(fpath, root).replace("\\", "/")
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
            except:
                continue

            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                for pattern, msg, level in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        found = True
                        fn = {"warn": warn, "err": err, "info": info}[level]
                        fn(f"{rel}  —  Setir {i}")
                        print(f"           {msg}")
                        print(f"           Kod: {safe(stripped[:80])}")
                        break

    if not found:
        ok("Umumi kod problemi tapilmadi.")

# ══════════════════════════════════════════
# 6. PARSER İŞLƏDİLMƏSİ
# ══════════════════════════════════════════
def run_parser(root):
    header("6. PARSER TEST — işlədilir...")
    try:
        backend = os.path.join(root, "backend")
        for p in [backend, root]:
            if p not in sys.path:
                sys.path.insert(0, p)

        from parser import parse_soccer_stats

        sample = (
            "Manchester United vs Liverpool\n"
            "Premier League\n"
            "Son 5 oyun: United: QMBMQ, Liverpool: MQBMQ\n"
            "United evde ortalama 1.8 qol atir, 1.1 buraxir.\n"
            "Liverpool seferde ortalama 2.0 qol atir, 0.9 buraxir.\n"
            "Over 2.5 faiz: 65%\n"
            "BTTS faiz: 54%\n"
            "Korner ortalama: United 5.3, Liverpool 6.1\n"
        )

        result = parse_soccer_stats(sample)
        output = json.dumps(result, indent=2, ensure_ascii=True)
        ok("Parser UGURLA isledi! Netice:")
        sys.stdout.buffer.write(output.encode("utf-8") + b"\n")

    except Exception as e:
        err("PARSER XETASI!")
        print()
        tb = traceback.extract_tb(sys.exc_info()[2])
        for frame in tb:
            rel = safe(os.path.relpath(frame.filename, root).replace("\\", "/"))
            print(f"  --> Fayl    : {rel}")
            print(f"      Setir   : {frame.lineno}")
            print(f"      Funksiya: {frame.name}")
            print(f"      Kod     : {safe(str(frame.line))}")
            print()
        print(f"  Xeta novu   : {type(e).__name__}")
        print(f"  Xeta mesaji : {safe(e)}")

        s = str(e).lower()
        print()
        if "latin-1" in s or "codec" in s:
            err("SEBEB: Encoding xetasi!")
            print("       .env faylindaki API key-in icinde xususi herf var.")
            print("       Yuxaridaki [4] bolumune baxin.")
        elif "401" in s or "invalid" in s:
            err("SEBEB: API key sehvdir! console.groq.com-dan yenileyin.")
        elif "rate limit" in s or "429" in s:
            warn("SEBEB: Rate limit. Bir az gozleyib yeniden calishdirin.")
        elif "timeout" in s or "connection" in s:
            err("SEBEB: Internet baglantisi yoxdur!")
        elif "no module" in s:
            err("SEBEB: Paket qurashdirilmayib. pip install <paket_adi>")

# ══════════════════════════════════════════
# ANA FUNKSIYA
# ══════════════════════════════════════════
def main():
    root = find_root()

    print("=" * 60)
    print("  LAYİHƏ TAM DİAQNOSTİKASI")
    print(f"  Layihe koku: {root}")
    print("=" * 60)

    check_encoding(root)
    check_syntax(root)
    check_imports(root)
    check_env(root)
    check_common_issues(root)
    run_parser(root)

    print("\n" + "=" * 60)
    print("  DİAQNOSTİKA BİTDİ")
    print("=" * 60)

if __name__ == "__main__":
    main()