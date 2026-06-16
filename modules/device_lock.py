"""
نظام القفل الذكي — Device Lock System
Telegram Automation Suite
By: Akram Haig | +967772009303
"""

import os
import sys
import hashlib
import platform
import subprocess
import json
import base64
import struct
import time
from pathlib import Path

# ─── كلمة المرور مدمجة في الكود ─────────────────────────────────────────────
_P = "05450545"

# ─── موقع الملف المخفي ────────────────────────────────────────────────────────
_HIDDEN_DIR  = Path.home() / ".cache" / ".libsys" / ".runtime"
_HIDDEN_FILE = _HIDDEN_DIR / ".dconf_cache"

# ─── بذرة مفتاح التشفير (مدمجة في الكود) ─────────────────────────────────────
_SEED = b"\x4b\x39\x17\xfa\x02\xc8\x5d\x3e\x91\x7b\x44\xf6\x0a\xd3\x28\x55"


def _derive_key() -> bytes:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    import cryptography.hazmat.backends as backends

    salt = hashlib.sha256(_SEED).digest()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390000,
        backend=backends.default_backend(),
    )
    raw = kdf.derive(_SEED + b"telegram_suite_v1")
    return base64.urlsafe_b64encode(raw)


def _get_fernet():
    from cryptography.fernet import Fernet
    return Fernet(_derive_key())


# ─── مولد البصمة ──────────────────────────────────────────────────────────────

def _read_file_safe(path: str) -> str:
    try:
        with open(path, "r", errors="ignore") as f:
            return f.read(512).strip()
    except Exception:
        return ""


def _run_cmd(cmd: list, timeout: int = 3) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def _generate_fingerprint() -> str:
    parts = []

    # 1. معالج — /proc/cpuinfo
    cpu = _read_file_safe("/proc/cpuinfo")
    if cpu:
        for line in cpu.splitlines():
            ll = line.lower()
            if ll.startswith("hardware"):
                parts.append("cpu_hw:" + line.split(":")[-1].strip())
            elif ll.startswith("serial"):
                s = line.split(":")[-1].strip()
                if s and s != "0000000000000000":
                    parts.append("cpu_serial:" + s)

    # 2. Machine ID
    mid = _read_file_safe("/etc/machine-id") or _read_file_safe("/var/lib/dbus/machine-id")
    if mid:
        parts.append("machine_id:" + mid[:32])

    # 3. Android — getprop
    for prop in ["ro.serialno", "ro.boot.serialno", "ro.product.model",
                 "ro.product.brand", "ro.product.device", "ro.product.board",
                 "ro.build.fingerprint"]:
        val = _run_cmd(["getprop", prop])
        if val and val not in ("unknown", ""):
            parts.append(f"{prop.replace('.','_')}:{val[:80]}")

    # 4. عناوين الماك
    net_path = Path("/sys/class/net")
    if net_path.exists():
        for iface in sorted(net_path.iterdir()):
            mac_file = iface / "address"
            if mac_file.exists():
                mac = _read_file_safe(str(mac_file))
                if mac and mac != "00:00:00:00:00:00":
                    parts.append(f"mac_{iface.name}:{mac}")

    # 5. معلومات احتياطية
    parts.append("node:" + platform.node())
    parts.append("arch:" + platform.machine())

    if len(parts) < 2:
        parts.append("python:" + sys.version[:20])

    raw = "|".join(sorted(parts))
    return hashlib.sha512(raw.encode("utf-8")).hexdigest()


# ─── حفظ وقراءة البصمة ───────────────────────────────────────────────────────

def _save_fingerprint(fingerprint: str) -> None:
    _HIDDEN_DIR.mkdir(parents=True, exist_ok=True)
    fernet = _get_fernet()
    payload = {"fp": fingerprint, "ts": int(time.time()), "v": 2}
    encrypted = fernet.encrypt(json.dumps(payload).encode("utf-8"))
    header = b"\x89SYS\r\n\x1a\n" + struct.pack(">I", len(encrypted))
    _HIDDEN_FILE.write_bytes(header + encrypted)
    _HIDDEN_FILE.chmod(0o600)


def _load_fingerprint() -> str | None:
    if not _HIDDEN_FILE.exists():
        return None
    try:
        raw = _HIDDEN_FILE.read_bytes()
        header_size = 12
        if len(raw) < header_size:
            return None
        encrypted = raw[header_size:]
        fernet = _get_fernet()
        decrypted = fernet.decrypt(encrypted)
        payload = json.loads(decrypted.decode("utf-8"))
        return payload.get("fp")
    except Exception:
        return None


