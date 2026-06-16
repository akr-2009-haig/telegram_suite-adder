"""
start.py — نقطة الدخول الوحيدة للأداة
Telegram Automation Suite | By: Akram Haig | +967772009303

الملفات المشفرة (.pye) لا تُقرأ بدون كلمة المرور الصحيحة.
"""

import os
import sys
import time
import json
import struct
import hashlib
import base64
import platform
import subprocess
from pathlib import Path

# ─── الهاش المدمج لكلمة المرور (PBKDF2-SHA256 — لا يمكن عكسه) ────────────────
_PH = (
    b"\x82\x16\xb1\x9d\xbf\x92\x9e\x22"
    b"\x54\x95\xb0\x24\xa0\xa2\x54\x81"
    b"\x08\x32\x78\x05\x3f\x44\xbc\x33"
    b"\x44\xdb\x7c\x81\xbc\xc6\x94\x3f"
)

_SEED = b"\x4b\x39\x17\xfa\x02\xc8\x5d\x3e\x91\x7b\x44\xf6\x0a\xd3\x28\x55"

BASE_DIR    = Path(__file__).parent
_HIDDEN_DIR = Path.home() / ".cache" / ".libsys" / ".runtime"
_FP_FILE    = _HIDDEN_DIR / ".dconf_cache"
_KEY_FILE   = _HIDDEN_DIR / ".key_cache"


# ═══════════════════════════════════════════════════════════════════════════════
#  1. التحقق من كلمة المرور
# ═══════════════════════════════════════════════════════════════════════════════

def _verify_password(pw: str) -> bool:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32,
        salt=_SEED, iterations=390000,
        backend=default_backend(),
    )
    candidate = kdf.derive(pw.encode("utf-8"))
    return hashlib.compare_digest(candidate, _PH)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. اشتقاق مفتاح Fernet من كلمة المرور
# ═══════════════════════════════════════════════════════════════════════════════

def _derive_fernet_key(pw: str) -> bytes:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    salt = hashlib.sha256(_SEED + b"enc_modules_v1").digest()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32,
        salt=salt, iterations=390000,
        backend=default_backend(),
    )
    raw = kdf.derive(pw.encode("utf-8") + _SEED)
    return base64.urlsafe_b64encode(raw)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. بصمة الجهاز
# ═══════════════════════════════════════════════════════════════════════════════

def _read_safe(path: str) -> str:
    try:
        with open(path, "r", errors="ignore") as f:
            return f.read(512).strip()
    except Exception:
        return ""


def _run(cmd: list) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        return r.stdout.strip()
    except Exception:
        return ""


