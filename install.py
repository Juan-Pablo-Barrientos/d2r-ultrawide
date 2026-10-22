"""Remove D2R's ultrawide side fade and 19:9 black side bars.

Reads the original files from YOUR game install, edits them, and writes the
results into a mod folder. Nothing in the game install itself is changed.

By default this creates a standalone mod called "ultrawide" that uses your
normal (unmodded) save folder. To add the fix to a mod you already play,
pass --mod <that mod's name> instead.

usage: py install.py --game "D:\\Diablo II Resurrected"
       py install.py --game "D:\\Diablo II Resurrected" --mod SomeOtherMod
       py install.py --game "D:\\Diablo II Resurrected" --uninstall
"""
import argparse
import json
import os
import sys

import casc
import dxbc

DEFAULT_MOD = "ultrawide"
TEXTURE = "data/hd/global/textures/vignette/vignette.texture"
SHADER = "data/hd/shaders/ps_create_vignette_p.bin"
TEXTURE_HEADER = 0x2C

# ps_create_vignette_p ends with  fade = x*x*(3 - 2x);  out = tex * (1 - fade)
# Zeroing the literals of `mad r0.z, r0.x, l(-2.0), l(3.0)` makes fade == 0.
SMOOTHSTEP_OLD = bytes.fromhex("01400000000000c00140000000004040")
SMOOTHSTEP_NEW = bytes.fromhex("01400000000000000140000000000000")


def white_texture(original):
    if original[:4] != b"<DE(":
        raise ValueError("unexpected texture header %r" % original[:4])
    return original[:TEXTURE_HEADER] + b"\xff" * (len(original) - TEXTURE_HEADER)


def unfaded_shader(original):
    data = bytearray(original)
    start, size = dxbc.find(original)
    blob = bytes(data[start:start + size])
    if blob[4:20] != dxbc.checksum(blob):
        raise ValueError("DXBC checksum check failed on the original shader")
    if blob.count(SMOOTHSTEP_OLD) != 1:
        raise ValueError("shader does not match the expected build; not patching")
    patched = bytearray(blob.replace(SMOOTHSTEP_OLD, SMOOTHSTEP_NEW))
    patched[4:20] = dxbc.checksum(bytes(patched))
    data[start:start + size] = patched
    return bytes(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True, help="D2R install folder (contains D2R.exe)")
    ap.add_argument("--mod", default=DEFAULT_MOD,
                    help="mod to install into (default: create the standalone '%s' mod)" % DEFAULT_MOD)
    ap.add_argument("--force", action="store_true", help="overwrite files that already exist in the mod")
    ap.add_argument("--uninstall", action="store_true", help="remove the files this script installs")
    args = ap.parse_args()

    if not os.path.isfile(os.path.join(args.game, ".build.info")):
        sys.exit("not a D2R install folder (no .build.info): %s" % args.game)
    mod_dir = os.path.join(args.game, "mods", args.mod)
    root = os.path.join(mod_dir, args.mod + ".mpq")
    targets = [os.path.join(root, *p.split("/")) for p in (TEXTURE, SHADER)]
    modinfo = os.path.join(root, "modinfo.json")

    if args.uninstall:
        for t in targets:
            if os.path.exists(t):
                os.remove(t)
                print("removed", t)
        if args.mod == DEFAULT_MOD and os.path.isdir(mod_dir):
            print("the '%s' mod folder is left in place: %s" % (DEFAULT_MOD, mod_dir))
        return

    if not os.path.isdir(root):
        if args.mod != DEFAULT_MOD:
            sys.exit("mod folder not found: %s" % root)
        os.makedirs(root)
        # "../" points the mod at the normal save folder, so existing characters show up.
        with open(modinfo, "w") as f:
            json.dump({"name": DEFAULT_MOD, "savepath": "../"}, f)
        print("created mod", root)
    existing = [t for t in targets if os.path.exists(t)]
    if existing and not args.force:
        sys.exit("already exists (use --force to overwrite):\n  " + "\n  ".join(existing))

    storage = casc.Casc(args.game)
    files = casc.tvfs_files(storage.read_ekey(storage.config["vfs-2"][1]))

    def extract(path):
        return b"".join(storage.read_ekey(ek) for ek, _ in files[path])

    outputs = [white_texture(extract(TEXTURE)), unfaded_shader(extract(SHADER))]
    for target, data in zip(targets, outputs):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as f:
            f.write(data)
        print("wrote", target)
    print("done - start the game with -mod %s" % args.mod)


if __name__ == "__main__":
    main()
