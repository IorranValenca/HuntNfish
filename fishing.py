"""
Fishing rod — cast, wait for bite, reel minigame, catch display + inventory.
States: idle -> charging -> flying -> waiting -> nibble -> reeling -> displaying
"""
from ursina import *
from game_utils import solid
from world_hunt import is_water
from panda3d.core import TransparencyAttrib
import random, math, wave, struct, os

player_ref = None


def _gen_wav(path, fn, dur=0.12, sr=22050):
    if os.path.exists(path):
        return
    n = int(sr * dur)
    data = [max(-32767, min(32767, int(fn(i / sr) * 32767))) for i in range(n)]
    with wave.open(path, 'w') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr)
        f.writeframes(struct.pack(f'<{n}h', *data))


def _build_sounds():
    _gen_wav('cast_splash.wav',
             lambda t: (random.uniform(-1, 1) * 0.7 + math.sin(2*math.pi*180*t) * 0.3)
                       * math.exp(-t * 22) * 0.8, dur=0.14)
    _gen_wav('reel_click.wav',
             lambda t: math.sin(2*math.pi*1100*t) * math.exp(-t*90) * 0.5, dur=0.04)

_build_sounds()

# (name, weight_range, fight_speed, pull_strength, bite_wait_mul, body_rgb, sx, sy, sz)
FISH_SPECIES = [
    ('Largemouth Bass',  (0.8, 4.5), 1.2, 0.75, 1.0, ( 55,  92, 42), 1.0, 1.0, 1.0),
    ('Rainbow Trout',    (0.4, 2.8), 1.9, 0.55, 0.9, (175, 165,145), 0.9, 0.9, 1.1),
    ('Northern Pike',    (1.8, 7.5), 1.0, 1.40, 1.4, ( 50,  82, 38), 0.7, 0.7, 1.8),
    ('Channel Catfish',  (2.5,11.0), 0.6, 1.65, 1.6, (108,  88, 60), 1.1, 0.9, 1.2),
    ('Atlantic Salmon',  (1.8, 8.5), 2.1, 1.20, 1.8, (190, 148,125), 1.0, 0.9, 1.2),
    ('Bluegill',         (0.1, 0.6), 1.5, 0.35, 0.7, ( 55, 100,150), 1.2, 1.4, 0.8),
    ('Yellow Perch',     (0.2, 1.4), 1.7, 0.45, 0.85,(212, 178, 60), 1.0, 1.2, 0.95),
    ('Walleye',          (1.2, 5.5), 1.3, 0.85, 1.1, (115, 132, 78), 0.85, 0.9, 1.35),
    ('Black Crappie',    (0.3, 1.8), 1.4, 0.50, 0.9, (148, 145, 130), 1.1, 1.3, 0.85),
]
_WEIGHTS = [50, 45, 25, 20, 10, 60, 40, 28, 35]


def _pick_fish():
    return random.choices(FISH_SPECIES, weights=_WEIGHTS, k=1)[0]


# ── Splash ripples on water ───────────────────────────────────────────────────

class _Ripple(Entity):
    def __init__(self, position, start_scale=0.45, grow_rate=4.0, life=1.3):
        super().__init__(model='quad', texture=solid(225, 235, 245),
                         scale=start_scale,
                         position=position,
                         rotation_x=90,
                         color=color.rgba(255, 255, 255, 200))
        self.setTransparency(TransparencyAttrib.M_alpha)
        self._life     = life
        self._max_life = life
        self._grow     = grow_rate

    def update(self):
        dt = time.dt
        self._life -= dt
        if self._life <= 0:
            destroy(self); return
        self.scale_x += self._grow * dt
        self.scale_y += self._grow * dt
        a = int(200 * (self._life / self._max_life))
        self.color = color.rgba(255, 255, 255, a)


# ── 3-D fish display model ────────────────────────────────────────────────────

