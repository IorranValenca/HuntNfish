# AGENTS.md — Hunt & Fish (Huntio)

This file is the orientation guide for AI assistants (Claude, GPT, Cursor, etc.) and contributors who need to make changes without re-reading every module first.

---

## 1. What this project is

A first-person hunting + fishing sandbox built with [Ursina](https://www.ursinaengine.org/) on Panda3D. **All visible objects are procedural cubes / spheres / cylinders** — there are no external 3D mesh imports. Textures are 1×1 solid color PNMImages.

The active game's entry point is **`main_hunt.py`**. Everything in this document refers to that game unless noted. A separate, unrelated Ursina project rooted at `main.py` also lives in the folder (`enemy.py`, `weapon.py`, `hud.py`, `map_builder.py`, `simulator.py`) — leave it alone unless explicitly asked.

## 2. Run / dev loop

```bash
pip install -r requirements.txt
python main_hunt.py
```

Tested on Python 3.11 + Ursina latest. There is no test suite. Verify changes by running the game and exercising the affected feature.

## 3. File map (Hunt & Fish)

| File | Role |
| ---- | ---- |
| `main_hunt.py` | Entry point. Boots Ursina, builds the world, instantiates the player + every weapon/tool, owns the economy state (`money`, `carcass_inventory`, `owned_weapons`), handles all input, drives the per-frame update of HUD/compass/minimap/stealth. |
| `world_hunt.py` | `build_world()` constructs ground plane, lake, dock, trees (pine/oak), bushes, stumps, fallen logs, wildflowers, lily pads, reeds, mountains with snow caps, drifting clouds, and the **Trader's Lodge**. Exports `LAKE_X0/X1/Z0/Z1`, `CABIN_POS`, `CABIN_DOOR_POS`, `is_water(x,z)`. |
| `hud_hunt.py` | `HuntHUD` — single class owning every UI element: tool chip, ammo, HP bar, hit/kill markers, kill ribbon, stats panel, compass strip, mini-map, stealth indicator, money display, kill log, loot/cabin prompts, pause menu, controls overlay, shop panel. |
| `animals_hunt.py` | All animal AI: `Deer`, `Rabbit`, `Wolf`, `Fox`, `Bear`, `Bird`. State machines (graze/walk/alert/flee/chase/charge etc.), herd cohesion (deer), pack coordination (wolves), bear stand-up alert pose. Spawns happen in `spawn_animals()`. Module globals are the source of truth: `all_deer`, `all_rabbits`, `all_wolves`, `all_foxes`, `all_bears`, `all_birds`, `lootable_deer`, `player_noise_mult`, `player_damage_fn`. |
| `rifle_hunt.py` | Bolt-action `BoltRifle`. 5-round mag, manual bolt cycle, scope ADS with overlay + reticle, shell ejection, smoke puffs, headshot detection, blood splat on hit. |
| `revolver_hunt.py` | `Revolver` — 6-shot DA, animated cylinder rotation per shot, swing-out reload. Uses `Revolvershot.mp3` / `RevolverReload.mp3`. |
| `fishing.py` | `FishingRod`, plus `_Ripple`, `CaughtFish` (the 3-D fish shown after a catch), and the `FISH_SPECIES` table. State machine: idle → charging → flying → waiting → nibble → reeling → displaying. Reel mini-game with surge mechanic, rod bend, bobber dive, tension warning, trajectory preview, splash ripples. |
| `bow.py` | `Bow` + `_Arrow`. Hold LMB to draw, release to fire a projectile that gets raycast each frame and sticks into surfaces / damages animals. **Silent** — small spook radius. |
| `shotgun.py` | `Shotgun`. 5-shell magazine, 8-pellet spread per shot, shell-by-shell reload. Headshot detection per pellet but only one kill credit per volley. |
| `binoculars.py` | `Binoculars`. Right-click zoom (FOV 18°). Left-click tags whatever animal is in the crosshair → adds to `binoculars.tagged_animals` (set). |
| `effects.py` | Shared `blood_splat(world_pos, n, intensity)` — spawns red sphere particles with gravity that flatten when they hit the ground. Used by every weapon. |
| `game_utils.py` | `solid(r, g, b)` — cached 1×1 `PNMImage` texture helper. **Use this for every flat color** — avoids an Ursina color/shader bug. |
| `bake_model.py` | Standalone utility (not imported). Auto-orients a GLTF model so its longest axis points along Panda3D +Z and saves a BAM. Useful for future 3D model imports. |
| `requirements.txt` | Ursina. |
| Various `.wav` / `.mp3` | Sound effects. Some WAVs are generated at module import time (`_gen_wav` in the weapon files) if missing; the MP3s are downloaded sound clips. |

## 4. Architecture & conventions

### 4.1 Texture pattern — always use `solid()`

Ursina has a known issue where `Entity(color=...)` can render incorrectly under certain shader paths. **Every flat-color surface in this codebase uses a 1×1 PNMImage texture instead**, fetched via `solid(r, g, b)` from `game_utils.py`. Values are 0–255. The result is cached so the same color returns the same `Texture` object.

```python
from game_utils import solid
Entity(model='cube', texture=solid(120, 60, 20))   # ✅
Entity(model='cube', color=color.rgb(120, 60, 20)) # ❌ avoid
```

### 4.2 Weapon model helpers

Every weapon's `__init__` builds the gun model out of dozens of small `Entity` children parented to a `self._gun_root`. To keep the code compact, weapons use local helper closures:

```python
def P(mdl, sc, pos, tex, **kw):
    return Entity(parent=self._gun_root, model=mdl,
                  scale=sc, position=pos, texture=tex, **kw)

def Cy(sc, pos, tex):
    # sc = (x_diameter, length, z_diameter); cube takes (x, z_diam, length)
    return Entity(parent=self._gun_root, model='cube',
                  scale=(sc[0], sc[2], sc[1]), position=pos, texture=tex)
```

`Cy()` is named "cylinder" historically but **always produces a cube** with the scale dimensions transposed so the length runs along Z (forward). This is because Ursina's `'cylinder'` primitive was unreliable in this env — see the rifle history if curious.

### 4.3 Module-level globals as wiring

Weapons and animals talk to the rest of the game through **module-level globals** that `main_hunt.py` populates at boot:

```python
# In rifle_hunt.py
player_ref      = None    # set by main: player FirstPersonController
hud_ref         = None    # set by main: HuntHUD instance
animals_mod_ref = None    # set by main: the animals_hunt module
```

After import, `main_hunt.py` does:

```python
import rifle_hunt as rifle_mod
rifle_mod.player_ref = player
rifle_mod.hud_ref    = hud
rifle_mod.animals_mod_ref = animals_mod
```

Same pattern for every weapon. The animals module similarly exposes `player_ref`, `player_damage_fn`, and `player_noise_mult` as globals.

### 4.4 Coordinate conventions

- Ursina/Panda3D: +X right, +Y up, +Z forward.
- Player heading: `player.rotation_y` (degrees). 0 = facing +Z = north (game convention).
- Weapons are parented to `camera` so they follow head movement; their local +Z points outward toward the muzzle.
- `rotation_x = 90` on a `Cylinder` model lays it horizontally along +Z — used for the original procedural barrel before it was switched to cubes.

### 4.5 Hit detection

All hitscan weapons (`rifle`, `revolver`, `shotgun`, `binoculars`) use Ursina's `raycast(origin, direction, distance, ignore=[...])`. The arrow uses a per-frame raycast over its travel segment.

Headshot heuristic (shared):
```python
head_y  = target.y + target.scale_y * 0.30
is_head = hit.world_point.y > head_y
dmg     = self.DAMAGE * (1.7 if is_head else 1.0)
```

### 4.6 HUD update contract

`HuntHUD` is built once in `main_hunt.py` and updated each frame by calling:

```python
hud.update_compass(player.rotation_y)
hud.update_minimap(player.position, player.rotation_y, lake_rect, animal_groups)
hud.update_stealth(animals_mod.player_noise_mult)
hud.update(dt)   # fades hit markers, kill ribbon, log, etc.
```

Weapons push state into the HUD via:
- `hud.refresh_ammo(ammo, state, mag_size)`
- `hud.register_shot()` / `hud.register_hit(headshot)` / `hud.register_miss()` / `hud.register_kill(name, distance, headshot)`
- `hud.add_log(text)` — left-side log strip
- `hud.show_hit(r, g, b)` — fullscreen damage flash (red = player took damage)

### 4.7 Economy state (lives in `main_hunt.py`)

```python
money              = 0                     # int
carcass_inventory  = []                    # [{name, grade, weight, price}]
owned_weapons      = {'rifle': True, ..., 'bow': False, 'shotgun': False, 'binoculars': False}
shop_open          = False
WEAPON_CATALOG     = [{'key': 'B', 'id': 'bow', 'name': 'Recurve Bow', 'price': 250}, ...]
```

Prices: `_compute_price(grade, weight)` — base table by grade × weight multiplier. Defined inline in `main_hunt.py`.

### 4.8 Stealth / noise

`animals_mod.player_noise_mult` is set each frame in `main_hunt.update()`:
- standing still → `0.55` (very quiet)
- WASD → `1.0`
- Shift held → `1.55` (very loud)

Each animal's `ALERT_D` / `FLEE_D` / `CHASE_D` are multiplied by this value in their LOS check. The HUD shows this state via `hud.update_stealth(...)`.

## 5. Game systems in detail

### Animals — life cycle

1. Spawned in `animals_hunt.spawn_animals()` at hardcoded positions; appended to `all_<species>` lists.
2. Each animal's `update()` is auto-called by Ursina (since they're `Entity` subclasses).
3. LOS check on a cadence (every ~0.2–0.35s) decides state transitions.
4. Damage via `take_damage(amount, shooter_pos)`. Death sets `state = 'dead'`, removes from `all_<species>`, adds to `lootable_deer`, runs a tip-over animation, and schedules `destroy(self, delay=60)`.
5. `get_lootable_near(pos, radius=2.8)` returns the closest collectable carcass within radius. Used by the `E` key in `main_hunt.py`.
6. `collect_deer(animal)` removes the animal from `lootable_deer` and destroys it.

