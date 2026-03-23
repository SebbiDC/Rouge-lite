"""
Run this AFTER make_async.py to build and copy the game files.
Usage: python build_after_patch.py
"""
import os, sys, shutil, subprocess

print("="*50)
print("  HORDE SURVIVOR - Build & Deploy")
print("="*50)

if not os.path.exists("main.py"):
    print("ERROR: main.py not found. Run make_async.py first!")
    input("Press Enter to exit..."); sys.exit(1)

if not os.path.exists("final_server/app.py"):
    print("ERROR: final_server/app.py not found")
    input("Press Enter to exit..."); sys.exit(1)

# Step 1: Build with pygbag
print("\n[1/2] Running pygbag build (takes 1-2 minutes)...")
print("      A browser window may open - just ignore it\n")
result = subprocess.run([sys.executable, "-m", "pygbag", "--build", "main.py"])
print(f"\n      Build finished (exit code: {result.returncode})")

if result.returncode != 0:
    print("\nERROR: pygbag build failed.")
    print("Make sure pygbag is installed:  pip install pygbag")
    input("Press Enter to exit..."); sys.exit(1)

# Step 2: Find output and copy
print("\n[2/2] Looking for build output...")
dest = os.path.join("final_server", "static", "game")
os.makedirs(dest, exist_ok=True)

found = False
for root, dirs, files in os.walk("."):
    if "final_server" in root:
        continue
    if "index.html" in files:
        has_wasm = any(f.endswith('.wasm') or f.endswith('.js') or f.endswith('.tar.gz') for f in files)
        if has_wasm or "web" in root or "build" in root:
            print(f"      Found build output at: {root}")
            count = 0
            for fname in files:
                src = os.path.join(root, fname)
                dst = os.path.join(dest, fname)
                shutil.copy2(src, dst)
                count += 1
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
    print("\nBuild output not found!")
    print("Try manually copying build/web/* to final_server/static/game/")
    input("\nPress Enter to exit..."); sys.exit(1)

# Step 3: Remove pycache from the copied files
pycache = os.path.join(dest, "__pycache__")
if os.path.exists(pycache):
    shutil.rmtree(pycache)
    print("      Removed __pycache__")

print("\n" + "="*50)
print("  SUCCESS!")
print("="*50)
print(f"\nFiles in {dest}:")
for f in os.listdir(dest):
    size = os.path.getsize(os.path.join(dest, f))
    print(f"  {f}  ({size//1024}KB)")
print("\nNEXT STEPS:")
print("  1. Stop app.py (press Ctrl+C in its window)")
print("  2. Run:  python final_server/app.py")
print("  3. Open: http://localhost:5000/game")
input("\nPress Enter to exit...")