def _fingerprint() -> str:
    parts = []
    cpu = _read_safe("/proc/cpuinfo")
    for line in cpu.splitlines():
        ll = line.lower()
        if ll.startswith("hardware"):
            parts.append("hw:" + line.split(":")[-1].strip())
        elif ll.startswith("serial"):
            s = line.split(":")[-1].strip()
            if s and s != "0000000000000000":
                parts.append("serial:" + s)
    mid = _read_safe("/etc/machine-id") or _read_safe("/var/lib/dbus/machine-id")
    if mid:
        parts.append("mid:" + mid[:32])
    for prop in ["ro.serialno", "ro.boot.serialno", "ro.product.model",
                 "ro.product.brand", "ro.build.fingerprint"]:
        v = _run(["getprop", prop])
        if v and v != "unknown":
            parts.append(f"{prop}:{v[:60]}")
    net = Path("/sys/class/net")
    if net.exists():
        for iface in sorted(net.iterdir()):
            mac = _read_safe(str(iface / "address"))
            if mac and mac != "00:00:00:00:00:00":
                parts.append(f"mac_{iface.name}:{mac}")
    parts.append("node:" + platform.node())
    parts.append("arch:" + platform.machine())
    if len(parts) < 2:
        parts.append("py:" + sys.version[:20])
    return hashlib.sha512("|".join(sorted(parts)).encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════════
#  4. تخزين وقراءة مفتاح Fernet (مشفر ببصمة الجهاز)
# ═══════════════════════════════════════════════════════════════════════════════

def _fp_to_key(fp: str) -> bytes:
    """يحوّل بصمة الجهاز لمفتاح AES لتشفير/فك مفتاح Fernet."""
    return base64.urlsafe_b64encode(
        hashlib.pbkdf2_hmac("sha256", fp.encode(), _SEED, 200000)
    )


def _save_session(fernet_key: bytes, fp: str):
    from cryptography.fernet import Fernet
    _HIDDEN_DIR.mkdir(parents=True, exist_ok=True)

    # (أ) احفظ البصمة مشفرة بمفتاح ثابت من SEED
    seed_fernet = Fernet(base64.urlsafe_b64encode(
        hashlib.sha256(_SEED + b"fp_enc").digest()
    ))
    fp_payload  = json.dumps({"fp": fp, "ts": int(time.time()), "v": 3}).encode()
    fp_enc      = seed_fernet.encrypt(fp_payload)
    hdr         = b"\x89SYS\r\n\x1a\n" + struct.pack(">I", len(fp_enc))
    _FP_FILE.write_bytes(hdr + fp_enc)
    _FP_FILE.chmod(0o600)

    # (ب) احفظ مفتاح Fernet مشفراً ببصمة الجهاز
    fp_fernet   = Fernet(_fp_to_key(fp))
    key_enc     = fp_fernet.encrypt(fernet_key)
    _KEY_FILE.write_bytes(key_enc)
    _KEY_FILE.chmod(0o600)


def _load_session() -> tuple[str | None, bytes | None]:
    """يُرجع (بصمة_محفوظة, مفتاح_Fernet) أو (None, None) عند الفشل."""
    from cryptography.fernet import Fernet, InvalidToken
    if not _FP_FILE.exists() or not _KEY_FILE.exists():
        return None, None
    try:
        raw     = _FP_FILE.read_bytes()
        fp_enc  = raw[12:]
        seed_fernet = Fernet(base64.urlsafe_b64encode(
            hashlib.sha256(_SEED + b"fp_enc").digest()
        ))
        fp_payload  = json.loads(seed_fernet.decrypt(fp_enc).decode())
        saved_fp    = fp_payload["fp"]
    except Exception:
        return None, None

    try:
        fp_fernet   = Fernet(_fp_to_key(saved_fp))
        fernet_key  = fp_fernet.decrypt(_KEY_FILE.read_bytes())
        return saved_fp, fernet_key
    except InvalidToken:
        return saved_fp, None


# ═══════════════════════════════════════════════════════════════════════════════
#  5. Import Hook — يفك تشفير الوحدات عند الاستيراد
# ═══════════════════════════════════════════════════════════════════════════════

_FERNET_KEY: bytes | None = None


def _setup_import_hook():
    import importlib.abc
    import importlib.machinery

    class EncFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            parts = fullname.split(".")
            # نبحث في مجلدَي modules/ فقط
            if parts[0] not in ("modules",):
                return None
            if len(parts) == 1:
                pkg = BASE_DIR / parts[0]
                if pkg.is_dir():
                    init = pkg / "__init__.pye"
                    if init.exists():
                        return importlib.machinery.ModuleSpec(
                            fullname, EncLoader(init), origin=str(init), is_package=True
                        )
                    # مجلد عادي بدون تشفير
                    init_py = pkg / "__init__.py"
                    if init_py.exists():
                        return None  # اترك لـ Python العادي
            elif len(parts) == 2:
                enc = BASE_DIR / parts[0] / (parts[1] + ".pye")
                if enc.exists():
                    return importlib.machinery.ModuleSpec(
                        fullname, EncLoader(enc), origin=str(enc)
                    )
            return None

    class EncLoader(importlib.abc.Loader):
        def __init__(self, path: Path):
            self.path = path

        def create_module(self, spec):
            return None

        def exec_module(self, module):
            from cryptography.fernet import Fernet, InvalidToken
            fernet = Fernet(_FERNET_KEY)
            try:
                source = fernet.decrypt(self.path.read_bytes()).decode("utf-8")
            except InvalidToken:
                print(f"\n  ❌  تعذّر فك تشفير {self.path.name} — الملف تالف أو مفتاح خاطئ.")
                sys.exit(1)
            code = compile(source, str(self.path), "exec")
            exec(code, module.__dict__)

    sys.meta_path.insert(0, EncFinder())


# ═══════════════════════════════════════════════════════════════════════════════
#  6. شاشات واجهة المستخدم
# ═══════════════════════════════════════════════════════════════════════════════

def _clear():
    os.system("clear")


def _show_blocked():
    _clear()
    print("\n  ╔══════════════════════════════════════════════════╗")
    print("  ║           ⛔  خطأ في التحقق                      ║")
    print("  ║                                                  ║")
    print("  ║   هذه الأداة مربوطة بجهاز آخر.                  ║")
    print("  ║   لا يمكن تشغيلها على هذا الجهاز.               ║")
    print("  ║                                                  ║")
    print("  ║   للمساعدة: +967772009303                        ║")
    print("  ╚══════════════════════════════════════════════════╝\n")
    time.sleep(2)
    sys.exit(1)


def _activation_screen() -> str:
    """يطلب كلمة المرور، يتحقق، ويُرجعها عند النجاح."""
    import getpass
    _clear()
    print("\n  ╔══════════════════════════════════════════════════╗")
    print("  ║      Telegram Automation Suite                   ║")
    print("  ║      By: Akram Haig | +967772009303              ║")
    print("  ╠══════════════════════════════════════════════════╣")
    print("  ║      🔐  تفعيل الأداة على هذا الجهاز             ║")
    print("  ╚══════════════════════════════════════════════════╝\n")

    for attempt in range(3):
        try:
            pw = getpass.getpass("  أدخل كلمة المرور: ")
        except (KeyboardInterrupt, EOFError):
            print("")
            sys.exit(0)

        if _verify_password(pw.strip()):
            return pw.strip()

        remaining = 2 - attempt
        _clear()
        if remaining > 0:
            print(f"\n  ❌  كلمة المرور خاطئة. ({remaining} محاولة متبقية)\n")
            time.sleep(1)
        else:
            print("\n  ❌  كلمة المرور خاطئة. تم إغلاق الأداة.\n")
            time.sleep(2)
            sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
#  7. نقطة الدخول الرئيسية
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    global _FERNET_KEY

    # تحقق من توفر مكتبة cryptography
    try:
        import cryptography  # noqa: F401
    except ImportError:
        print("\n  ⚠️  يرجى تشغيل: pip install cryptography\n")
        sys.exit(1)

    # تحقق من وجود الملفات المشفرة
    enc_files = list((BASE_DIR / "modules").glob("*.pye"))
    if not enc_files:
        print("\n  ⚠️  لم يتم العثور على ملفات مشفرة (.pye)")
        print("  تأكد من تشغيل tools/encrypt_modules.py أولاً.\n")
        sys.exit(1)

    saved_fp, fernet_key = _load_session()
    current_fp = _fingerprint()

    if saved_fp is None:
        # ─── أول تشغيل على هذا الجهاز ───
        pw         = _activation_screen()
        fernet_key = _derive_fernet_key(pw)
        _clear()
        print("\n  ⏳  جاري ربط الأداة بهذا الجهاز...")
        _save_session(fernet_key, current_fp)
        _clear()
        print("\n  ╔══════════════════════════════════════════════════╗")
        print("  ║      ✅  تم التفعيل بنجاح!                       ║")
        print("  ║      الأداة الآن مرتبطة بهذا الجهاز.             ║")
        print("  ╚══════════════════════════════════════════════════╝\n")
        time.sleep(1.5)

    else:
        # ─── جهاز مسجّل — تحقق من البصمة ───
        if current_fp != saved_fp:
            _show_blocked()

        if fernet_key is None:
            # الملف موجود لكن تالف
            _clear()
            print("\n  ⚠️  بيانات التفعيل تالفة. يرجى التواصل مع الأدمن: +967772009303\n")
            time.sleep(2)
            sys.exit(1)

    # ─── تفعيل Import Hook ───
    _FERNET_KEY = fernet_key
    _setup_import_hook()

    # ─── تشغيل الأداة ───
    main_pye = BASE_DIR / "main.pye"
    if not main_pye.exists():
        # fallback: اشتغل main.py لو موجود
        main_py = BASE_DIR / "main.py"
        if main_py.exists():
            import runpy
            runpy.run_path(str(main_py), run_name="__main__")
        else:
            print("\n  ❌  main.pye غير موجود. شغّل encrypt_modules.py أولاً.\n")
            sys.exit(1)
        return

    from cryptography.fernet import Fernet, InvalidToken
    fernet = Fernet(_FERNET_KEY)
    try:
        source = fernet.decrypt(main_pye.read_bytes()).decode("utf-8")
    except InvalidToken:
        print("\n  ❌  تعذّر فك تشفير main.pye — الملف تالف.\n")
        sys.exit(1)

    code = compile(source, str(main_pye), "exec")
    globs = {
        "__name__": "__main__",
        "__file__": str(BASE_DIR / "main.py"),
        "__spec__": None,
    }
    exec(code, globs)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  [مقاطعة] إلى اللقاء!\n")
        sys.exit(0)