class CaughtFish(Entity):
    def __init__(self, position, species_data):
        super().__init__(position=position)

        br, bg, bb = species_data[5]
        sx, sy, sz = species_data[6], species_data[7], species_data[8]
        name = species_data[0]

        T_BODY   = solid(br, bg, bb)
        T_BELLY  = solid(min(255, br+48), min(255, bg+36), min(255, bb+28))
        T_FIN    = solid(max(0, br-24),   max(0, bg-24),   max(0, bb-18))
        T_EYE    = solid(15, 15, 15)
        T_STRIPE = solid(min(255, br+30), max(0, bg-25),   max(0, bb-25))

        # Main body
        Entity(parent=self, model='sphere', texture=T_BODY,
               scale=(0.30*sx, 0.13*sy, 0.52*sz))
        # Lighter belly
        Entity(parent=self, model='sphere', texture=T_BELLY,
               scale=(0.22*sx, 0.095*sy, 0.40*sz),
               position=(0, -0.027*sy, 0.01*sz))

        # Tail fork — upper
        Entity(parent=self, model='cube', texture=T_FIN,
               scale=(0.07*sx, 0.18*sy, 0.14*sz),
               position=(0,  0.060*sy, -0.29*sz), rotation_x=-25)
        # Tail fork — lower
        Entity(parent=self, model='cube', texture=T_FIN,
               scale=(0.07*sx, 0.18*sy, 0.14*sz),
               position=(0, -0.060*sy, -0.29*sz), rotation_x=25)

        # Dorsal fin
        Entity(parent=self, model='cube', texture=T_FIN,
               scale=(0.04*sx, 0.15*sy, 0.25*sz),
               position=(0, 0.108*sy, 0.04*sz), rotation_x=6)

        # Pectoral fins
        Entity(parent=self, model='cube', texture=T_FIN,
               scale=(0.15*sx, 0.04*sy, 0.11*sz),
               position=(-0.148*sx, -0.010*sy, 0.09*sz), rotation_z=20)
        Entity(parent=self, model='cube', texture=T_FIN,
               scale=(0.15*sx, 0.04*sy, 0.11*sz),
               position=( 0.148*sx, -0.010*sy, 0.09*sz), rotation_z=-20)

        # Anal fin
        Entity(parent=self, model='cube', texture=T_FIN,
               scale=(0.04*sx, 0.08*sy, 0.10*sz),
               position=(0, -0.100*sy, -0.10*sz))

        # Eyes
        for ex in (-0.138*sx, 0.138*sx):
            Entity(parent=self, model='sphere', texture=T_EYE,
                   scale=(0.038, 0.038, 0.028),
                   position=(ex, 0.022*sy, 0.21*sz))

        # Catfish whiskers
        if 'Catfish' in name:
            for wx, dz in ((-0.13, 0.02), (0.13, 0.02), (-0.09, -0.03), (0.09, -0.03)):
                Entity(parent=self, model='cube', texture=T_FIN,
                       scale=(0.010, 0.010, 0.18*sz),
                       position=(wx*sx, -0.018*sy, 0.24*sz + dz*sz))

        # Trout / Salmon lateral stripe
        if 'Trout' in name or 'Salmon' in name:
            Entity(parent=self, model='cube', texture=T_STRIPE,
                   scale=(0.055*sx, 0.048*sy, 0.44*sz),
                   position=(0, 0.010*sy, 0))

        # Pike flank markings
        if 'Pike' in name:
            T_MARK = solid(100, 132, 68)
            for i in range(6):
                px = (i - 2.5) * 0.055 * sz
                Entity(parent=self, model='sphere', texture=T_MARK,
                       scale=(0.04*sx, 0.022*sy, 0.055*sz),
                       position=(0, 0.048*sy, px))

        # Bluegill vertical bars
        if 'Bluegill' in name:
            T_BAR = solid(max(0, br-35), max(0, bg-35), min(255, bb+20))
            for i in range(5):
                pz = (i - 2) * 0.06 * sz
                Entity(parent=self, model='cube', texture=T_BAR,
                       scale=(0.28*sx, 0.12*sy, 0.025*sz),
                       position=(0, 0, pz))


# ── Fishing rod ───────────────────────────────────────────────────────────────

