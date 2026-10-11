#!/usr/bin/env python3
"""
apk-analyzer: static triage of suspicious Android APKs for incident reporting.

SAFETY: this tool never installs or executes the APK and never contacts any
host found inside it. Everything is read from the file on disk.

Usage:
    python3 analyze_apk.py analyze sample.apk [-o out_dir]
    python3 analyze_apk.py compare out_dir/a.json out_dir/b.json [...]

What it does:
  * hashes, manifest (permissions, components), signing certificate
  * entropy of assets (flags encrypted payloads)
  * auto-detects the common "base64 + rolling XOR" string decoders that
    obfuscators insert, emulates them and decodes every call site
  * pulls IOCs (domains, URLs, IPs, Telegram tokens, numeric IDs, AES-key-like
    strings) out of plain and decoded strings
  * writes a JSON + Markdown report; `compare` shows IOCs shared by samples
"""
import argparse
import base64
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

try:
    from loguru import logger

    logger.remove()
    from androguard.misc import AnalyzeAPK
except ImportError:
    sys.exit("Missing dependencies. Run: pip install -r requirements.txt")

RISKY_PERMS = {
    "REQUEST_INSTALL_PACKAGES": "installs other APKs (dropper)",
    "BIND_ACCESSIBILITY_SERVICE": "reads/controls screen (banker/RAT)",
    "SYSTEM_ALERT_WINDOW": "draws over other apps (phishing overlay)",
    "READ_SMS": "reads SMS (OTP theft)",
    "RECEIVE_SMS": "intercepts SMS (OTP theft)",
    "SEND_SMS": "sends SMS",
    "READ_CONTACTS": "reads contacts",
    "READ_CALL_LOG": "reads call log",
    "RECORD_AUDIO": "records audio",
    "CAMERA": "camera access",
    "BIND_DEVICE_ADMIN": "device admin (hard to uninstall)",
    "BIND_VPN_SERVICE": "VPN interception",
    "MANAGE_EXTERNAL_STORAGE": "all-files access",
    "READ_PHONE_STATE": "device identifiers",
    "QUERY_ALL_PACKAGES": "lists installed apps (AV detection)",
    "RECEIVE_BOOT_COMPLETED": "starts on boot",
    "USE_FULL_SCREEN_INTENT": "full-screen pop-ups",
    "FOREGROUND_SERVICE_MEDIA_PROJECTION": "screen capture service",
}

SUSPICIOUS_API = [
    "Landroid/media/projection/MediaProjection",
    "Landroid/net/VpnService",
    "Landroid/content/pm/PackageInstaller",
    "Ldalvik/system/DexClassLoader",
    "Ldalvik/system/InMemoryDexClassLoader",
    "Landroid/accessibilityservice/AccessibilityService",
    "Landroid/telephony/SmsManager",
    "Landroid/app/admin/DevicePolicyManager",
    "Ljavax/crypto/Cipher",
]

BENIGN_HOSTS = (
    "schemas.android.com", "w3.org", "apache.org", "google.com", "googleapis.com",
    "github.com", "jetbrains.com", "android.com", "kotlinlang.org", "gstatic.com",
    "mozilla.org", "example.com", "xmlpull.org", "ietf.org",
)

URL_RE = re.compile(r"https?://[^\s\"'<>\\]{4,}")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
TG_TOKEN_RE = re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")
HOST_RE = re.compile(r"^(?=.{4,80}$)(?:[a-z0-9-]{2,}\.)+[a-z]{2,24}$")
NUM_ID_RE = re.compile(r"^-?\d{8,13}$")
KEYLIKE_RE = re.compile(r"^(?:[0-9a-fA-F]{16}|[0-9a-fA-F]{32}|[0-9a-fA-F]{64})$")
# TLDs rarely seen in legit code strings but common in throwaway C2 domains.
COMMON_TLDS = {"com", "net", "org", "ru", "uz", "cn", "io", "me", "cc", "xyz", "top",
               "best", "click", "site", "online", "icu", "shop", "vip", "live", "cyou",
               "sbs", "buzz", "fun", "pw", "app", "link", "club", "info", "biz", "tk",
               "ml", "ga", "cf", "gq", "world", "store", "tech", "space", "website"}
