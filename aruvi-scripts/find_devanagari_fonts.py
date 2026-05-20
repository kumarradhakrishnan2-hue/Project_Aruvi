"""Run this on the Mac to find available Devanagari-capable fonts."""
import os, glob

candidates = [
    # macOS system fonts
    "/System/Library/Fonts/Supplemental/Kohinoor Devanagari.ttc",
    "/System/Library/Fonts/KohinoorDevanagari.ttc",
    "/System/Library/Fonts/Supplemental/ITF Devanagari.ttf",
    "/System/Library/Fonts/Supplemental/ITFDevanagari.ttf",
    # Homebrew / user installed Noto
    "/Library/Fonts/NotoSansDevanagari-Regular.ttf",
    os.path.expanduser("~/Library/Fonts/NotoSansDevanagari-Regular.ttf"),
    # Linux
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansDevanagari-Regular.ttf",
]

print("=== Devanagari font search ===")
for p in candidates:
    print(f"{'FOUND' if os.path.exists(p) else '  ---'}  {p}")

# Also glob for any Kohinoor / Noto / Devanagari font
print("\n=== Glob search ===")
for pattern in [
    "/System/Library/Fonts/**/*Kohinoor*",
    "/System/Library/Fonts/**/*Devanagari*",
    "/Library/Fonts/*Noto*Devanagari*",
    os.path.expanduser("~/Library/Fonts/*Devanagari*"),
]:
    for f in glob.glob(pattern, recursive=True):
        print(f"  {f}")
