"""
move_cbin.py  (one-time use)
----------------------------
Moves *.ap.cbin and *.ap.ch files from inside each
mxxxsxxrx_gx / mxxxsxxrx_gx_imec0 folder up to base_dir.

Usage:
    python move_cbin.py
"""

import os
import re
import sys
import shutil

def main():
    raw = input("  Enter path to session directory: ").strip().strip('"').strip("'")
    base_dir = os.path.abspath(raw)

    if not os.path.isdir(base_dir):
        print(f"  [ERROR] Directory not found: {base_dir}")
        sys.exit(1)

    session_pattern = re.compile(r"^m\d+s\d+r\d+_g\d+$", re.IGNORECASE)
    sessions = sorted(
        [d for d in os.listdir(base_dir)
         if os.path.isdir(os.path.join(base_dir, d)) and session_pattern.match(d)]
    )

    if not sessions:
        print("  No mxxxsxxrx_gx session folders found.")
        sys.exit(1)

    moved, skipped = 0, 0

    for session in sessions:
        imec_dir = os.path.join(base_dir, session, f"{session}_imec0")
        if not os.path.isdir(imec_dir):
            continue

        for fname in os.listdir(imec_dir):
            if fname.endswith(".ap.cbin") or fname.endswith(".ap.ch"):
                src = os.path.join(imec_dir, fname)
                dst = os.path.join(base_dir, fname)
                if os.path.isfile(dst):
                    print(f"  [SKIP] Already exists in base_dir: {fname}")
                    skipped += 1
                else:
                    shutil.move(src, dst)
                    print(f"  [MOVED] {session}_imec0/{fname}  ->  base_dir/")
                    moved += 1

    print(f"\n  Done. Moved: {moved}, Skipped (already exists): {skipped}")

if __name__ == "__main__":
    main()
