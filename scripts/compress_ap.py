"""
compress_ap.py
--------------
Compresses all *.ap.bin files found directly in the given base_dir.
Skips files that already have corresponding .ap.cbin and .ap.ch.

Expected input:
    <base_dir>/
        m1096s18r1_g0_t0.imec0.ap.bin
        m1097s01r1_g0_t0.imec0.ap.bin
        ...

Output (in base_dir):
    m1096s18r1_g0_t0.imec0.ap.cbin
    m1096s18r1_g0_t0.imec0.ap.ch
    ...

Usage:
    python compress_ap.py

Requirements:
    pip install mtscomp

Jongwon 03/24/2026
- Initial version of the script. Uses mtscomp Python API to compress ap.bin files.
"""

import os
import sys
import glob
import shutil
import datetime

try:
    import mtscomp as _mtscomp
except ImportError:
    print("  [ERROR] mtscomp package is not installed.")
    print("          Run: pip install mtscomp")
    sys.exit(1)

# ──────────────────────────────────────────────
# Configuration — mtscomp parameters (Neuropixels defaults)
# ──────────────────────────────────────────────
N_CHANNELS   = 385
SAMPLE_RATE  = 30000
DTYPE        = "int16"
FREE_RATIO   = 0.80   # Required free space ratio vs ap.bin size
LOG_FILENAME = "mtscomp_log.txt"


# ──────────────────────────────────────────────
# Append a timestamped message to the log file
# ──────────────────────────────────────────────
def write_log(log_path: str, message: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(f"  [LOG] {message}")


# ──────────────────────────────────────────────
# Disk space warning
# ──────────────────────────────────────────────
def warn_disk_full(path: str, required_gb: float, free_gb: float):
    lines = [
        "=" * 65,
        "  ██████  DISK SPACE CRITICALLY LOW!  ██████",
        "=" * 65,
        f"  Path          : {path}",
        f"  Required space: {required_gb:.2f} GB  (80% of ap.bin size)",
        f"  Free space    : {free_gb:.2f} GB",
        "-" * 65,
        "  [!] Compression may CORRUPT DATA if disk fills up mid-write!",
        "  [!] Delete or move unnecessary files to free up space.",
        "  [!] Re-run this script after securing enough free space.",
        "=" * 65,
    ]
    for line in lines:
        print(line)


def main():
    print(f"\n{'='*65}")
    print(f"  compress_ap  —  batch ap.bin compressor")
    print(f"  Parameters: n={N_CHANNELS}, s={SAMPLE_RATE}, d={DTYPE}")
    print(f"{'='*65}\n")

    # Prompt for directory containing ap.bin files
    raw = input("  Enter path to directory containing ap.bin file(s): ").strip().strip('"').strip("'")
    base_dir = os.path.abspath(raw)

    if not os.path.isdir(base_dir):
        print(f"\n  [ERROR] Directory not found: {base_dir}")
        sys.exit(1)

    log_path = os.path.join(base_dir, LOG_FILENAME)

    # Find all *.ap.bin files (sorted)
    ap_bins = sorted(glob.glob(os.path.join(base_dir, "*.ap.bin")))
    if not ap_bins:
        print(f"  [ERROR] No *.ap.bin files found in: {base_dir}")
        sys.exit(1)

    print(f"  Found {len(ap_bins)} ap.bin file(s):\n  " + "\n  ".join(os.path.basename(f) for f in ap_bins) + "\n")

    for ap_bin in ap_bins:
        prefix  = os.path.basename(ap_bin)[:-len(".ap.bin")]
        ap_cbin = os.path.join(base_dir, f"{prefix}.ap.cbin")
        ap_ch   = os.path.join(base_dir, f"{prefix}.ap.ch")

        print(f"\n{'─'*65}")
        print(f"  Processing: {os.path.basename(ap_bin)}")

        # Skip if already compressed
        if os.path.isfile(ap_cbin) and os.path.isfile(ap_ch):
            print(f"  [SKIP] Already compressed — .ap.cbin and .ap.ch exist")
            write_log(log_path, f"{prefix}: already compressed — skipping")
            continue

        # Check disk space
        ap_size = os.path.getsize(ap_bin)
        _, _, free = shutil.disk_usage(base_dir)
        needed = ap_size * FREE_RATIO
        if free < needed:
            warn_disk_full(base_dir, needed / 1e9, free / 1e9)
            write_log(log_path, f"{prefix}: insufficient disk space (needed {needed/1e9:.2f} GB, free {free/1e9:.2f} GB) — aborted")
            print("\n  Script terminated due to insufficient disk space.")
            sys.exit(1)

        print(f"  Disk space OK  (needed {needed/1e9:.2f} GB / free {free/1e9:.2f} GB)")
        print(f"  Starting mtscomp ...")

        # Run mtscomp
        try:
            writer = _mtscomp.Writer()
            writer.open(ap_bin, sample_rate=SAMPLE_RATE, n_channels=N_CHANNELS, dtype=DTYPE)
            writer.write(ap_cbin, ap_ch)
            writer.close()
        except Exception as exc:
            msg = f"{prefix}: mtscomp failed — {exc}"
            print(f"  [ERROR] {msg}")
            write_log(log_path, msg)
            continue

        # Verify output
        if not (os.path.isfile(ap_cbin) and os.path.isfile(ap_ch)):
            msg = f"{prefix}: mtscomp exited but output files not found — compression may not have completed properly"
            print(f"  [ERROR] {msg}")
            write_log(log_path, msg)
            continue

        write_log(log_path, f"{prefix}: mtscomp completed successfully")
        print(f"  [OK] Done — {prefix}.ap.cbin")

    print(f"\n{'='*65}")
    print(f"  All files processed.")
    print(f"  Log file: {log_path}")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
