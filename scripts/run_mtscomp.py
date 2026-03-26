"""
run_mtscomp.py
--------------
Run from anywhere. You will be prompted to enter the path to the
directory containing mxxxsxxrx_gx session folders.

Expected folder structure:
    <base_dir>/
        m1096s18r1_g0/
            m1096s18r1_g0_imec0/
                m1096s18r1_g0_t0.imec0.ap.bin   <- compressed by this script
                m1096s18r1_g0_t0.imec0.ap.meta  ]
                m1096s18r1_g0_t0.imec0.lf.bin   ]  copied to Y drive
                m1096s18r1_g0_t0.imec0.lf.meta  ]

Output files produced by mtscomp:
    m1096s18r1_g0_t0.imec0.ap.cbin
    m1096s18r1_g0_t0.imec0.ap.ch

Usage:
    python run_mtscomp.py

Requirements:
    pip install mtscomp

2026-03-24: Jongwon
- Initial version of the script. Uses mtscomp Python API to compress ap.bin files
  and copies the original .ap.meta, .lf.bin, .lf.meta files to Y drive.
- Checks for sufficient disk space before compression and logs all actions to a log file.
- Output .ap.cbin and .ap.ch files are saved in the base_dir.
- Compression is skipped if output files already exist, and sessions with missing
  imec0 folder or ap.bin file are also skipped with a warning.


"""

import os
import re
import sys
import glob
import shutil
import datetime
import platform

try:
    import mtscomp as _mtscomp
except ImportError:
    print("  [ERROR] mtscomp package is not installed.")
    print("          Run: pip install mtscomp")
    sys.exit(1)

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
# Destination root: Windows uses Y drive, Linux uses /mnt/y mount point
if platform.system() == "Windows":
    DEST_ROOT = r"Y:\NeuRLab\Data"
else:
    DEST_ROOT = "/mnt/Y/NeuRLab/Data"

FREE_RATIO   = 0.80                 # Required free space ratio vs ap.bin size
LOG_FILENAME = "mtscomp_log.txt"

# mtscomp parameters (Neuropixels defaults)
N_CHANNELS  = 385
SAMPLE_RATE = 30000
DTYPE       = "int16"

# File suffixes to copy after compression (relative to the ap.bin prefix)
# e.g. prefix = "m1096s18r1_g0_t0.imec0"
# -> copies prefix.ap.meta, prefix.lf.bin, prefix.lf.meta
COPY_SUFFIXES = ["ap.meta", "lf.bin", "lf.meta"]


# ──────────────────────────────────────────────
# Disk space warning (printed when space is insufficient)
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


# ──────────────────────────────────────────────
# Check if free disk space >= required bytes * FREE_RATIO
# Returns (ok, needed_gb, free_gb)
# ──────────────────────────────────────────────
def has_enough_space(path: str, required_bytes: int) -> tuple[bool, float, float]:
    _, _, free = shutil.disk_usage(path)
    needed = required_bytes * FREE_RATIO
    return (free >= needed), needed / 1e9, free / 1e9


# ──────────────────────────────────────────────
# Extract mouse ID from session folder name
# e.g. "m1096s18r1_g0" -> "m1096"
# ──────────────────────────────────────────────
def extract_mid(session_name: str) -> str:
    # e.g. "m1096s18r1_g0" -> "1096"  (no leading 'm')
    m = re.match(r"m(\d+)", session_name, re.IGNORECASE)
    return m.group(1) if m else session_name.split("s")[0]


# ──────────────────────────────────────────────
# Find the ap.bin file inside imec_dir
# Filename pattern: {anything}.ap.bin
# Returns the full path, or None if not found
# ──────────────────────────────────────────────
def find_ap_bin(imec_dir: str) -> str | None:
    matches = glob.glob(os.path.join(imec_dir, "*.ap.bin"))
    if not matches:
        return None
    if len(matches) > 1:
        print(f"  [WARN] Multiple ap.bin files found, using: {os.path.basename(matches[0])}")
    return matches[0]


