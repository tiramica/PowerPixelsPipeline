"""
check_io.py
-----------
Tests sequential read of a large binary file to detect I/O errors.
Equivalent to the PowerShell read test.

Usage:
    python check_io.py
"""

import sys

BUFFER_SIZE = 1024 * 1024 * 1024  # 1 GB

file_path = input("Enter file path: ").strip().strip('"').strip("'")

total_read = 0
try:
    with open(file_path, "rb") as f:
        while True:
            buffer = f.read(BUFFER_SIZE)
            if not buffer:
                break
            total_read += len(buffer)
            print(f"  Read: {total_read / 1e9:.2f} GB")

    print(f"\n  Done! Total read: {total_read / 1e9:.2f} GB")

except OSError as e:
    print(f"\n  I/O error at: {total_read / 1e9:.2f} GB")
    print(f"  Error: {e}")
    sys.exit(1)
