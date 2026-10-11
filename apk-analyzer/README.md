# apk-analyzer

Static triage of suspicious Android APKs (e.g. fake "video" files spread via
Telegram) to extract indicators of compromise (IOCs) for incident reports
(CERT.UZ, Telegram, registrars).

**The tool never installs or runs the APK and never contacts any host found in it.**

## Setup

    pip install -r requirements.txt

## Use

    # analyze one sample -> reports/<name>.json + reports/<name>.md
    python3 analyze_apk.py analyze path/to/sample.apk -o reports

    # find what several samples have in common (same actor / builder?)
    python3 analyze_apk.py compare reports/a.json reports/b.json

## What you get

- hashes, package, signing certificate (builders often reuse one certificate)
- permissions flagged as risky, use of VPN / PackageInstaller / crypto APIs
- high-entropy assets (encrypted second-stage payloads)
- automatic detection and emulation of the common "base64 + rolling XOR"
  string decoders that obfuscators insert; all call sites are decoded
- IOCs from plain and decoded strings: domains, URLs, IPs, Telegram bot tokens,
  numeric IDs (Telegram chat IDs), hex key/IV candidates

## Limits

- Decoder keys differ per build, so they are re-detected for every sample.
- Only simple add/xor/rsub decoders are emulated. Other schemes (AES-wrapped
  strings, native code, custom loaders) need manual analysis; the report says so.
- Encrypted payload assets are not decrypted automatically.
- Review the output: heuristic matches can be false positives.

## Handling samples safely

Never install a sample on a phone. Keep samples outside git (`*.apk` is ignored
here), store them zipped, and report indicators through official channels
rather than contacting the operators.
