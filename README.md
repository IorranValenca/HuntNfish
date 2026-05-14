# Huntio — Hunt & Fish

A first-person hunting and fishing sandbox built with [Ursina](https://www.ursinaengine.org/) (Python / Panda3D). All assets are procedural cubes/spheres — no external 3D models required.

## Run it

```bash
pip install -r requirements.txt
python main_hunt.py
```

Tested on Python 3.11. The game spawns you in an open forest beside a lake with a Trader's Lodge nearby.

## Gameplay

| Key             | Action                                                      |
| --------------- | ----------------------------------------------------------- |
| `WASD`          | Move (standing still = quiet, sprint = loud)                |
| `Shift`         | Sprint                                                      |
| `Mouse`         | Look                                                        |
| `1` / `2` / `3` | Rifle / Revolver / Fishing Rod (always owned)               |
| `4` / `5` / `6` | Bow / Shotgun / Binoculars (purchase at the lodge)          |
| `F`             | Cycle owned weapons                                         |
| Left click      | Shoot · Charge bow · Cast rod · Tag with binoculars         |
| Right click     | ADS / zoom                                                  |
| `R`             | Reload / cycle bolt / reel                                  |
| `E`             | Collect carcass · Store fish · Enter Trader's Lodge         |
| `Tab`           | Tackle box · Switch shop tab                                |
| `H`             | Controls overlay                                            |
| `Esc`           | Pause menu (`R` resume, `H` controls, `Q` quit)             |

**Hunting loop:** kill animals → walk over them and press `E` to collect → visit the Trader's Lodge (cabin a short walk from spawn) → press `E` to open the shop → sell carcasses (`A` = sell all) → switch to BUY tab with `Tab` → buy Bow / Shotgun / Binoculars.

**Fishing loop:** equip the rod with `3`, walk to the lake/dock, hold left click to charge, release to cast (trajectory arc preview), wait for the bite, click on the alert, then react to the reel mini-game (zone-track + fish surges) until progress fills.

## Project layout

The active game is **Hunt & Fish**. Its entry point is [`main_hunt.py`](main_hunt.py). See [`AGENTS.md`](AGENTS.md) for a full architecture map for AI assistants and contributors.

The folder also contains an unrelated older Ursina project rooted at [`main.py`](main.py) (`enemy.py`, `weapon.py`, `hud.py`, `map_builder.py`, `simulator.py`). It is not part of Hunt & Fish.

## Credits

- Engine: [Ursina](https://github.com/pokepetter/ursina) / Panda3D
- Sound effects: a mix of procedurally generated WAVs and downloaded MP3 clips (see filenames in repo root)
