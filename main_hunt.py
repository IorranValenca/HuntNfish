"""
Hunt & Fish
-----------
Controls
  WASD          Move          (standing still = quiet; sprint = loud)
  Mouse         Look
  Shift         Sprint
  1 / 2 / 3     Rifle / Revolver / Fishing Rod
  4 / 5 / 6     Bow / Shotgun / Binoculars  (must be purchased)
  F             Cycle owned weapons
  Left Click    Shoot  |  Charge bow (release to fire)  |  Cast rod
  Right Click   ADS / zoom
  R             Reload / cycle bolt / reel
  E             Collect loot / fish / enter Trader's Lodge
  Tab           Tackle box / switch shop tab
  H             Controls overlay
  Escape        Pause menu  (R = resume, H = controls, Q = quit)

Earn money by killing animals → collect their carcass → sell at
the Trader's Lodge (small wooden cabin in the woods near spawn).
Use the money to buy the Bow, Shotgun, and Binoculars.
"""
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from game_utils import solid
import sys, os

# ── Engine ───────────────────────────────────────────────────────────────────
app = Ursina(vsync=False)
window.title               = 'Hunt & Fish'
window.borderless          = False
window.exit_button.visible = False
window.fps_counter.enabled = True
mouse.locked               = True

# ── World ────────────────────────────────────────────────────────────────────
from world_hunt import build_world
build_world()

# ── Player ───────────────────────────────────────────────────────────────────
player = FirstPersonController(
    position          = Vec3(0, 2, 0),
    speed             = 5,
    jump_height       = 1.6,
    gravity           = 1.0,
    mouse_sensitivity = Vec2(40, 40),
)
player.cursor.enabled = False

# ── HUD ──────────────────────────────────────────────────────────────────────
from hud_hunt import HuntHUD
hud = HuntHUD()

# ── Rifle ────────────────────────────────────────────────────────────────────
import rifle_hunt as rifle_mod
rifle_mod.player_ref = player
rifle_mod.hud_ref    = hud
from rifle_hunt import BoltRifle
rifle = BoltRifle()
hud.refresh_ammo(rifle.ammo, rifle.state)

# ── Revolver ─────────────────────────────────────────────────────────────────
import revolver_hunt as rev_mod
rev_mod.player_ref = player
rev_mod.hud_ref    = hud
from revolver_hunt import Revolver
revolver = Revolver()
revolver.enabled = False

# ── Fishing rod ──────────────────────────────────────────────────────────────
import fishing as fish_mod
fish_mod.player_ref = player
from fishing import FishingRod
rod = FishingRod()
rod.enabled = False

# ── Bow / Shotgun / Binoculars (purchased at Trader's Lodge) ────────────────
import bow as bow_mod
bow_mod.player_ref = player
bow_mod.hud_ref    = hud
from bow import Bow
bow = Bow()
bow.enabled = False

import shotgun as shot_mod
shot_mod.player_ref = player
shot_mod.hud_ref    = hud
from shotgun import Shotgun
shotgun = Shotgun()
shotgun.enabled = False

import binoculars as bino_mod
bino_mod.player_ref = player
bino_mod.hud_ref    = hud
from binoculars import Binoculars
binoculars = Binoculars()
binoculars.enabled = False

# ── Animals ──────────────────────────────────────────────────────────────────
import animals_hunt as animals_mod
animals_mod.player_ref    = player
rifle_mod.animals_mod_ref = animals_mod
rev_mod.animals_mod_ref   = animals_mod
bow_mod.animals_mod_ref   = animals_mod
shot_mod.animals_mod_ref  = animals_mod
bino_mod.animals_mod_ref  = animals_mod

# ── Player HP ────────────────────────────────────────────────────────────────
_player_hp     = 100
_PLAYER_MAX_HP = 100
_hp_regen_t    = 0.0

def _on_player_damaged(amount):
    global _player_hp, _hp_regen_t
    _player_hp  = max(0, _player_hp - amount)
    _hp_regen_t = 0.0
    hud.refresh_hp(_player_hp)
    hud.show_hit(r=220, g=30, b=30)

animals_mod.player_damage_fn = _on_player_damaged
animals_mod.spawn_animals()

# ── Tool state ───────────────────────────────────────────────────────────────
active    = 'rifle'
paused    = False
_BASE_SPD = 5.0
_CYCLE    = ['rifle', 'revolver', 'rod']

_GRADE_STARS = {1: '[*   ]', 2: '[**  ]', 3: '[*** ]', 4: '[****]'}

# ── Economy ──────────────────────────────────────────────────────────────────
money              = 0
carcass_inventory  = []        # [{name, grade, weight, price}, ...]
owned_weapons      = {'rifle': True, 'revolver': True, 'rod': True,
                      'bow': False, 'shotgun': False, 'binoculars': False}
