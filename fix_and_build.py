"""
Run this instead of pygbag:
  python fix_and_build.py

It patches pygbag to read UTF-8, then builds the game.
"""
import sys, os, re, subprocess, shutil

# ── Step 1: Find pygbag's app.py and patch the broken open() call ──────────────
import pygbag
pygbag_dir = os.path.dirname(pygbag.__file__)
app_py = os.path.join(pygbag_dir, "app.py")

print(f"Found pygbag at: {pygbag_dir}")

with open(app_py, "r", encoding="utf-8") as f:
    src = f.read()

# The broken line is:  src_code = f.read()
# inside a block that opens the file without encoding=
# We patch the open() call that reads main.py to force utf-8
old = 'src_code = f.read()'
new = 'src_code = f.read() if hasattr(f, "mode") and "b" in f.mode else f.read()'

# More targeted: find the with open(...mainscript...) block and add encoding
patched = re.sub(
    r'(with open\([^)]*mainscript[^)]*\))',
    lambda m: m.group(0) if 'encoding' in m.group(0) 
              else m.group(0).rstrip(')') + ', encoding="utf-8")',
    src
)

if patched == src:
    # Try alternate pattern - open with just the path variable
    patched = src.replace(
        'async with aopen(mainscript) as f:',
        'async with aopen(mainscript, encoding="utf-8") as f:'
    ).replace(
        'with open(mainscript) as f:',
        'with open(mainscript, encoding="utf-8") as f:'
    )

if patched != src:
    # Back up original
    backup = app_py + ".backup"
    if not os.path.exists(backup):
        shutil.copy(app_py, backup)
        print("Backed up original app.py")
    with open(app_py, "w", encoding="utf-8") as f:
        f.write(patched)
    print("Patched pygbag to use UTF-8!")
else:
    print("WARNING: Could not auto-patch pygbag. Trying manual fix...")
    # Show the relevant lines so we can fix manually
    for i, line in enumerate(src.splitlines()):
        if 'f.read()' in line or 'mainscript' in line.lower():
            print(f"  Line {i+1}: {line.rstrip()}")

# ── Step 2: Make sure main.py exists with utf-8 encoding ──────────────────────
print("\nCreating main.py...")
with open("spill.py", "rb") as f:
    raw = f.read()

# Decode as utf-8 then re-encode cleanly
try:
    text = raw.decode("utf-8")
except UnicodeDecodeError:
    text = raw.decode("latin-1")

# Remove any existing coding declaration and add fresh one
lines = text.splitlines()
if lines and 'coding' in lines[0]:
    lines = lines[1:]
text = "# -*- coding: utf-8 -*-\n" + "\n".join(lines)

with open("main.py", "w", encoding="utf-8") as f:
    f.write(text)
print("main.py created with UTF-8 encoding")

# ── Step 3: Run pygbag build ───────────────────────────────────────────────────
print("\nRunning pygbag build...")
result = subprocess.run([sys.executable, "-m", "pygbag", "--build", "main.py"])

if result.returncode != 0:
    print("\nBuild failed. Trying to show the relevant pygbag source...")
    for i, line in enumerate(open(app_py, encoding="utf-8").splitlines()):
        if 'f.read()' in line:
            print(f"  Line {i+1}: {line.rstrip()}")
    sys.exit(1)

# ── Step 4: Copy output ────────────────────────────────────────────────────────
print("\nCopying game files to server...")
dest = os.path.join("final_server", "static", "game")
os.makedirs(dest, exist_ok=True)

candidates = ["build/web", "main/build/web", "build\\web", "main\\build\\web"]
copied = False
for c in candidates:
    if os.path.exists(os.path.join(c, "index.html")):
        print(f"Found build at: {c}")
        for root, dirs, files in os.walk(c):
            for file in files:
                src_path = os.path.join(root, file)
                rel = os.path.relpath(src_path, c)
                dst_path = os.path.join(dest, rel)
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy2(src_path, dst_path)
        print(f"Copied to {dest}")
        copied = True
        break

if not copied:
    # Walk everything looking for index.html in a web folder
    for root, dirs, files in os.walk("."):
        if "index.html" in files and "web" in root:
            print(f"Found build at: {root}")
            for file in files:
                src_path = os.path.join(root, file)
                rel = os.path.relpath(src_path, root)
                dst_path = os.path.join(dest, rel)
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy2(src_path, dst_path)
            copied = True
            break

if copied:
    print("\n✓ SUCCESS!")
    print(f"Files in {dest}:")
    for f in os.listdir(dest):
        print(f"  {f}")
    print("\nNow restart app.py and go to /game")
else:
    print("\nERROR: Could not find build output. Check errors above.")

input("\nPress Enter to close...")
