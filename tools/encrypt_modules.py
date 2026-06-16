"""
tools/encrypt_modules.py — أداة تشفير ملفات المشروع (للمطوّر فقط)
Telegram Automation Suite | By: Akram Haig | +967772009303

شغّل هذا الملف مرة واحدة بعد كل تعديل على الكود:
    python tools/encrypt_modules.py

يشفّر جميع ملفات .py في modules/ وملف main.py
ويحذف الأصل بعد التشفير.
"""

import sys
import hashlib
import base64
import getpass
from pathlib import Path

# ─── الهاش المدمج لكلمة المرور (نفس الموجود في start.py) ─────────────────────
_PH = (
    b"\x82\x16\xb1\x9d\xbf\x92\x9e\x22"
    b"\x54\x95\xb0\x24\xa0\xa2\x54\x81"
    b"\x08\x32\x78\x05\x3f\x44\xbc\x33"
    b"\x44\xdb\x7c\x81\xbc\xc6\x94\x3f"
)

_SEED = b"\x4b\x39\x17\xfa\x02\xc8\x5d\x3e\x91\x7b\x44\xf6\x0a\xd3\x28\x55"

BASE_DIR = Path(__file__).parent.parent  # جذر المشروع

# ─── الملفات التي لا تُشفَّر (تبقى قابلة للقراءة) ────────────────────────────
SKIP_FILES = {
    "__init__.py",       # فارغ، لا حاجة لتشفيره
    "device_lock.py",    # يحتوي فقط على الهاش (لا كود حساس)
}

# ─── المجلدات التي تُشفَّر ────────────────────────────────────────────────────
ENCRYPT_DIRS = [
    BASE_DIR / "modules",
]

# ─── الملفات الجذرية التي تُشفَّر ────────────────────────────────────────────
ENCRYPT_ROOT_FILES = [
    BASE_DIR / "main.py",
]


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


def _derive_key(pw: str) -> bytes:
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


def encrypt_file(path: Path, fernet) -> Path:
    source  = path.read_bytes()
    enc     = fernet.encrypt(source)
    out     = path.with_suffix(".pye")
    out.write_bytes(enc)
    return out


def decrypt_file(path: Path, fernet) -> Path:
    """لفك التشفير عند الحاجة للتعديل."""
    enc    = path.read_bytes()
    source = fernet.decrypt(enc)
    out    = path.with_suffix(".py")
    out.write_bytes(source)
    return out


def collect_py_files() -> list[Path]:
    files = []
    for d in ENCRYPT_DIRS:
        if d.exists():
            for f in sorted(d.glob("*.py")):
                if f.name not in SKIP_FILES:
                    files.append(f)
    for f in ENCRYPT_ROOT_FILES:
        if f.exists():
            files.append(f)
    return files


def collect_pye_files() -> list[Path]:
    files = []
    for d in ENCRYPT_DIRS:
        if d.exists():
            for f in sorted(d.glob("*.pye")):
                files.append(f)
    for f in ENCRYPT_ROOT_FILES:
        pye = f.with_suffix(".pye")
        if pye.exists():
            files.append(pye)
    return files


def main():
    print("\n  ╔══════════════════════════════════════════════════╗")
    print("  ║   🔒  Telegram Suite — Module Encryptor          ║")
    print("  ║   By: Akram Haig | +967772009303                ║")
    print("  ╚══════════════════════════════════════════════════╝\n")

    try:
        import cryptography  # noqa: F401
    except ImportError:
        print("  ❌  pip install cryptography\n")
        sys.exit(1)

    from cryptography.fernet import Fernet

    print("  الوضع:")
    print("  [1] 🔒 تشفير الملفات (encrypt)  ← للنشر")
    print("  [2] 🔓 فك التشفير  (decrypt)   ← للتعديل")
    print("  [0] خروج\n")

    choice = input("  اختر: ").strip()
    if choice == "0":
        return

    # التحقق من كلمة المرور
    print()
    for attempt in range(3):
        pw = getpass.getpass("  كلمة المرور: ")
        if _verify_password(pw.strip()):
            break
        remaining = 2 - attempt
        if remaining > 0:
            print(f"  ❌ خاطئة ({remaining} محاولة متبقية)")
        else:
            print("  ❌ تم إغلاق الأداة.")
            sys.exit(1)

    pw = pw.strip()
    key    = _derive_key(pw)
    fernet = Fernet(key)
    print()

    if choice == "1":
        # ─── تشفير ───────────────────────────────────────────────────────
        py_files = collect_py_files()
        if not py_files:
            print("  ⚠️  لا توجد ملفات .py لتشفيرها.")
            sys.exit(0)

        print(f"  سيتم تشفير {len(py_files)} ملف:\n")
        for f in py_files:
            print(f"  • {f.relative_to(BASE_DIR)}")

        print()
        confirm = input("  متأكد؟ سيُحذف الكود الأصلي [y/N]: ").strip().lower()
        if confirm != "y":
            print("  إلغاء.")
            return

        print()
        ok = 0
        for f in py_files:
            try:
                out = encrypt_file(f, fernet)
                f.unlink()  # احذف الأصل
                print(f"  ✅  {f.name} → {out.name}")
                ok += 1
            except Exception as e:
                print(f"  ❌  {f.name}: {e}")

        print(f"\n  تم تشفير {ok}/{len(py_files)} ملف.")
        print("  الآن يمكنك رفع المشروع لـ GitHub — الملفات .pye غير قابلة للقراءة.\n")

        # تحديث .gitignore
        gi = BASE_DIR / ".gitignore"
        gi_content = gi.read_text(encoding="utf-8") if gi.exists() else ""
        additions = []
        for line in ["# ملفات المصدر الأصلية — لا تُرفع للمستودع",
                     "modules/*.py", "main.py", "!modules/__init__.py",
                     "!modules/device_lock.py", "tools/encrypt_modules.py"]:
            if line not in gi_content:
                additions.append(line)
        if additions:
            with open(gi, "a", encoding="utf-8") as f:
                f.write("\n" + "\n".join(additions) + "\n")
            print("  ✅  تم تحديث .gitignore")

    elif choice == "2":
        # ─── فك التشفير ──────────────────────────────────────────────────
        pye_files = collect_pye_files()
        if not pye_files:
            print("  ⚠️  لا توجد ملفات .pye لفك تشفيرها.")
            sys.exit(0)

        print(f"  سيتم فك تشفير {len(pye_files)} ملف:\n")
        for f in pye_files:
            print(f"  • {f.relative_to(BASE_DIR)}")

        print()
        ok = 0
        for f in pye_files:
            try:
                out = decrypt_file(f, fernet)
                f.unlink()
                print(f"  🔓  {f.name} → {out.name}")
                ok += 1
            except Exception as e:
                print(f"  ❌  {f.name}: {e}")

        print(f"\n  تم فك تشفير {ok}/{len(pye_files)} ملف.")
        print("  يمكنك الآن تعديل الكود. بعد الانتهاء شغّل التشفير مجدداً.\n")

    else:
        print("  خيار غير صحيح.")


if __name__ == "__main__":
    main()