shop_open          = False

WEAPON_CATALOG = [
    {'key': 'B', 'id': 'bow',        'name': 'Recurve Bow',  'price': 250},
    {'key': 'X', 'id': 'binoculars', 'name': 'Binoculars',   'price': 175},
    {'key': 'S', 'id': 'shotgun',    'name': 'Shotgun',      'price': 500},
]
_CATALOG_BY_KEY = {w['key'].lower(): w for w in WEAPON_CATALOG}


def _compute_price(grade, weight):
    base = {1: 15, 2: 75, 3: 160, 4: 290}.get(grade, 10)
    mult = {1: 2.5, 2: 2.0, 3: 2.2, 4: 2.4}.get(grade, 1.5)
    return int(base + weight * mult)


def _refresh_shop_panel():
    catalog = []
    for w in WEAPON_CATALOG:
        catalog.append({
            'key':        w['key'],
            'name':       w['name'],
            'price':      w['price'],
            'owned':      owned_weapons[w['id']],
            'affordable': money >= w['price'],
        })
    hud.render_shop(money, carcass_inventory, catalog)


def _open_shop():
    global shop_open
    shop_open = True
    hud.show_shop()
    hud.set_shop_tab('sell')
    _refresh_shop_panel()


def _close_shop():
    global shop_open
    shop_open = False
    hud.hide_shop()


def _sell_one(idx):
    global money
    if 0 <= idx < len(carcass_inventory):
        item = carcass_inventory.pop(idx)
        money += item['price']
        hud.set_money(money)
        hud.add_log(f"Sold  {item['name']}  +${item['price']}")
        _refresh_shop_panel()


def _sell_all():
    global money
    if not carcass_inventory:
        return
    total = sum(c['price'] for c in carcass_inventory)
    money += total
    carcass_inventory.clear()
    hud.set_money(money)
    hud.add_log(f"Sold everything  +${total}")
    _refresh_shop_panel()


def _try_buy(weapon_id):
    global money
    if owned_weapons.get(weapon_id):
        return
    spec = next((w for w in WEAPON_CATALOG if w['id'] == weapon_id), None)
    if spec is None or money < spec['price']:
        return
    money -= spec['price']
    owned_weapons[weapon_id] = True
    hud.set_money(money)
    hud.add_log(f"Purchased  {spec['name']}!")
    if weapon_id not in _CYCLE:
        _CYCLE.append(weapon_id)
    _refresh_shop_panel()


def _activate(name):
    global active
    if not owned_weapons.get(name, False):
        return
    rifle.enabled      = (name == 'rifle')
    revolver.enabled   = (name == 'revolver')
    rod.enabled        = (name == 'rod')
    bow.enabled        = (name == 'bow')
    shotgun.enabled    = (name == 'shotgun')
    binoculars.enabled = (name == 'binoculars')
    active = name
    hud.set_tool(name)
    if name == 'rifle':
        hud.refresh_ammo(rifle.ammo, rifle.state)
    elif name == 'revolver':
        hud.refresh_ammo(revolver.ammo, revolver.state, revolver.MAG_SIZE)
    elif name == 'shotgun':
        hud.refresh_ammo(shotgun.ammo, shotgun.state, shotgun.MAG_SIZE)


def _collect_animal(animal):
    g    = animal._loot_grade
    w    = animal._loot_weight
    name = getattr(animal, '_loot_display_name', 'Animal')
    price = _compute_price(g, w)
    carcass_inventory.append({
        'name': name, 'grade': g, 'weight': w, 'price': price,
    })
    label = f"{_GRADE_STARS.get(g, '[*   ]')}  {name}  {w} kg   (+${price})"
    hud.add_log(label)
    animals_mod.collect_deer(animal)


# ── Mini-map dot palette ─────────────────────────────────────────────────────
_MM_DEER   = solid(220, 200, 130)
_MM_RABBIT = solid(240, 240, 235)
_MM_WOLF   = solid(255,  80,  60)
_MM_FOX    = solid(255, 140,  40)
_MM_BEAR   = solid(255,  30,  30)