CODE_PREFIXES = ("android.", "java.", "javax.", "kotlin.", "androidx.", "org.", "com.",
                 "dalvik.", "libcore.", "sun.", "net.")


def sb(x):
    return x - 256 if x > 127 else x


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    c = Counter(data)
    n = len(data)
    return -sum(v / n * math.log2(v / n) for v in c.values())


# --------------------------------------------------------------------------
# String decoder detection / emulation
# --------------------------------------------------------------------------
PAYLOAD_HEX = re.compile(r"\\x([0-9a-fA-F]{2})")


def static_byte_arrays(cls):
    """Map static field name -> bytes, read from the class <clinit>."""
    out = {}
    for m in cls.get_methods():
        if m.is_external() or str(m.name) != "<clinit>":
            continue
        ins = list(m.get_method().get_instructions())
        sizes, reg_payload_idx, payloads = {}, {}, []
        for i in ins:
            if i.get_name() == "fill-array-data-payload":
                tail = i.get_output().split("|", 1)[-1]
                payloads.append(bytes(int(h, 16) for h in PAYLOAD_HEX.findall(tail)))
        k = 0
        for i in ins:
            nm, o = i.get_name(), i.get_output()
            mt = re.match(r"(v\d+), (-?\d+)$", o)
            if nm.startswith("const") and mt:
                sizes[mt.group(1)] = int(mt.group(2))
            elif nm == "fill-array-data":
                reg = o.split(",")[0].strip()
                reg_payload_idx[reg] = (k, sizes.get(reg))
                k += 1
            elif nm.startswith("sput-object"):
                mt = re.match(r"(v\d+), L[^;]+;->(\w+) \[B", o)
                if mt and mt.group(1) in reg_payload_idx:
                    idx, size = reg_payload_idx[mt.group(1)]
                    if idx < len(payloads):
                        data = payloads[idx]
                        out[mt.group(2)] = data[:size] if size else data
    return out


def detect_decoders(dx):
    """Find static (String)->String methods that base64-decode and XOR with a
    static key. Returns {(class, method): (keybytes, ops)}."""
    decoders = {}
    for cls in dx.get_classes():
        cname = str(cls.name)
        if cname.startswith(("Landroid", "Lkotlin", "Ljava", "Lokhttp", "Lorg/webrtc")):
            continue
        keys = None
        for m in cls.get_methods():
            if m.is_external():
                continue
            if "(Ljava/lang/String;)Ljava/lang/String;" not in str(m.get_method().get_descriptor()) \
                    and "(Ljava/lang/String;)Ljava/lang/String;" not in m.descriptor:
                continue
            ins = [(i.get_name(), i.get_output()) for i in m.get_method().get_instructions()]
            txt = " ".join(f"{a} {b}" for a, b in ins)
            if "aget-byte" not in txt or "xor-int/2addr" not in txt or "rem-int" not in txt:
                continue
            if "Base64;->decode" not in txt and "Method;->invoke" not in txt:
                continue
            if keys is None:
                keys = static_byte_arrays(cls)
            keyfield = None
            reg_field = {}
            ops, key_reg_dest = [], None
            for nm, o in ins:
                mt = re.match(r"(v\d+), L[^;]+;->(\w+) \[B", o)
                if nm.startswith("sget-object") and mt and mt.group(2) in keys:
                    reg_field[mt.group(1)] = mt.group(2)
                mt = re.match(r"(v\d+), (v\d+), (v\d+)$", o)
                if nm == "aget-byte" and mt and mt.group(2) in reg_field and key_reg_dest is None:
                    key_reg_dest = mt.group(1)
                    keyfield = reg_field[mt.group(2)]
                    continue
                if key_reg_dest and nm == "xor-int/2addr":
                    mt = re.match(r"(v\d+), (v\d+)$", o)
                    if mt and mt.group(2) == key_reg_dest:
                        break
                if key_reg_dest:
                    mt = re.match(r"(v\d+), (v\d+), (-?\d+)$", o)
                    if mt and mt.group(1) == key_reg_dest == mt.group(2) and nm in (
                            "add-int/lit8", "xor-int/lit8", "rsub-int/lit8",
                            "add-int/lit16", "xor-int/lit16", "rsub-int"):
                        ops.append((nm.split("/")[0], int(mt.group(3))))
            if keyfield and keys.get(keyfield):
                decoders[(cname, str(m.name))] = (keys[keyfield], ops)
    return decoders