# ──────────────────────────────────────────────
# Append a timestamped message to the log file
# ──────────────────────────────────────────────
def write_log(log_path: str, message: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(f"  [LOG] {message}")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    print(f"\n{'='*65}")
    print(f"  mtscomp automation script")
    print(f"  Parameters: n={N_CHANNELS}, s={SAMPLE_RATE}, d={DTYPE}")
    print(f"{'='*65}\n")

    # Prompt user for the directory containing session folders
    raw = input("  Enter path to session directory: ").strip().strip('"').strip("'")
    base_dir = os.path.abspath(raw)

    if not os.path.isdir(base_dir):
        print(f"\n  [ERROR] Directory not found: {base_dir}")
        sys.exit(1)

    print(f"  Session directory: {base_dir}\n")
    log_path = os.path.join(base_dir, LOG_FILENAME)

    # Collect all mxxxsxxrx_gx session folders (sorted alphabetically)
    session_pattern = re.compile(r"^m\d+s\d+r\d+_g\d+$", re.IGNORECASE)
    sessions = sorted(
        [d for d in os.listdir(base_dir)
         if os.path.isdir(os.path.join(base_dir, d)) and session_pattern.match(d)]
    )

    if not sessions:
        print("  No session folders matching mxxxsxxrx_gx pattern found.")
        print("  Make sure you're running this script from the correct directory.")
        sys.exit(1)

    print(f"  Found {len(sessions)} session folder(s):\n  " + "\n  ".join(sessions) + "\n")

    for session in sessions:
        print(f"\n{'─'*65}")
        print(f"  Processing: {session}")

        session_dir = os.path.join(base_dir, session)
        imec_dir    = os.path.join(session_dir, f"{session}_imec0")

        # Check imec0 folder exists
        if not os.path.isdir(imec_dir):
            msg = f"{session}: imec0 folder not found ({imec_dir})"
            print(f"  [SKIP] {msg}")
            write_log(log_path, msg)
            continue

        # Find ap.bin (e.g. m1096s18r1_g0_t0.imec0.ap.bin)
        ap_bin = find_ap_bin(imec_dir)
        if ap_bin is None:
            msg = f"{session}: no *.ap.bin file found in {imec_dir} — skipping mtscomp"
            print(f"  [SKIP] {msg}")
            write_log(log_path, msg)
            continue

        print(f"  Found: {os.path.basename(ap_bin)}")

        # Derive shared prefix (e.g. "m1096s18r1_g0_t0.imec0")
        # by stripping ".ap.bin" from the filename
        prefix = os.path.basename(ap_bin)[:-len(".ap.bin")]  # "m1096s18r1_g0_t0.imec0"

        ap_size = os.path.getsize(ap_bin)

        # Check available disk space before starting compression
        ok, needed_gb, free_gb = has_enough_space(base_dir, ap_size)
        if not ok:
            warn_disk_full(base_dir, needed_gb, free_gb)
            msg = (f"{session}: insufficient disk space "
                   f"(needed {needed_gb:.2f} GB, free {free_gb:.2f} GB) — aborted")
            write_log(log_path, msg)
            print("\n  Script terminated due to insufficient disk space.")
            sys.exit(1)

        print(f"  Disk space OK  (needed {needed_gb:.2f} GB / free {free_gb:.2f} GB)")

        # Skip if already compressed (both .ap.cbin and .ap.ch exist)
        # Output files are placed in base_dir (same level as mxxxsxxrx_gx folders)
        ap_cbin = os.path.join(base_dir, f"{prefix}.ap.cbin")
        ap_ch   = os.path.join(base_dir, f"{prefix}.ap.ch")
        if os.path.isfile(ap_cbin) and os.path.isfile(ap_ch):
            print(f"  [SKIP] Already compressed ({prefix}.ap.cbin + .ap.ch exist)")
            write_log(log_path, f"{session}: already compressed — skipping mtscomp")
            continue

        # Run mtscomp via Python API
        # Output: prefix.ap.cbin, prefix.ap.ch
        print(f"  Starting mtscomp ...")
        try:
            writer = _mtscomp.Writer()
            writer.open(
                ap_bin,
                sample_rate=SAMPLE_RATE,
                n_channels=N_CHANNELS,
                dtype=DTYPE,
            )
            writer.write(ap_cbin, ap_ch)
            writer.close()
        except Exception as exc:
            msg = f"{session}: mtscomp failed — {exc}"
            print(f"  [ERROR] {msg}")
            write_log(log_path, msg)
            continue

        # Verify output files were actually created
        if not (os.path.isfile(ap_cbin) and os.path.isfile(ap_ch)):
            msg = (f"{session}: mtscomp exited but {prefix}.ap.cbin / .ap.ch not found "
                   "— compression may not have completed properly")
            print(f"  [ERROR] {msg}")
            write_log(log_path, msg)
            continue

        print(f"  [OK] mtscomp complete -> {prefix}.ap.cbin")

        # Copy files to Y drive (NeuRLab NAS)
        # Destination: Y:\NeuRLab\Data\{mid}\np\{session}\{session}_imec0\
        mid      = extract_mid(session)
        dest_dir = os.path.join(DEST_ROOT, mid, "np", session, f"{session}_imec0")
        try:
            os.makedirs(dest_dir, exist_ok=True)
            print(f"  Copying to: {dest_dir}")

            for suffix in COPY_SUFFIXES:
                fname = f"{prefix}.{suffix}"      # e.g. m1096s18r1_g0_t0.imec0.ap.meta
                src   = os.path.join(imec_dir, fname)
                dst   = os.path.join(dest_dir, fname)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                    print(f"    Copied: {fname}")
                else:
                    msg = f"{session}: file not found for copy — {fname}"
                    print(f"    [WARN] {msg}")
                    write_log(log_path, msg)

            write_log(log_path, f"{session}: mtscomp and file copy completed successfully")

        except PermissionError as e:
            msg = f"{session}: permission denied while copying to Y drive — {e}"
            print(f"  [ERROR] {msg}")
            print(f"  [!!] Please manually copy the following files to:")
            print(f"       {dest_dir}")
            for suffix in COPY_SUFFIXES:
                print(f"         - {prefix}.{suffix}")
            write_log(log_path, msg)
            write_log(log_path, f"{session}: MANUAL COPY REQUIRED -> {dest_dir}")

        except Exception as e:
            msg = f"{session}: unexpected error while copying to Y drive — {e}"
            print(f"  [ERROR] {msg}")
            print(f"  [!!] Please manually copy the following files to:")
            print(f"       {dest_dir}")
            for suffix in COPY_SUFFIXES:
                print(f"         - {prefix}.{suffix}")
            write_log(log_path, msg)
            write_log(log_path, f"{session}: MANUAL COPY REQUIRED -> {dest_dir}")

    print(f"\n{'='*65}")
    print(f"  All sessions processed.")
    print(f"  Log file: {log_path}")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