### Trader's Lodge — interaction flow

1. Player walks within 4 m of `CABIN_DOOR_POS` → `hud.show_cabin_prompt(True)`.
2. `E` → `_open_shop()` in `main_hunt.py`: sets `shop_open = True`, `hud.show_shop()`, `hud.set_shop_tab('sell')`, `_refresh_shop_panel()`.
3. While `shop_open`, `input()` short-circuits: digits sell, `A` sells all, `Tab` switches tabs, letter keys (`B`/`X`/`S`) buy weapons, `E`/`Esc` close.
4. `update()` early-returns after freezing `player.speed = 0`.

### Fishing — state graph

```
idle → charging → flying → waiting → nibble → reeling → displaying → idle
                                  ↘ (timeout) ↗
```

- `charging` shows trajectory preview dots.
- `flying` interpolates bobber along parabola; on landing in water → spawn ripples + spray + cast-distance readout.
- `waiting` is silent bobbing until a random timer fires.
- `nibble` triggers a 2.8 s window to click (rod also twitches).
- `reeling` runs the surge / rod-bend / bobber-dive / tension-warning mini-game.
- `displaying` spins the caught fish in front of the camera; `E` stores it.

## 6. Adding a new ...

### ... weapon

1. Make a new file `myweapon.py` modeled on `bow.py` or `shotgun.py`. It must:
   - Subclass `Entity` with `parent=camera, position=self.HIP_POS`.
   - Build the gun model under `self._gun_root`.
   - Expose module globals `player_ref`, `hud_ref`, `animals_mod_ref` that `main_hunt.py` will populate.
   - Implement either `try_shoot()` (instant) or `on_click_down()` / `on_click_up()` (charge).
   - Implement `update()` for ADS / bob / reload.
   - Implement `on_disable()` to reset FOV and any state.