# ─── واجهة التعطل ─────────────────────────────────────────────────────────────

def _show_blocked():
    os.system("clear")
    print("")
    print("  ╔══════════════════════════════════════════════════╗")
    print("  ║                                                  ║")
    print("  ║           ⛔  خطأ في التحقق                      ║")
    print("  ║                                                  ║")
    print("  ║   هذه الأداة مربوطة بجهاز آخر.                  ║")
    print("  ║   لا يمكن تشغيلها على هذا الجهاز.               ║")
    print("  ║                                                  ║")
    print("  ║   للمساعدة تواصل مع الأدمن:                      ║")
    print("  ║   +967772009303                                  ║")
    print("  ║                                                  ║")
    print("  ╚══════════════════════════════════════════════════╝")
    print("")
    time.sleep(2)
    sys.exit(1)


def _show_corrupt():
    os.system("clear")
    print("")
    print("  ╔══════════════════════════════════════════════════╗")
    print("  ║                                                  ║")
    print("  ║           ⚠️  تعذر التحقق                        ║")
    print("  ║                                                  ║")
    print("  ║   بيانات التفعيل غير موجودة أو تالفة.            ║")
    print("  ║                                                  ║")
    print("  ║   للمساعدة تواصل مع الأدمن:                      ║")
    print("  ║   +967772009303                                  ║")
    print("  ║                                                  ║")
    print("  ╚══════════════════════════════════════════════════╝")
    print("")
    time.sleep(2)
    sys.exit(1)


# ─── شاشة التفعيل ─────────────────────────────────────────────────────────────

def _activation_screen() -> None:
    import getpass
    os.system("clear")
    print("")
    print("  ╔══════════════════════════════════════════════════╗")
    print("  ║                                                  ║")
    print("  ║      Telegram Automation Suite                   ║")
    print("  ║      By: Akram Haig | +967772009303              ║")
    print("  ║                                                  ║")
    print("  ╠══════════════════════════════════════════════════╣")
    print("  ║                                                  ║")
    print("  ║      🔐  تفعيل الأداة على هذا الجهاز             ║")
    print("  ║                                                  ║")
    print("  ╚══════════════════════════════════════════════════╝")
    print("")

    try:
        pw = getpass.getpass("  أدخل كلمة المرور: ")
    except (KeyboardInterrupt, EOFError):
        print("")
        sys.exit(0)

    if pw.strip() != _P:
        os.system("clear")
        print("")
        print("  ❌  كلمة المرور خاطئة.")
        print("")
        time.sleep(2)
        sys.exit(1)

    print("")
    print("  ⏳  جاري ربط الأداة بهذا الجهاز...")
    fingerprint = _generate_fingerprint()
    _save_fingerprint(fingerprint)

    os.system("clear")
    print("")
    print("  ╔══════════════════════════════════════════════════╗")
    print("  ║                                                  ║")
    print("  ║      ✅  تم التفعيل بنجاح!                       ║")
    print("  ║                                                  ║")
    print("  ║      الأداة الآن مرتبطة بهذا الجهاز.             ║")
    print("  ║                                                  ║")
    print("  ╚══════════════════════════════════════════════════╝")
    print("")
    time.sleep(2)


# ─── نقطة الدخول ─────────────────────────────────────────────────────────────

def check_device_lock() -> None:
    """
    استدعِ هذه الدالة أول شيء في main.py.

    المنطق:
      - لا يوجد ملف قفل  → شاشة التفعيل (كلمة المرور + حفظ البصمة)
      - يوجد ملف، بصمة مطابقة  → تشغيل طبيعي
      - يوجد ملف، بصمة مختلفة → رسالة الحجب + إغلاق
      - الملف تالف / لا يُفك تشفيره → رسالة التلف + إغلاق
    """
    try:
        import cryptography  # noqa: F401
    except ImportError:
        print("\n  ⚠️  يرجى تشغيل: pip install cryptography\n")
        sys.exit(1)

    if not _HIDDEN_FILE.exists():
        # أول تشغيل — فعّل الأداة
        _activation_screen()
        return

    saved_fp = _load_fingerprint()

    if saved_fp is None:
        # الملف موجود لكن تالف
        _show_corrupt()
        return

    current_fp = _generate_fingerprint()

    if current_fp == saved_fp:
        return  # الجهاز الأصلي — تشغيل طبيعي
    else:
        _show_blocked()  # جهاز مختلف — منسوخة
