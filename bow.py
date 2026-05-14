"""Recurve hunting bow — charged shot, silent, projectile-based arrows."""
from ursina import *
from game_utils import solid
from effects import blood_splat
import math, random

player_ref      = None
hud_ref         = None
animals_mod_ref = None


class _Arrow(Entity):
    """Physics-projected arrow that flies, detects hits, sticks on miss."""
    GRAVITY = 11.0
    LIFE    = 4.0

    def __init__(self, position, velocity, damage):
        super().__init__(model=None, position=position)
        T_SHAFT = solid(155, 115, 70)
        T_HEAD  = solid(200, 200, 210)
        T_FETCH = solid(220, 220, 220)
        Entity(parent=self, model='cube', scale=(.018, .018, .58),
               position=(0, 0, .04), texture=T_SHAFT)
        Entity(parent=self, model='cube', scale=(.026, .026, .07),
               position=(0, 0, .36), texture=T_HEAD, rotation_y=45)
        for ang in (0, 60, 120):
            Entity(parent=self, model='cube', scale=(.008, .055, .08),
                   position=(0, 0, -.23),
                   rotation_z=ang, texture=T_FETCH)

        self._vel    = velocity
        self._life   = self.LIFE
        self._stuck  = False
        self._damage = damage
        self.look_at(self.position + self._vel)

    def update(self):
        if self._stuck:
            return
        dt = time.dt
        self._life -= dt
        if self._life <= 0:
            destroy(self); return

        self._vel.y -= self.GRAVITY * dt
        step = self._vel * dt
        step_len = step.length()
        if step_len < 0.001:
            return

        direction = step.normalized()
        ignore = [player_ref]
        if hasattr(self, '_owner_gun') and self._owner_gun:
            ignore.append(self._owner_gun)
        hit = raycast(self.world_position, direction,
                      distance=step_len, ignore=ignore)
        if hit.hit:
            if hud_ref: hud_ref.register_shot()
            if hasattr(hit.entity, 'take_damage'):
                target  = hit.entity
                head_y  = target.y + target.scale_y * 0.30
                is_head = hit.world_point.y > head_y
                dmg     = self._damage * (1.7 if is_head else 1.0)
                dist    = (player_ref.position - hit.world_point).length() \
                          if player_ref else 0
                target.take_damage(dmg,
                                   player_ref.position if player_ref else None)
                blood_splat(hit.world_point,
                            n=20 if is_head else 12,
                            intensity=1.4 if is_head else 1.0)
                died = getattr(target, 'state', '') == 'dead' \
                       or getattr(target, 'hp', 1) <= 0
                if hud_ref:
                    if died:
                        name = getattr(target, '_loot_display_name', 'Animal')
                        hud_ref.register_kill(name, dist, is_head)
                    else:
                        hud_ref.register_hit(is_head)
                destroy(self); return
            else:
                # Stick into the world surface
                self.world_position = hit.world_point
                self.look_at(self.world_position + direction)
                self._stuck = True
                self._life  = 12.0
                if hud_ref: hud_ref.register_miss()
                return

        # No hit this frame — advance
        self.position += step
        self.look_at(self.position + self._vel)