def run_decoder(spec, s: str):
    key, ops = spec
    raw = bytearray(base64.b64decode(s + "=" * (-len(s) % 4)))
    n = len(key)
    for i in range(len(raw)):
        v = sb(key[i % n])
        for op, c in ops:
            if op == "add-int":
                v += c
            elif op == "xor-int":
                v ^= c
            elif op == "rsub-int":
                v = c - v
        raw[i] ^= v & 0xFF
    return raw.decode("utf-8", "replace")


CALL_RE = re.compile(r"(v\d+)[^L]*?(L[^;]+;)->(\w+)\(Ljava/lang/String;\)Ljava/lang/String;")


def decode_call_sites(dx, decoders):
    found = set()
    for cls in dx.get_classes():
        cname = str(cls.name)
        if "/bulk/" in cname:
            continue
        for m in cls.get_methods():
            if m.is_external():
                continue
            consts = {}
            for i in m.get_method().get_instructions():
                nm, o = i.get_name(), i.get_output()
                if nm == "const-string":
                    mt = re.match(r'(v\d+), "(.*)"$', o)
                    if mt:
                        consts[mt.group(1)] = mt.group(2)
                elif nm.startswith("invoke-static"):
                    mt = CALL_RE.search(o)
                    if mt and mt.group(1) in consts and (mt.group(2), mt.group(3)) in decoders:
                        try:
                            r = run_decoder(decoders[(mt.group(2), mt.group(3))], consts[mt.group(1)])
                        except Exception:
                            continue
                        found.add((cname, r))
    return sorted(found)


def plain_strings(dx):
    out = set()
    for cls in dx.get_classes():
        if str(cls.name).startswith(("Landroid", "Lkotlin", "Ljava", "Lokhttp")):
            continue
        for m in cls.get_methods():
            if m.is_external():
                continue
            for i in m.get_method().get_instructions():
                if i.get_name() == "const-string":
                    mt = re.match(r'v\d+, "(.*)"$', i.get_output())
                    if mt:
                        out.add(mt.group(1))
    return out


# --------------------------------------------------------------------------
# IOC extraction
# --------------------------------------------------------------------------
def benign(host):
    return any(host == b or host.endswith("." + b) for b in BENIGN_HOSTS)


def extract_iocs(strings):
    iocs = {"urls": set(), "hosts": set(), "ips": set(), "telegram_tokens": set(),
            "numeric_ids": set(), "key_like": set()}
    for s in strings:
        s = s.strip()
        for u in URL_RE.findall(s):
            host = re.sub(r"^https?://", "", u).split("/")[0].split(":")[0]
            if not benign(host):
                iocs["urls"].add(u)
        for t in TG_TOKEN_RE.findall(s):
            iocs["telegram_tokens"].add(t)
        for ip in IP_RE.findall(s):
            if all(0 <= int(p) <= 255 for p in ip.split(".")) and not ip.startswith(
                    ("0.", "127.", "255.", "2.5.4.", "1.2.", "10.", "192.168.", "172.16.")):
                iocs["ips"].add(ip)
        low = s.lower()
        if HOST_RE.match(low) and low.rsplit(".", 1)[-1] in COMMON_TLDS \
                and not low.startswith(CODE_PREFIXES) and not benign(low) \
                and low.rsplit(".", 1)[-1] not in {"xml", "png", "apk", "dex", "json", "txt", "mp3"}:
            iocs["hosts"].add(low)
        if NUM_ID_RE.match(s):
            iocs["numeric_ids"].add(s)
        if KEYLIKE_RE.match(s):
            iocs["key_like"].add(s)
    return {k: sorted(v) for k, v in iocs.items()}


