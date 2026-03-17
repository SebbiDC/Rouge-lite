"""
Run this AFTER patch_pygbag.py to build and copy the game files.
Usage: python build_after_patch.py
"""
import os, sys, shutil, subprocess

print("="*50)
print("  HORDE SURVIVOR - Build & Deploy")
print("="*50)

# Check we're in the right folder
if not os.path.exists("spill.py"):
    print("ERROR: Run this from the 'Rouge lite' folder (where spill.py is)")
    input("Press Enter to exit...")
    sys.exit(1)

if not os.path.exists("final_server/app.py"):
    print("ERROR: final_server/app.py not found")
    input("Press Enter to exit...")
    sys.exit(1)

# Step 1: Create clean main.py
print("\n[1/3] Creating main.py...")
with open("spill.py", "rb") as f:
    raw = f.read()
try:
    text = raw.decode("utf-8")
except:
    text = raw.decode("latin-1")
with open("main.py", "w", encoding="utf-8") as f:
    f.write(text)
print("      main.py created OK")

# Step 2: Build
print("\n[2/3] Running pygbag build (takes 1-2 minutes)...")
print("      A browser window may open - just ignore it\n")
result = subprocess.run([sys.executable, "-m", "pygbag", "--build", "main.py"])
print(f"\n      Build finished (exit code: {result.returncode})")

# Step 3: Find output and copy
print("\n[3/3] Looking for build output...")
dest = os.path.join("final_server", "static", "game")
os.makedirs(dest, exist_ok=True)

found = False
# Search everywhere for index.html in a web-related folder
for root, dirs, files in os.walk("."):
    # Skip the destination itself
    if "final_server" in root:
        continue
    if "index.html" in files:
        # Check it's actually a pygbag output (has .wasm or .js files)
        has_wasm = any(f.endswith('.wasm') or f.endswith('.js') for f in files)
        if has_wasm or "web" in root or "build" in root:
            print(f"      Found build output at: {root}")
            # Copy all files
            count = 0
            for fname in files:
                src = os.path.join(root, fname)
                dst = os.path.join(dest, fname)
                shutil.copy2(src, dst)
                count += 1
            # Copy subdirectories too
            for subdir in dirs:
                src_sub = os.path.join(root, subdir)
                dst_sub = os.path.join(dest, subdir)
                if os.path.exists(dst_sub):
                    shutil.rmtree(dst_sub)
                shutil.copytree(src_sub, dst_sub)
            print(f"      Copied {count} files to {dest}")
            found = True
            break

if not found:
    print("\n  Build output not found!")
    print("  Contents of current directory:")
    for item in os.listdir("."):
        print(f"    {item}")
    print("\n  If you see a 'build' folder, run this command manually:")
    print("  xcopy /E /Y /I build\\web\\* final_server\\static\\game\\")
    input("\nPress Enter to exit...")
    sys.exit(1)

print("\n" + "="*50)
print("  SUCCESS!")
print("="*50)
print(f"\nFiles in {dest}:")
for f in os.listdir(dest):
    print(f"  {f}")
print("\nNEXT STEPS:")
print("  1. Stop app.py (press Ctrl+C in its window)")
print("  2. Run:  python final_server\\app.py")
print("  3. Open: http://localhost:5000/game")
input("\nPress Enter to exit...")