# ── Input ────────────────────────────────────────────────────────────────────
def input(key):
    global paused

    # ── Shop interaction (takes priority over normal keys) ──────────────
    if shop_open:
        if key in ('escape', 'e'):
            _close_shop()
            return
        if key == 'tab':
            new_tab = 'buy' if hud._shop_tab == 'sell' else 'sell'
            hud.set_shop_tab(new_tab)
            _refresh_shop_panel()
            return
        if hud._shop_tab == 'sell':
            if key == 'a':
                _sell_all()
            elif key in '123456789':
                _sell_one(int(key) - 1)
        else:
            spec = _CATALOG_BY_KEY.get(key)
            if spec:
                _try_buy(spec['id'])
        return

    # ── Pause menu ──────────────────────────────────────────────────────
    if key == 'escape':
        paused       = not paused
        mouse.locked = not paused
        if paused:
            hud.show_pause_menu()
        else:
            hud.hide_pause_menu()
        return
    if paused:
        if key == 'r':
            paused       = False
            mouse.locked = True
            hud.hide_pause_menu()
        elif key == 'h':
            hud.toggle_controls()
        elif key == 'q':
            application.quit()
        return
    if key == 'h':
        hud.toggle_controls()
        return

    # ── Weapon select ───────────────────────────────────────────────────
    if   key == '1': _activate('rifle')
    elif key == '2': _activate('revolver')
    elif key == '3': _activate('rod')
    elif key == '4': _activate('bow')
    elif key == '5': _activate('shotgun')
    elif key == '6': _activate('binoculars')
    elif key == 'f':
        idx = _CYCLE.index(active) if active in _CYCLE else 0
        _activate(_CYCLE[(idx + 1) % len(_CYCLE)])

    # ── Fire / cast / charge ────────────────────────────────────────────
    if key == 'left mouse down':
        if   active == 'rifle':    rifle.try_shoot()
        elif active == 'revolver': revolver.try_shoot()
        elif active == 'shotgun':  shotgun.try_shoot()
        elif active == 'rod':      rod.on_click_down()
        elif active == 'bow':      bow.on_click_down()
        elif active == 'binoculars': binoculars.try_shoot()

    if key == 'left mouse up':
        if   active == 'rod': rod.on_click_up()
        elif active == 'bow': bow.on_click_up()

    # ── R — context-sensitive ───────────────────────────────────────────
    if key == 'r':
        if   active == 'rod':      rod.on_r_key()
        elif active == 'revolver': revolver.try_reload()
        elif active == 'shotgun':  shotgun.try_reload()
        # rifle handles R entirely via held_keys inside rifle.update()

    # ── E — collect / open shop / catch ─────────────────────────────────
    if key == 'e':
        from world_hunt import CABIN_DOOR_POS
        if (player.position - CABIN_DOOR_POS).length() < 4.0:
            _open_shop()
            return
        if active == 'rod' and rod.state == 'displaying':
            rod.on_collect_key()
        else:
            animal = animals_mod.get_lootable_near(player.position)
            if animal:
                _collect_animal(animal)

    if key == 'tab':
        if active == 'rod':
            rod.toggle_inventory()


# ── Update ───────────────────────────────────────────────────────────────────
def update():
    global _player_hp, _hp_regen_t
    if paused:
        return
    dt = time.dt

    # While the shop is open, freeze player movement / look but keep HUD ticking
    if shop_open:
        player.speed = 0
        hud.update(dt)
        return

    if held_keys['shift']:
        player.speed = _BASE_SPD * 1.7
        animals_mod.player_noise_mult = 1.55
    elif any(held_keys[k] for k in ('w', 'a', 's', 'd')):
        player.speed = _BASE_SPD
        animals_mod.player_noise_mult = 1.0
    else:
        player.speed = _BASE_SPD
        animals_mod.player_noise_mult = 0.55   # standing still — very quiet

    player.x = clamp(player.x, -220, 220)
    player.z = clamp(player.z, -220, 220)

    # Slow HP regen after 8 s without being hit
    _hp_regen_t += dt
    if _hp_regen_t > 8.0 and _player_hp < _PLAYER_MAX_HP:
        _player_hp = min(_PLAYER_MAX_HP, _player_hp + int(3 * dt))
        hud.refresh_hp(_player_hp)

    # Loot / cabin prompts (mutually exclusive — cabin wins if both apply)
    from world_hunt import CABIN_DOOR_POS, LAKE_X0, LAKE_X1, LAKE_Z0, LAKE_Z1
    near_cabin  = (player.position - CABIN_DOOR_POS).length() < 4.0
    near_animal = animals_mod.get_lootable_near(player.position)
    hud.show_cabin_prompt(near_cabin)
    hud.show_loot_prompt((near_animal is not None) and not near_cabin)

    # Compass / minimap / stealth
    hud.update_compass(player.rotation_y)
    hud.update_minimap(player.position, player.rotation_y,
                       (LAKE_X0, LAKE_X1, LAKE_Z0, LAKE_Z1),
                       [(animals_mod.all_deer,    _MM_DEER),
                        (animals_mod.all_rabbits, _MM_RABBIT),
                        (animals_mod.all_foxes,   _MM_FOX),
                        (animals_mod.all_wolves,  _MM_WOLF),
                        (animals_mod.all_bears,   _MM_BEAR)])
    hud.update_stealth(animals_mod.player_noise_mult)

    hud.update(dt)


app.run()
