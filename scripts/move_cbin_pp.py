"""
move_cbin_tmp.py  (modified for specific folder structure)
------------------------------------------------------
Moves *.ap.cbin and *.ch files from inside each
mxxxsxxrx_gx/raw_ephys_data/probe00 folder to a 'compressed' folder.

Usage:
    python move_cbin_tmp.py
"""

import os
import re
import sys
import shutil

def main():
    raw = input("  Enter path to base directory (e.g., C:\\Users\\NeuRLab\\Done): ").strip().strip('"').strip("'")
    base_dir = os.path.abspath(raw)

    if not os.path.isdir(base_dir):
        print(f"  [ERROR] Directory not found: {base_dir}")
        sys.exit(1)

    # 1. 목적지 폴더(compressed) 설정 및 없으면 생성
    dest_dir = os.path.join(base_dir, "compressed")
    os.makedirs(dest_dir, exist_ok=True)

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
        # 2. 탐색할 실제 폴더 경로로 수정 (raw_ephys_data/probe00)
        probe_dir = os.path.join(base_dir, session, "raw_ephys_data", "probe00")
        
        if not os.path.isdir(probe_dir):
            print(f"  [SKIP] Directory not found: {session}/raw_ephys_data/probe00")
            continue

        for fname in os.listdir(probe_dir):
            # 3. .ap.cbin 또는 .ch 파일 확인
            if fname.endswith(".ap.cbin") or fname.endswith(".ch"):
                src = os.path.join(probe_dir, fname)
                dst = os.path.join(dest_dir, fname)
                
                if os.path.isfile(dst):
                    print(f"  [SKIP] Already exists in compressed: {fname}")
                    skipped += 1
                else:
                    shutil.move(src, dst)
                    # 출력 메시지도 경로에 맞게 수정
                    print(f"  [MOVED] {session}/.../{fname}  ->  compressed/")
                    moved += 1

    print(f"\n  Done. Moved: {moved}, Skipped (already exists): {skipped}")

if __name__ == "__main__":
    main()