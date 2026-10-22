# D2R Ultrawide: remove the 19:9 side bars

Diablo II: Resurrected caps the playfield at 19:9. On a wider screen (21:9, 32:9) it **blacks out the sides of the screen**
(about 200 px per side on 3440×1440) with a short fade into the black. This repo removes that, so the game fills your whole screen.

Two ways to install:

| | Works with other mods? | Needs |
|---|---|---|
| **A. D2RLoader memory patch** (recommended) | Yes, any mod or none | [D2RLoader](https://d2rloader.net) |
| **B. Standalone mod** | No, D2R loads one mod at a time | Python 3 |

No game files are modified or included here. Option A changes 4 bytes in memory when the game starts.
Option B builds a small mod from **your own** game files.

> **Offline / single player only.** Don't use mods or patches on Battle.net.
> Blizzard capped the view at 19:9 because monsters at the screen edges don't react to you yet,
> so with this you can see, and hit, some monsters slightly before they notice you.

## A. D2RLoader memory patch (recommended)

1. Copy [`d2rloader/ultrawide.json`](d2rloader/ultrawide.json) into `<game folder>\d2rloader\patches\`.
2. Start the game through D2RLoader, with or without a mod.

The loader log (`d2rloader\logs\d2rloader.log`) should show:

```
[PATCH]      Ultrawide (no 19:9 side bars) [global] — 1 change
```

To uninstall, delete the file.

The patch includes the original bytes it expects. If a D2R or D2RLoader update moves the code, the loader refuses the patch instead of writing to the wrong place.
In that case, open an issue.

## B. Standalone mod (no D2RLoader)

Requires Python 3.8 or newer ([python.org](https://www.python.org/downloads/)). The scripts use only the standard library.

```
py install.py --game "C:\Program Files (x86)\Diablo II Resurrected"
```

This creates `<game>\mods\ultrawide`. It uses your normal save folder, so your existing offline characters show up. Start the game with `-mod ultrawide`
(Battle.net launcher → Game Settings → Additional command line arguments).

The mod also removes the screen-edge vignette completely, while option A keeps the normal vignette.

To add the fix to a mod you already play, use `--mod YourModName`. You have to re-run it whenever that mod is regenerated or updated.
To remove it, run the same command with `--uninstall`.

## Tested with

- D2R 3.3.0 (build 93847) and D2RLoader 1.3.1-beta, on 3440×1440 (21:9)
- Option A: tested with another mod active. In that test the patch also changed the constant described under *Notes*, which on its own made no visible difference.
- Option B: tested through D2RLoader; the Battle.net launcher's `-mod` route hasn't been tested yet

## How it works

The side bars aren't a UI overlay. They're drawn by the pixel shader `data/hd/shaders/ps_create_vignette_p.bin`. Each frame the game gives that shader the screen width `W`, height `H` and the cap `k = 19/9`.
The shader blacks out everything outside a centred area `k·H` wide, fades into the black over `W/36` px, and multiplies by the vignette mask `data/hd/global/textures/vignette/vignette.texture`.

**Option A** changes where the game sets `k`:

```
mov dword ptr [rdx+8], 0x40071C72   ; k = 19/9   (RVA 0xE19DF8 in D2RLoader's image)
mov dword ptr [rdx+8], 0x40800000   ; k = 4.0
```

The shader's fade only reaches the screen when `k·H < W·19/18`, so `k = 4.0` removes it on screens up to 32:9.
The vignette mask is then stretched wider, which leaves only a light, normal-looking edge vignette.

**Option B** overrides the two data files instead:

- The **shader**: the smoothstep `fade = x*x*(3 - 2x)` (`mad r0.z, r0.x, l(-2.0), l(3.0)`) gets both literals set to `0.0`, so `fade` is always 0.
  The DXBC checksum (the MD5 variant at bytes 4–20) is recomputed by `dxbc.py`. Before patching, the script checks that this code reproduces the original shader's stored checksum.
- The **vignette mask** (1024×576 RGBA, multiplied over the screen) is set to full white.

`casc.py` is a small read-only CASC/TVFS reader (local `.idx` → `data.###` → BLTE → TVFS path table) and also works on its own:

```
py casc.py "C:\Program Files (x86)\Diablo II Resurrected" list vignette
py casc.py "C:\Program Files (x86)\Diablo II Resurrected" get data/hd/shaders/ps_create_vignette_p.bin out.bin
```

### Notes for anyone digging further

- `D2R.exe`'s code section is encrypted on disk. These addresses were found in the running game's memory, under D2RLoader.
- A separate 19/9 constant (RVA `0x1CBA908` in the same image) is used by code that draws black side rectangles and keeps the mouse cursor out of them.
  Changing it made no visible difference in normal play. If your cursor can't reach the screen edges, try changing it as well.
- Writing to the game's code while it's running made it close. Patch it at startup through D2RLoader instead.
- Loose files in `<game>\Data\hd` are only read with `-direct`, and that needs a fully extracted install.

## License

MIT. Not affiliated with or endorsed by Blizzard Entertainment. Diablo is a trademark of Blizzard Entertainment, Inc.