class FishingRod(Entity):
    HIP_POS = Vec3(.20, -.26, .34)

    def __init__(self):
        super().__init__(parent=camera, position=self.HIP_POS)

        # — Rod model —
        T_BLANK = solid(100, 72, 38)
        T_DARK  = solid( 55, 42, 22)
        T_CORK  = solid(210,185,150)
        T_METAL = solid( 60, 62, 65)

        self._body = Entity(parent=self, model='cube', texture=T_BLANK,
                            scale=(.020,.020,.60), position=(0,0,.30))
        self._tip  = Entity(parent=self, model='cube', texture=T_DARK,
                            scale=(.010,.010,.35), position=(0,.003,.63))
        Entity(parent=self, model='cube', texture=T_CORK,
               scale=(.032,.032,.16), position=(0,0,-.02))
        Entity(parent=self, model='cube', texture=T_METAL,
               scale=(.036,.044,.08), position=(0,-.016,.04))
        Entity(parent=self, model='sphere', texture=T_METAL,
               scale=(.03,.055,.055), position=(.02,-.035,.05))
        for gz in (.15, .35, .55):
            Entity(parent=self, model='cube', texture=T_METAL,
                   scale=(.028,.005,.005), position=(0,.015,gz))

        self._tip_marker = Entity(parent=self._tip, position=(0,0,.55))

        # Bobber
        self._bobber = Entity(model='sphere', texture=solid(215,45,45),
                              scale=.075, enabled=False)
        Entity(parent=self._bobber, model='sphere',
               texture=solid(240,240,240), scale=.6, position=(0,.5,0))

        # Line visual
        self._line_vis = Entity(model='cube', texture=solid(215,215,200),
                                scale=(.006,.006,1), enabled=False)

        # — UI — (all quads use texture= to avoid Ursina color bug)
        ui = camera.ui

        # Cast power bar (left)
        self._pw_bg   = Entity(parent=ui, model='quad', texture=solid(18,18,18),
                               scale=(.018,.22), position=(-.75,0), enabled=False)
        self._pw_fill = Entity(parent=ui, model='quad', texture=solid(50,210,80),
                               scale=(.014,.001), position=(-.75,-.095),
                               origin=(0,-.5), enabled=False)
        self._pw_lbl  = Text(parent=ui, text='POWER', position=(-.75,-.145),
                              scale=.85, origin=(0,0), enabled=False)

        # Reel minigame bar (centre)
        BAR_Y = -.20
        self._rl_bg      = Entity(parent=ui, model='quad', texture=solid(22,22,22),
                                  scale=(.52,.032), position=(0,BAR_Y), enabled=False)
        self._rl_zone    = Entity(parent=ui, model='quad', texture=solid(45,185,55),
                                  scale=(.10,.028), position=(0,BAR_Y), enabled=False)
        self._rl_needle  = Entity(parent=ui, model='quad', texture=solid(240,240,240),
                                  scale=(.005,.036), position=(0,BAR_Y), enabled=False)
        self._rl_prog_bg = Entity(parent=ui, model='quad', texture=solid(22,22,22),
                                  scale=(.52,.018), position=(0,BAR_Y+.038), enabled=False)
        self._rl_prog    = Entity(parent=ui, model='quad', texture=solid(80,220,80),
                                  scale=(.001,.015), position=(-.26,BAR_Y+.038),
                                  origin=(-.5,0), enabled=False)
        self._rl_hint    = Text(parent=ui, text='CLICK / R  to reel',
                                position=(0,BAR_Y-.038), scale=.88,
                                origin=(0,0), enabled=False)
        self._rl_fish    = Text(parent=ui, text='', position=(0,BAR_Y-.072),
                                scale=1.0, color=color.rgb(80,220,255),
                                origin=(0,0), enabled=False)

        # Bite alert
        self._bite_txt   = Text(parent=ui, text='!! BITE !!  LEFT CLICK',
                                position=(0,.05), scale=2.2,
                                color=color.rgba(255,220,30,0), origin=(0,0))
        self._bite_flash = 0.0

        # Feedback text
        self._fb_txt = Text(parent=ui, text='', position=(0,.12), scale=1.8,
                             origin=(0,0))
        self._fb_t   = 0.0
        self._fb_rgb = (255,255,255)

        # Crosshair dot
        self._dot = Entity(parent=ui, model='quad', texture=solid(240,240,240),
                           scale=(.005,.005))

        # ── Catch display panel (bottom strip) ───────────────────────────────
        CX, CY = 0, -0.28
        self._catch_panel   = Entity(parent=ui, model='quad', texture=solid(14,18,22),
                                     scale=(.62,.20), position=(CX,CY), z=0.1, enabled=False)
        # border frame (slightly larger, different shade)
        Entity(parent=self._catch_panel, model='quad', texture=solid(40,80,100),
               scale=(1.02,1.04), position=(0,0), z=0.05)
        Entity(parent=self._catch_panel, model='quad', texture=solid(14,18,22),
               scale=(0.99,0.985), position=(0,0), z=0.04)

        self._catch_title   = Text(parent=ui, text='CATCH !',
                                   position=(CX, CY+.145), scale=3.0,
                                   color=color.rgb(255,215,45), origin=(0,0), enabled=False)
        self._catch_name    = Text(parent=ui, text='',
                                   position=(CX+.06, CY+.04), scale=1.55,
                                   color=color.white, origin=(0,0), enabled=False)
        self._catch_weight  = Text(parent=ui, text='',
                                   position=(CX+.06, CY-.015), scale=1.25,
                                   color=color.rgba(200,200,200,220), origin=(0,0), enabled=False)
        self._catch_swatch  = Entity(parent=ui, model='quad', texture=solid(100,100,100),
                                     scale=(.10,.065), position=(CX-.19, CY+.015),
                                     z=0.09, enabled=False)
        self._catch_collect = Text(parent=ui, text='Press  E  to collect',
                                   position=(CX, CY-.115), scale=1.05,
                                   color=color.rgb(100,240,100), origin=(0,0), enabled=False)

        # ── Inventory panel (Tab to toggle) ───────────────────────────────────
        self._inv_panel = Entity(parent=ui, model='quad', texture=solid(12,16,20),
                                 scale=(.70,.58), position=(0,0), z=0.1, enabled=False)
        Entity(parent=self._inv_panel, model='quad', texture=solid(38,75,95),
               scale=(1.02,1.025), z=0.05)
        Entity(parent=self._inv_panel, model='quad', texture=solid(12,16,20),
               scale=(0.99,0.988), z=0.04)
        self._inv_text  = Text(parent=ui, text='', position=(-.30,.25),
                               scale=.88, color=color.white, enabled=False)

        # — State —
        self.state       = 'idle'
        self._charge     = 0.0
        self._fly_t      = 0.0
        self._fly_dur    = 1.0
        self._fly_start  = Vec3(0,0,0)
        self._fly_end    = Vec3(0,0,0)
        self._wait_t     = 0.0
        self._nibble_t   = 0.0
        self._fish_data  = None
        self._in_water   = False

        self._reel_needle = 0.5
        self._reel_zone_p = 0.35
        self._reel_zone_w = 0.26
        self._reel_prog   = 0.0
        self._reel_pull   = 1.0
        self._reel_spd    = 1.0

        # Fish struggle / surge
        self._surge_t      = 0.0
        self._surge_active = 0.0
        self._surge_flash  = 0.0

        # Trajectory preview dots (during charging)
        T_DOT = solid(255, 240, 180)
        self._traj_dots = [
            Entity(model='sphere', texture=T_DOT, scale=0.06, enabled=False)
            for _ in range(10)
        ]

        # Surge alert (during fight)
        ui = camera.ui
        self._surge_txt = Text(parent=ui, text='SURGE!', position=(0, -.13),
                               scale=1.6, color=color.rgba(255, 90, 80, 0),
                               origin=(0, 0), enabled=False)
        # Tension warning (low reel-progress)
        self._tens_txt = Text(parent=ui, text='LINE TIGHT!', position=(0, -.16),
                              scale=1.4, color=color.rgba(255, 60, 60, 0),
                              origin=(0, 0), enabled=False)
        # Cast distance readout (briefly after splash)
        self._dist_txt = Text(parent=ui, text='', position=(0, -.06),
                              scale=1.4, color=color.rgba(150, 220, 255, 0),
                              origin=(0, 0), enabled=False)
        self._dist_t  = 0.0
        self._last_cast_dist = 0.0

        self._bob_t = 0.0
        self._sway  = Vec3(0,0,0)

        # Catch / inventory state
        self.inventory       = []          # list of {'name':str, 'weight':float}
        self._caught_entity  = None        # the CaughtFish 3D entity
        self._pending_fish   = None        # data for the fish being displayed
        self._display_spin   = 0.0

        self._snd_splash = base.loader.loadSfx('cast_splash.wav')
        self._snd_click  = base.loader.loadSfx('reel_click.wav')
        self._snd_splash.setVolume(0.7)
        self._snd_click.setVolume(0.4)

    # ── Public controls ──────────────────────────────────────────────────────

    def on_click_down(self):
        if self.state == 'idle':
            self.state   = 'charging'
            self._charge = 0.0
        elif self.state == 'nibble':
            self._start_reel()
        elif self.state == 'waiting':
            self._reel_in()
        elif self.state == 'reeling':
            self._tap_reel(0.09)

    def on_click_up(self):
        if self.state == 'charging':
            self._cast()

    def on_r_key(self):
        if self.state == 'reeling':
            self._tap_reel(0.12)
        elif self.state in ('waiting', 'nibble', 'flying'):
            self._reel_in()

    def on_collect_key(self):
        if self.state != 'displaying':
            return
        # Store in inventory
        self.inventory.append(self._pending_fish)
        # Destroy 3-D fish
        if self._caught_entity:
            destroy(self._caught_entity)
            self._caught_entity = None
        self._hide_catch_ui()
        self.state = 'idle'
        f = self._pending_fish
        self._show_feedback(f"Stored: {f['name']}  {f['weight']} kg", 80, 230, 80)
        self._pending_fish = None

    def toggle_inventory(self):
        if self._inv_panel.enabled:
            self._inv_panel.enabled = False
            self._inv_text.enabled  = False
        else:
            self._refresh_inventory_text()
            self._inv_panel.enabled = True
            self._inv_text.enabled  = True

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _cast(self):
        if not player_ref:
            return
        power  = 0.3 + self._charge * 0.7
        horiz  = Vec3(camera.forward.x, 0, camera.forward.z).normalized()
        dist   = 6 + power * 28
        end    = player_ref.position + horiz * dist + Vec3(0, 0.04, 0)

        self._fly_start = self._tip_marker.world_position
        self._fly_end   = end
        self._fly_t     = 0.0
        self._fly_dur   = 0.45 + power * 0.45
        self.state      = 'flying'
        self._in_water  = is_water(end.x, end.z)
        self._last_cast_dist = dist

        self._bobber.position  = self._fly_start
        self._bobber.enabled   = True
        self._line_vis.enabled = True
        self.rotation_x        = 0
        self._set_pw_visible(False)
        self._hide_trajectory()

    def _reel_in(self):
        self.state             = 'idle'
        self._bobber.enabled   = False
        self._line_vis.enabled = False
        self._fish_data        = None
        self._set_pw_visible(False)
        self._set_reel_visible(False)
        self._bite_txt.color   = color.rgba(255, 220, 30, 0)
        self._surge_txt.enabled = False
        self._tens_txt.enabled  = False
        self.rotation_x         = 0

    def _start_reel(self):
        f = self._fish_data
        self.state        = 'reeling'
        self._reel_needle = 0.5
        self._reel_zone_p = random.uniform(0.15, 0.60)
        self._reel_prog   = 0.25
        self._reel_pull   = f[3] if f else 1.0
        self._reel_spd    = f[2] if f else 1.0
        self._surge_t      = random.uniform(2.0, 4.0)
        self._surge_active = 0.0
        self._bite_txt.color = color.rgba(255, 220, 30, 0)
        if f:
            self._rl_fish.text    = f[0]
            self._rl_fish.enabled = True
        self._set_reel_visible(True)

    def _hide_trajectory(self):
        for dot in self._traj_dots:
            dot.enabled = False

    def _update_trajectory(self):
        if not player_ref:
            return
        power = 0.3 + self._charge * 0.7
        horiz = Vec3(camera.forward.x, 0, camera.forward.z).normalized()
        dist  = 6 + power * 28
        start = self._tip_marker.world_position
        end   = player_ref.position + horiz * dist + Vec3(0, 0.04, 0)
        n = len(self._traj_dots)
        for i, dot in enumerate(self._traj_dots):
            p = (i + 1) / (n + 1)
            pos = start + (end - start) * p
            pos.y += math.sin(p * math.pi) * 5
            dot.position = pos
            dot.enabled  = True

    def _spawn_splash(self):
        """Ripple rings and small spray cubes when bobber lands in water."""
        pos = Vec3(self._bobber.x, 0.10, self._bobber.z)
        _Ripple(pos, start_scale=0.45, grow_rate=4.5, life=1.2)
        _Ripple(pos, start_scale=0.20, grow_rate=2.8, life=1.0)
        for _ in range(8):
            sp = Entity(model='cube',
                        texture=solid(220, 235, 250),
                        scale=random.uniform(0.04, 0.09),
                        position=pos + Vec3(random.uniform(-.2, .2), 0,
                                            random.uniform(-.2, .2)))
            sp.animate_y(0.6 + random.uniform(.1, .5), duration=0.35,
                         curve=curve.out_quad)
            sp.animate_position(sp.position +
                                Vec3(random.uniform(-.4, .4), -0.4,
                                     random.uniform(-.4, .4)),
                                duration=0.7, curve=curve.in_quad)
            destroy(sp, delay=0.7)

    def _tap_reel(self, amount):
        self._reel_needle = min(1.0, self._reel_needle + amount)
        self._snd_click.play()

    def _set_pw_visible(self, on):
        self._pw_bg.enabled   = on
        self._pw_fill.enabled = on
        self._pw_lbl.enabled  = on

    def _set_reel_visible(self, on):
        self._rl_bg.enabled      = on
        self._rl_zone.enabled    = on
        self._rl_needle.enabled  = on
        self._rl_prog_bg.enabled = on
        self._rl_prog.enabled    = on
        self._rl_hint.enabled    = on
        if not on:
            self._rl_fish.enabled = False

    def _on_catch(self):
        f   = self._fish_data
        kg  = round(random.uniform(*f[1]), 2)
        self._reel_in()           # hide bobber / line, state → idle
        self._spawn_caught_fish(f, kg)

    def _on_lost(self):
        self._show_feedback('The fish got away!', 255, 120, 40)
        self._reel_in()

    def _spawn_caught_fish(self, species_data, weight):
        if not player_ref:
            return
        # Position the fish in front of the player, above eye level so it
        # occupies the upper portion of the screen
        fwd = Vec3(camera.forward.x, 0, camera.forward.z)
        if fwd.length() > 0.01:
            fwd = fwd.normalized()
        pos = (player_ref.position
               + Vec3(0, player_ref.camera_pivot.y, 0)
               + fwd * 1.3
               + Vec3(0, 0.28, 0))

        self._caught_entity = CaughtFish(pos, species_data)
        self._caught_entity.scale = 2.2
        self._display_spin  = 0.0
        self._pending_fish  = {'name': species_data[0], 'weight': weight}
        self.state          = 'displaying'

        # Show catch UI card
        br, bg, bb = species_data[5]
        self._catch_name.text   = species_data[0]
        self._catch_weight.text = f'{weight} kg'
        self._catch_swatch.texture = solid(br, bg, bb)
        self._catch_title.enabled   = True
        self._catch_panel.enabled   = True
        self._catch_name.enabled    = True
        self._catch_weight.enabled  = True
        self._catch_swatch.enabled  = True
        self._catch_collect.enabled = True

    def _hide_catch_ui(self):
        for e in (self._catch_panel, self._catch_title, self._catch_name,
                  self._catch_weight, self._catch_swatch, self._catch_collect):
            e.enabled = False

    def _show_feedback(self, text, r, g, b):
        self._fb_txt.text  = text
        self._fb_txt.color = color.rgba(r, g, b, 230)
        self._fb_t         = 3.5
        self._fb_rgb       = (r, g, b)

    def _refresh_inventory_text(self):
        lines = ['TACKLE BOX', '──────────────────────────']
        if not self.inventory:
            lines.append('  (empty — go catch something!)')
        else:
            for item in self.inventory:
                lines.append(f"  {item['name']:<22} {item['weight']} kg")
            total_w = sum(i['weight'] for i in self.inventory)
            lines.append('──────────────────────────')
            lines.append(f"  {len(self.inventory)} fish    total: {total_w:.2f} kg")
        lines.append('')
        lines.append('  Press TAB to close')
        self._inv_text.text = '\n'.join(lines)

    # ── Ursina update ────────────────────────────────────────────────────────

    def update(self):
        if not self.enabled:
            return
        dt = time.dt

        if self.state == 'charging':
            if held_keys['left mouse']:
                self._charge = min(1.0, self._charge + dt * 1.0)
                self.rotation_x = -self._charge * 32
                self._set_pw_visible(True)
                self._pw_fill.scale_y = max(0.001, self._charge * 0.19)
                self._update_trajectory()
            else:
                self.rotation_x = 0
                self._hide_trajectory()
                self._cast()

        elif self.state == 'flying':
            self._fly_t += dt
            p = min(1.0, self._fly_t / self._fly_dur)
            pos = self._fly_start + (self._fly_end - self._fly_start) * p
            pos.y += math.sin(p * math.pi) * 5
            self._bobber.position = pos
            if p >= 1.0:
                if self._in_water:
                    self._snd_splash.play()
                    self._spawn_splash()
                    self._dist_txt.text = f'{int(self._last_cast_dist)} m'
                    self._dist_t = 2.0
                    self._dist_txt.enabled = True
                    self._wait_t = random.uniform(3, 14)
                    self.state   = 'waiting'
                else:
                    self.state   = 'waiting'
                    self._wait_t = 999

        elif self.state == 'waiting':
            self._bobber.y = 0.04 + math.sin(time.time() * 1.4) * 0.007
            if self._in_water:
                self._wait_t -= dt
                if self._wait_t <= 0:
                    self._fish_data = _pick_fish()
                    self.state      = 'nibble'
                    self._nibble_t  = 2.8

        elif self.state == 'nibble':
            self._nibble_t -= dt
            self._bobber.y = 0.04 - abs(math.sin(time.time() * 5.5)) * 0.045
            self._bite_flash += dt * 4
            a = int((math.sin(self._bite_flash) * 0.5 + 0.5) * 230)
            self._bite_txt.color = color.rgba(255, 220, 30, a)
            # rod tip twitches with the bite
            self.rotation_x = math.sin(time.time() * 24) * 4
            if self._nibble_t <= 0:
                self._bite_txt.color = color.rgba(255, 220, 30, 0)
                self.rotation_x = 0
                self.state      = 'waiting'
                self._wait_t    = random.uniform(5, 18)
                self._fish_data = None

        elif self.state == 'reeling':
            pull = self._reel_pull
            spd  = self._reel_spd

            # Surge timing — periodic burst-pulls that move the zone & ramp pull
            self._surge_t -= dt
            if self._surge_t <= 0:
                self._surge_active = 1.0
                self._surge_flash  = 0.55
                self._reel_zone_p  = random.uniform(0.04, 0.94 - self._reel_zone_w)
                self._surge_t      = random.uniform(2.4, 4.6)
                self._surge_txt.enabled = True
            if self._surge_active > 0:
                self._surge_active = max(0.0, self._surge_active - dt * 0.75)
            extra_pull = self._surge_active * 1.6

            self._reel_needle -= (pull + extra_pull) * dt * 0.38
            self._reel_needle  = max(0.0, self._reel_needle)

            self._reel_zone_p += math.sin(time.time() * spd * 1.8) * dt * 0.25
            self._reel_zone_p  = clamp(self._reel_zone_p, 0.02,
                                       1.0 - self._reel_zone_w - 0.02)

            in_zone = (self._reel_zone_p <= self._reel_needle <=
                       self._reel_zone_p + self._reel_zone_w)
            self._reel_prog += (0.20 if in_zone else -0.28) * dt
            self._reel_prog  = clamp(self._reel_prog, 0.0, 1.0)

            BAR_W  = 0.52
            BAR_X0 = -0.26
            self._rl_zone.x        = BAR_X0 + self._reel_zone_p * BAR_W + self._reel_zone_w * BAR_W * 0.5
            self._rl_needle.x      = BAR_X0 + self._reel_needle * BAR_W
            self._rl_prog.scale_x  = max(0.001, self._reel_prog * BAR_W)

            # Rod bend — leans down with the fish, harder during surges
            target_pitch = -22 - self._surge_active * 18
            self.rotation_x = lerp(self.rotation_x, target_pitch, dt * 6)

            # Bobber dives erratically during the fight
            dive_t = time.time() * (5 + spd * 2)
            dive   = 0.05 + math.sin(dive_t) * 0.05 + self._surge_active * 0.12
            self._bobber.y = 0.02 - dive

            # Surge alert flash
            if self._surge_flash > 0:
                self._surge_flash -= dt
                a = int(min(1, self._surge_flash / 0.55) * 230)
                self._surge_txt.color = color.rgba(255, 90, 80, a)
            else:
                self._surge_txt.enabled = False

            # Tension warning when progress is dangerously low
            if self._reel_prog < 0.18:
                a = int((math.sin(time.time() * 9) * 0.4 + 0.6) * 230)
                self._tens_txt.enabled = True
                self._tens_txt.color   = color.rgba(255, 60, 60, a)
            else:
                self._tens_txt.enabled = False

            if self._reel_prog >= 1.0:
                self._on_catch()
            elif self._reel_prog <= 0.0:
                self._on_lost()

        elif self.state == 'displaying':
            # Slowly spin the caught fish so the player can see it
            if self._caught_entity:
                self._display_spin += dt * 42
                self._caught_entity.rotation_y = self._display_spin

        # Line tip → bobber
        if self._bobber.enabled:
            tip  = self._tip_marker.world_position
            bob  = self._bobber.world_position
            mid  = (tip + bob) * 0.5
            dist = (tip - bob).length()
            if dist > 0.01:
                self._line_vis.world_position = mid
                self._line_vis.look_at(bob)
                self._line_vis.scale_z = dist

        # Feedback text fade
        if self._fb_t > 0:
            self._fb_t -= dt
            a = max(0, min(230, int(self._fb_t / 3.5 * 230)))
            r, g, b = self._fb_rgb
            self._fb_txt.color = color.rgba(r, g, b, a)
            if self._fb_t <= 0:
                self._fb_txt.text = ''

        # Cast distance readout fade
        if self._dist_t > 0:
            self._dist_t -= dt
            a = max(0, min(230, int(self._dist_t / 2.0 * 230)))
            self._dist_txt.color = color.rgba(150, 220, 255, a)
            if self._dist_t <= 0:
                self._dist_txt.enabled = False

        # Rod sway (skip while displaying)
        if self.state != 'displaying':
            moving = any(held_keys[k] for k in ('w', 'a', 's', 'd'))
            if moving and self.state != 'charging':
                self._bob_t += dt * 5
                sway = Vec3(math.sin(self._bob_t) * .004,
                            abs(math.sin(self._bob_t)) * .002, 0)
            else:
                sway = Vec3(0, 0, 0)
            self._sway = Vec3(lerp(self._sway.x, sway.x, dt * 8),
                              lerp(self._sway.y, sway.y, dt * 8), 0)
            dest = self.HIP_POS + self._sway
            self.x = lerp(self.x, dest.x, dt * 12)
            self.y = lerp(self.y, dest.y, dt * 12)

    def on_disable(self):
        self._set_pw_visible(False)
        self._set_reel_visible(False)
        self._bite_txt.color    = color.rgba(255, 220, 30, 0)
        self._dot.enabled       = False
        self._surge_txt.enabled = False
        self._tens_txt.enabled  = False
        self._dist_txt.enabled  = False
        self._hide_trajectory()
        # Clean up any active display
        if self.state == 'displaying':
            self._hide_catch_ui()
            if self._caught_entity:
                destroy(self._caught_entity)
                self._caught_entity = None
            self.state = 'idle'

    def on_enable(self):
        self._dot.enabled = True