class Bow(Entity):
    DAMAGE       = 95         # raw, before headshot multiplier
    MAX_RANGE    = 220.0
    HIP_POS      = Vec3(.20, -.14, .26)
    ADS_POS      = Vec3(.00, -.06, .20)
    ADS_FOV      = 38

    DRAW_DUR     = 1.10
    MIN_POWER    = 0.35
    MAX_VEL      = 60.0       # m/s at full draw

    def __init__(self):
        super().__init__(parent=camera, position=self.HIP_POS)
        self._gun_root = Entity(parent=self)
        T_WOOD   = solid(118,  74,  32)
        T_WOOD_D = solid( 80,  48,  20)
        T_GRIP   = solid( 55,  35,  18)
        T_STRING = solid(220, 220, 215)
        T_ARROW  = solid(160, 120,  72)
        T_HEAD   = solid(205, 205, 215)
        T_FETCH  = solid(225, 225, 225)

        # Riser (handle / grip block in the middle)
        Entity(parent=self._gun_root, model='cube',
               scale=(.022, .120, .060), position=(0, 0, .08),
               texture=T_GRIP)
        Entity(parent=self._gun_root, model='cube',
               scale=(.030, .180, .025), position=(0, 0, .12),
               texture=T_WOOD)

        # Upper limb (curved, segmented)
        for i, (sy, sz, rx) in enumerate([
            (.090, .025, -10),
            (.080, .024, -25),
            (.060, .022, -42),
        ]):
            Entity(parent=self._gun_root, model='cube',
                   scale=(.018, sy, sz),
                   position=(0, 0.085 + i*0.075, .12),
                   rotation_x=rx, texture=T_WOOD)
        # Lower limb (mirror)
        for i, (sy, sz, rx) in enumerate([
            (.090, .025,  10),
            (.080, .024,  25),
            (.060, .022,  42),
        ]):
            Entity(parent=self._gun_root, model='cube',
                   scale=(.018, sy, sz),
                   position=(0, -0.085 - i*0.075, .12),
                   rotation_x=rx, texture=T_WOOD)

        # Tips
        self._tip_up   = Entity(parent=self._gun_root, model='sphere',
                                scale=.025,
                                position=(0,  0.245, -.038),
                                texture=T_WOOD_D)
        self._tip_dn   = Entity(parent=self._gun_root, model='sphere',
                                scale=.025,
                                position=(0, -0.245, -.038),
                                texture=T_WOOD_D)

        # Bowstring — single visible cube; will animate during draw
        self._string = Entity(parent=self._gun_root, model='cube',
                              scale=(.004, .50, .004),
                              position=(0, 0, .085),
                              texture=T_STRING)

        # Nocked arrow (visible only when ready to fire)
        self._arrow_visual = Entity(parent=self._gun_root, position=(0, 0, .085))
        Entity(parent=self._arrow_visual, model='cube',
               scale=(.012, .012, .50),
               position=(0, 0, -.10), texture=T_ARROW)
        Entity(parent=self._arrow_visual, model='cube',
               scale=(.018, .018, .06),
               position=(0, 0, .14), texture=T_HEAD, rotation_y=45)
        for ang in (0, 60, 120):
            Entity(parent=self._arrow_visual, model='cube',
                   scale=(.006, .045, .055),
                   position=(0, 0, -.30),
                   rotation_z=ang, texture=T_FETCH)

        # Muzzle (where arrow spawns from)
        self._muzzle = Entity(parent=self._gun_root, position=(0, 0, .35))

        # State
        self.state    = 'ready'    # ready | drawing | reloading
        self._draw_t  = 0.0
        self._charge  = 0.0
        self._ads     = False
        self._reload_t = 0.0
        self._sway    = Vec3(0, 0, 0)
        self._bob_t   = 0.0

        # Audio — reuse generic shot/click sounds, soft
        try:
            self._snd_release = base.loader.loadSfx('bolt_fwd.wav')
            self._snd_release.setVolume(0.35)
        except Exception:
            self._snd_release = None
        try:
            self._snd_draw = base.loader.loadSfx('bullet_insert.wav')
            self._snd_draw.setVolume(0.25)
        except Exception:
            self._snd_draw = None

    # ── Input bridge ────────────────────────────────────────────────────────
    def on_click_down(self):
        if self.state == 'ready':
            self.state   = 'drawing'
            self._draw_t = 0.0
            if self._snd_draw: self._snd_draw.play()

    def on_click_up(self):
        if self.state == 'drawing':
            self._fire()

    def try_shoot(self):
        # not used; bow uses on_click_down / on_click_up
        pass

    # ── Internals ───────────────────────────────────────────────────────────
    def _fire(self):
        power = max(self.MIN_POWER, self._charge)
        vel_mag = self.MAX_VEL * power
        forward = camera.forward.normalized()
        velocity = forward * vel_mag + Vec3(0, 0.7, 0)   # tiny upward arc
        pos = self._muzzle.world_position

        arrow = _Arrow(pos, velocity, self.DAMAGE * (0.6 + 0.4 * power))
        arrow._owner_gun = self

        if self._snd_release: self._snd_release.play()
        self._charge  = 0.0
        self._draw_t  = 0.0
        self.state    = 'reloading'
        self._reload_t = 0.55
        self._arrow_visual.enabled = False
        self._string.position = (0, 0, .085)
        if animals_mod_ref:
            # Bow is much quieter than firearms — small spook radius
            animals_mod_ref.spook_all(camera.world_position, 14)

    # ── Update ──────────────────────────────────────────────────────────────
    def update(self):
        if not self.enabled:
            return
        dt = time.dt

        if self.state == 'drawing':
            self._draw_t = min(self.DRAW_DUR, self._draw_t + dt)
            self._charge = self._draw_t / self.DRAW_DUR
            # Pull the string and nocked arrow back
            pull = self._charge * 0.18
            self._string.position = (0, 0, .085 - pull)
            self._arrow_visual.position = (0, 0, .085 - pull)
            self._arrow_visual.enabled = True
        elif self.state == 'reloading':
            self._reload_t -= dt
            if self._reload_t <= 0:
                self.state = 'ready'
                self._arrow_visual.enabled = True

        # ADS
        prev_ads = self._ads
        self._ads = bool(held_keys['right mouse'])
        target = self.ADS_POS if self._ads else self.HIP_POS
        camera.fov = lerp(camera.fov, self.ADS_FOV if self._ads else 80, dt * 10)

        # Bob / sway
        moving = any(held_keys[k] for k in ('w','a','s','d'))
        if moving and not self._ads:
            self._bob_t += dt * 6
            sway = Vec3(math.sin(self._bob_t) * .004,
                        abs(math.sin(self._bob_t)) * .002, 0)
        else:
            sway = Vec3(0, 0, 0)
        self._sway = Vec3(lerp(self._sway.x, sway.x, dt*8),
                          lerp(self._sway.y, sway.y, dt*8), 0)
        dest = target + self._sway
        self.position = Vec3(lerp(self.x, dest.x, dt*12),
                             lerp(self.y, dest.y, dt*12),
                             lerp(self.z, dest.z, dt*12))

    def on_disable(self):
        self._charge   = 0.0
        self._draw_t   = 0.0
        self.state     = 'ready'
        self._ads      = False
        self._reload_t = 0.0
        self._string.position = (0, 0, .085)
        self._arrow_visual.position = (0, 0, .085)
        self._arrow_visual.enabled = True
        camera.fov = 80