2. In `main_hunt.py`:
   - Import and instantiate (start `.enabled = False`).
   - Add to `owned_weapons` dict and `WEAPON_CATALOG`.
   - Wire the new weapon into `_activate()`.
   - Add a number key in `input()`.
3. Update `hud_hunt.py`'s `set_tool()` `names` dict with a display label + color.

### ... animal

1. New class in `animals_hunt.py` modeled on `Deer` or `Wolf`. Add an `all_<name>` list and append in `__init__`.
2. Implement `take_damage`, `_die`, `update`, and the state-machine helpers.
3. Add positions to `spawn_animals()`.
4. (Optional) Add to the minimap palette in `main_hunt.py` and to the `update_minimap()` call.
5. (Optional) Update `_compute_price` if your animal's grade range is unusual.

### ... HUD element

1. Build the entity in `HuntHUD.__init__`. Use `parent=ui` (which is `camera.ui`).
2. Always set its texture via `solid(r, g, b)` — not `color=`.
3. Add a public method (e.g. `set_xxx(value)` / `update_xxx(...)`) that other modules call.
4. Fade / animation logic goes in `HuntHUD.update(dt)`.

## 7. Pitfalls / lessons learned

- **Ursina's built-in `'cylinder'` model is unreliable in some installs** (silent missing-model warning, entities don't render). Use cubes with transposed scale instead (`Cy()` helper).
- **Fog (`scene.set_fog(...)`) tints distant geometry by camera distance.** With a 480-unit ground plane, this makes the ground color shift as you pan. Avoid fog unless you also shrink visible geometry.
- **`Entity(color=...)` can render wrong** under some Ursina versions — always use `texture=solid(...)`.
- **`Text(parent=scene, ...)` in world space is flaky.** Stick to UI-space text on `camera.ui` for anything you need to read.
- **`mouse.locked = False`** disables FirstPersonController look, so any modal panel must either keep the mouse locked and rely on keyboard, or accept that the camera will freeze.
- **Don't `destroy()` an animal during another module's iteration over its `all_*` list.** Iterate over `list(all_deer)` if you need to remove during the loop.

## 8. Style

- 4-space indents.
- Roughly PEP 8 but loose on line length — readability wins.
- Comments are sparse and explain *why*, not *what*. Section dividers (`# ── name ──`) mark major regions inside long `__init__`s.
- No type hints — the project values brevity. Don't add them unless asked.
- Don't add tests, CI, or docstrings unless asked. The project is a single-player game maintained by hand.
