"""
Makes spill.py compatible with pygbag (browser WebAssembly).
Run: python make_async.py
Then: python build_after_patch.py
"""
import os, re, py_compile

if not os.path.exists("spill.py"):
    print("ERROR: Run from the Rouge lite folder (where spill.py is)")
    input("Press Enter..."); exit(1)

with open("spill.py", "rb") as f:
    raw = f.read()
try:
    text = raw.decode("utf-8")
except:
    text = raw.decode("latin-1")
text = text.replace("\r\n", "\n").replace("\r", "\n")

ASYNC_FUNCS = ["index_screen","card_log_screen","meta_upgrade_screen",
               "weapon_select_screen","death_screen","game_loop","title_screen"]

# Make defs async
for fn in ASYNC_FUNCS:
    text = text.replace(f"def {fn}(", f"async def {fn}(")
    print(f"  async def {fn}")

# Add await asyncio.sleep(0) after every display.flip()
lines = text.splitlines()
new_lines = []
for line in lines:
    new_lines.append(line)
    if "pygame.display.flip()" in line:
        indent = len(line) - len(line.lstrip())
        new_lines.append(" " * indent + "await asyncio.sleep(0)")
text = "\n".join(new_lines)

# Add await to calls (but not on def lines)
lines = text.splitlines()
new_lines = []
for line in lines:
    stripped = line.lstrip()
    if not (stripped.startswith("async def ") or stripped.startswith("def ")):
        for fn in ASYNC_FUNCS:
            line = re.sub(
                r'(?<!\bawait )(?<!\bdef )\b(' + re.escape(fn) + r')(\s*\()',
                r'await \1\2', line)
        line = line.replace("await await ", "await ")
    new_lines.append(line)
text = "\n".join(new_lines)

# Replace __main__ block
new_main = '''import asyncio

async def main():
    save = load_save()
    await title_screen(save)
    while True:
        sw = await weapon_select_screen(save)
        await game_loop(sw, save)
        await asyncio.sleep(0)

asyncio.run(main())'''

text = re.sub(r'\nif __name__\s*==\s*["\']__main__["\']\s*:.*', '', text, flags=re.DOTALL)
text += "\n\n" + new_main

if "import asyncio" not in text[:300]:
    text = "import asyncio\n" + text

with open("main.py", "w", encoding="utf-8") as f:
    f.write(text)

try:
    py_compile.compile("main.py", doraise=True)
    print("\n✓ main.py is valid — ready to build!")
    print("\nNow run:  python build_after_patch.py")
except py_compile.PyCompileError as e:
    print(f"\n✗ Syntax error: {e}")

input("\nPress Enter to exit...")