# --------------------------------------------------------------------------
# Main analysis
# --------------------------------------------------------------------------
def analyze(path: Path, outdir: Path):
    data = path.read_bytes()
    rep = {"file": path.name, "size": len(data),
           "md5": hashlib.md5(data).hexdigest(),
           "sha1": hashlib.sha1(data).hexdigest(),
           "sha256": hashlib.sha256(data).hexdigest()}
    print(f"[+] analyzing {path.name} sha256={rep['sha256']}", file=sys.stderr)
    a, _d, dx = AnalyzeAPK(str(path))

    def safe(fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    rep["package"] = safe(a.get_package)
    rep["main_activity"] = safe(a.get_main_activity)
    perms = sorted(set(safe(a.get_permissions, [])))
    rep["permissions"] = perms
    rep["risky_permissions"] = {p: why for p in perms for k, why in RISKY_PERMS.items() if p.endswith(k)}
    rep["services"] = safe(a.get_services, [])
    rep["receivers"] = safe(a.get_receivers, [])
    rep["activities"] = safe(a.get_activities, [])

    certs = []
    for c in safe(a.get_certificates, []):
        certs.append({"subject": c.subject.human_friendly, "issuer": c.issuer.human_friendly,
                      "self_signed": c.subject.human_friendly == c.issuer.human_friendly,
                      "sha256": c.sha256_fingerprint.replace(" ", ""),
                      "not_before": str(c.not_valid_before), "not_after": str(c.not_valid_after)})
    rep["certificates"] = certs

    assets = []
    for name in safe(a.get_files, []):
        if name.startswith(("assets/", "res/raw/", "lib/")):
            blob = safe(lambda n=name: a.get_file(n), b"")
            if len(blob) > 64:
                e = entropy(blob)
                assets.append({"name": name, "size": len(blob), "entropy": round(e, 2),
                               "likely_encrypted": e > 7.5 and len(blob) > 1024})
    rep["assets_total"] = len(assets)
    rep["assets"] = sorted((x for x in assets if x["likely_encrypted"]),
                           key=lambda x: -x["size"])[:15]
    rep["assets_note"] = (f"{len(assets)} data files; showing up to 15 high-entropy ones "
                          "(many tiny ones are usually decoy padding)")

    api_hits = Counter()
    for cls in dx.get_classes():
        for m in cls.get_methods():
            if m.is_external():
                continue
            for i in m.get_method().get_instructions():
                o = i.get_output()
                for api in SUSPICIOUS_API:
                    if api in o:
                        api_hits[api] += 1
    rep["suspicious_api_usage"] = dict(api_hits)

    decoders = detect_decoders(dx)
    rep["string_decoders"] = [{"class": c, "method": m, "key_hex": spec[0].hex(),
                               "ops": spec[1]} for (c, m), spec in decoders.items()]
    decoded = decode_call_sites(dx, decoders)
    plain = plain_strings(dx)
    rep["decoded_strings_count"] = len(decoded)
    rep["decoded_strings"] = [{"class": c, "value": v} for c, v in decoded if v.isprintable() or "\n" in v]
    rep["iocs"] = extract_iocs(plain | {v for _, v in decoded})
    rep["iocs"]["from_decoded_only"] = sorted(
        set(extract_iocs({v for _, v in decoded})["hosts"]) - set(extract_iocs(plain)["hosts"]))
    rep["notes"] = []
    big = [x for x in assets if x["likely_encrypted"] and x["size"] > 50_000]
    if big:
        rep["notes"].append("Large high-entropy asset(s) "
                            + ", ".join(x["name"] for x in big)
                            + ": probably an encrypted second-stage payload.")
    if len(assets) > 40:
        rep["notes"].append(f"{len(assets)} data files in the APK: likely decoy padding "
                            "added by an obfuscator/builder.")
    if decoders:
        rep["notes"].append(f"{len(decoders)} string decoder(s) auto-emulated; "
                            f"{len(decoded)} strings recovered.")
    else:
        rep["notes"].append("No simple base64+XOR string decoder found; strings may use a "
                            "different scheme and need manual analysis.")
    if not certs or certs[0]["self_signed"]:
        rep["notes"].append("Self-signed / unknown signer (common for malware builders).")

    outdir.mkdir(parents=True, exist_ok=True)
    jpath = outdir / f"{path.stem}.json"
    jpath.write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    mpath = outdir / f"{path.stem}.md"
    mpath.write_text(markdown(rep))
    print(f"[+] wrote {jpath} and {mpath}", file=sys.stderr)
    print(markdown(rep))
    return rep


def markdown(r):
    L = [f"# APK report: {r['file']}", "",
         f"- SHA-256: `{r['sha256']}`", f"- MD5: `{r['md5']}`", f"- Size: {r['size']} bytes",
         f"- Package: `{r['package']}`", f"- Main activity: `{r['main_activity']}`", ""]
    L.append("## Signing certificate")
    for c in r["certificates"] or [{"subject": "none"}]:
        L.append(f"- {c.get('subject')} (self-signed: {c.get('self_signed')}) "
                 f"sha256 `{c.get('sha256','')}` valid {c.get('not_before','')} -> {c.get('not_after','')}")
    L += ["", "## IOCs"]
    for k, v in r["iocs"].items():
        if v:
            L.append(f"- **{k}**: " + ", ".join(f"`{x}`" for x in v[:40]))
    L += ["", "## Risky permissions"]
    L += [f"- `{p}`: {w}" for p, w in r["risky_permissions"].items()] or ["- none"]
    L += ["", "## Suspicious API usage (call count)"]
    L += [f"- `{k}`: {v}" for k, v in r["suspicious_api_usage"].items()] or ["- none"]
    L += ["", f"## Assets ({r.get('assets_note','')})"]
    L += [f"- `{a['name']}` {a['size']} B, entropy {a['entropy']}" +
          (" **ENCRYPTED?**" if a["likely_encrypted"] else "") for a in r["assets"]] or ["- none"]
    L += ["", "## Notes"] + [f"- {n}" for n in r["notes"]]
    L += ["", f"## String decoders found: {len(r['string_decoders'])}",
          f"Strings recovered: {r['decoded_strings_count']} (see JSON `decoded_strings`)", ""]
    return "\n".join(L)


def compare(paths):
    reps = [json.loads(Path(p).read_text()) for p in paths]
    print(f"# Comparison of {len(reps)} samples\n")
    def common(getter, title):
        sets = [set(getter(r)) for r in reps]
        inter = set.intersection(*sets) if sets else set()
        print(f"## {title}")
        for r, s in zip(reps, sets):
            print(f"- {r['file']}: {sorted(s)[:10]}")
        print(f"**shared by all:** {sorted(inter) if inter else 'none'}\n")
    common(lambda r: [c["sha256"] for c in r["certificates"]], "Signing certificate SHA-256")
    common(lambda r: r["iocs"]["hosts"], "Hosts / domains")
    common(lambda r: r["iocs"]["numeric_ids"], "Numeric IDs (Telegram chat IDs?)")
    common(lambda r: r["iocs"]["telegram_tokens"], "Telegram bot tokens")
    common(lambda r: r["iocs"]["key_like"], "Key-like strings (AES key / IV)")
    common(lambda r: r["iocs"]["ips"], "IP addresses")
    common(lambda r: [r["package"]], "Package name")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze")
    a.add_argument("apk", type=Path)
    a.add_argument("-o", "--out", type=Path, default=Path("reports"))
    c = sub.add_parser("compare")
    c.add_argument("json", nargs="+")
    args = ap.parse_args()
    if args.cmd == "analyze":
        analyze(args.apk, args.out)
    else:
        compare(args.json)


if __name__ == "__main__":
    main()
