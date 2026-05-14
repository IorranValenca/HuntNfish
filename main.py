"""
FPS Combat Zone  -  Call of Duty style prototype
-------------------------------------------------
Controls
  WASD          Move
  Mouse         Look around
  Left Click    Shoot  (hold for auto-fire)
  Right Click   Aim Down Sights
  Shift         Sprint
  Ctrl          Crouch
  R             Reload
  F             Toggle fullscreen
  Escape        Pause / unlock mouse
"""

from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random, math, sys, os

# ── Engine init ──────────────────────────────────────────────────────────────
app = Ursina(vsync=False)
window.title               = 'FPS Combat Zone'
window.borderless          = False
window.exit_button.visible = False
window.fps_counter.enabled = True
mouse.locked               = True

try:
    base.setBackgroundColor(88/255, 112/255, 145/255)
except Exception:
    pass

# ── Map ───────────────────────────────────────────────────────────────────────
from map_builder import build_map
build_map()

# ── Player ────────────────────────────────────────────────────────────────────
player = FirstPersonController(
    position          = Vec3(0, 2, 0),
    speed             = 7,
    jump_height       = 1.8,
    gravity           = 1.0,
    mouse_sensitivity = Vec2(40, 40),
)
player.cursor.enabled = False

# ── Weapon ────────────────────────────────────────────────────────────────────
import weapon as weapon_mod
weapon_mod.player_ref = player
gun = weapon_mod.Weapon()

# ── HUD ───────────────────────────────────────────────────────────────────────
import hud as hud_mod
hud = hud_mod.HUD()
weapon_mod.hud_ref = hud

# ── Enemy system ──────────────────────────────────────────────────────────────
import enemy as enemy_mod
enemy_mod.player_ref = player
enemy_mod.hud_ref    = hud

# ── Game state ────────────────────────────────────────────────────────────────
kills       = 0
wave        = 1
game_over   = False
paused      = False
_wave_delay = 0.0
_BASE_SPD   = 7.0


def on_kill():
    global kills
    kills += 1
    hud.refresh_kills(kills)
    hud.add_kill_feed()
    hud.refresh_wave(wave, len(enemy_mod.all_enemies))

enemy_mod.on_kill_cb = on_kill


def start_wave(w):
    global wave, _wave_delay
    wave        = w
    _wave_delay = 0.0
    enemy_mod.spawn_wave(w)
    hud.refresh_wave(w, len(enemy_mod.all_enemies))
    hud.show_wave_banner(w)


start_wave(1)


# ── Input ─────────────────────────────────────────────────────────────────────
def input(key):
    global game_over, paused

    if key == 'escape':
        paused       = not paused
        mouse.locked = not paused
        return

    if key == 'f':
        window.fullscreen = not window.fullscreen
        return

    if game_over:
        if key == 'r':
            os.execv(sys.executable, [sys.executable] + sys.argv)
        return

    if key == 'r':
        gun.start_reload()

    if key == 'left mouse down':
        gun.try_shoot()
        hud._ch_spread = min(hud._ch_spread + .012, .06)


# ── Update ────────────────────────────────────────────────────────────────────
def update():
    global game_over, _wave_delay, wave

    if paused or game_over:
        return

    dt = time.dt

    if held_keys['shift']:
        player.speed = _BASE_SPD * 1.65
    elif held_keys['control']:
        player.speed = _BASE_SPD * 0.42
    else:
        player.speed = _BASE_SPD

    target_cam_y = 1.0 if held_keys['control'] else 2.0
    player.camera_pivot.y = lerp(player.camera_pivot.y, target_cam_y, dt * 10)

    player.x = clamp(player.x, -54, 54)
    player.z = clamp(player.z, -54, 54)

    hud.update()
    hud.update_compass(player.rotation_y % 360)
    hud.refresh_wave(wave, len(enemy_mod.all_enemies))

    if not any(held_keys[k] for k in ('w', 'a', 's', 'd')):
        hud._ch_spread = max(0, hud._ch_spread - dt * .14)

    if hud.hp <= 0 and not game_over:
        game_over    = True
        mouse.locked = False
        hud.show_game_over(kills)
        return

    if len(enemy_mod.all_enemies) == 0 and _wave_delay <= 0:
        _wave_delay = 6.5
        hud.show_wave_complete(wave, kills)

    if _wave_delay > 0:
        _wave_delay -= dt
        if _wave_delay <= 0:
            start_wave(wave + 1)


app.run()
