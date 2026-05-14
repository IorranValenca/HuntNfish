"""
Weapon system for FPS Combat Zone.
"""
from ursina import *
from ursina import Texture as UrsinaTexture
from panda3d.core import Texture as P3DTex, PNMImage
import random, math, wave, struct, os

player_ref = None
hud_ref    = None


def _gen_wav(path, samples_fn, duration=0.13, sr=22050):
    """Write a mono 16-bit WAV to path using samples_fn(i, t) → float [-1,1]."""
    if os.path.exists(path):
        return
    n = int(sr * duration)
    data = [max(-32767, min(32767, int(samples_fn(i, i / sr) * 32767)))
            for i in range(n)]
    with wave.open(path, 'w') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr)
        f.writeframes(struct.pack(f'<{n}h', *data))


def _build_sounds():
    # Gunshot: white-noise burst + low-frequency punch, fast decay
    def shot(i, t):
        env   = math.exp(-t * 28)
        noise = random.uniform(-1, 1)
        punch = math.sin(2 * math.pi * 70 * t) * math.exp(-t * 18)
        return (noise * 0.55 + punch * 0.45) * env * 0.92

    # Reload click: short metallic tick
    def reload_click(i, t):
        env = math.exp(-t * 80)
        return math.sin(2 * math.pi * 900 * t) * env * 0.6

    # Empty-mag click: dry click
    def empty(i, t):
        env = math.exp(-t * 120)
        return math.sin(2 * math.pi * 1400 * t) * env * 0.45

    _gen_wav('gunshot.wav',      shot,         duration=0.13)
    _gen_wav('reload_click.wav', reload_click, duration=0.06)
    _gen_wav('empty_click.wav',  empty,        duration=0.04)

_build_sounds()


def _solid(r, g, b):
    img = PNMImage(1, 1)
    img.set_xel(0, 0, r / 255, g / 255, b / 255)
    p3d = P3DTex()
    p3d.load(img)
    p3d.set_magfilter(P3DTex.FT_nearest)
    p3d.set_minfilter(P3DTex.FT_nearest)
    ut = UrsinaTexture(p3d)
    ut._cached_image = None
    return ut


class _Shell(Entity):
    _TEX = None

    def __init__(self, position, velocity):
        if _Shell._TEX is None:
            _Shell._TEX = _solid(190, 140, 45)
        super().__init__(
            model='cube',
            texture=_Shell._TEX,
            scale=(.012, .012, .042),
            position=position,
        )
        self._vel      = velocity
        self._spin     = random.uniform(400, 700)
        self._lifetime = 5.0
        self._bounced  = False

    def update(self):
        dt = time.dt
        self._lifetime -= dt
        if self._lifetime <= 0:
            destroy(self)
            return

        self._vel.y -= 12.0 * dt
        new_pos = Vec3(
            self.x + self._vel.x * dt,
            self.y + self._vel.y * dt,
            self.z + self._vel.z * dt,
        )

        if new_pos.y <= 0.02:
            new_pos.y = 0.02
            if not self._bounced:
                self._vel.y = abs(self._vel.y) * 0.28
                self._vel.x *= 0.45
                self._vel.z *= 0.45
                self._bounced = True
            else:
                self._vel = Vec3(0, 0, 0)

        self.position = new_pos
        self.rotation_z += self._spin * dt


class Weapon(Entity):
    MAG_SIZE  = 30
    RESERVE   = 150
    FIRE_RATE = 0.085
    DAMAGE    = 30
    RANGE     = 220.0
    HIP_POS   = Vec3( .28, -.22, .40)
    ADS_POS   = Vec3( .00, -.17, .32)

    def __init__(self):
        super().__init__(parent=camera, position=self.HIP_POS)

        def _part(mdl, sc, pos, r, g, b):
            return Entity(parent=self, model=mdl, scale=sc,
                          position=pos, texture=_solid(r, g, b))

        self._body         = _part('cube', (.10,.065,.30), (0,0,0),       32, 32, 32)
        self._barrel       = _part('cube', (.028,.028,.22),(0,.012,.26),   22, 22, 22)
        self._hguard       = _part('cube', (.042,.042,.14),(0,.01,.12),    40, 40, 40)
        self._stock        = _part('cube', (.07,.09,.15),  (0,-.04,-.15),  65, 50, 28)
        self._mag          = _part('cube', (.05,.12,.065), (0,-.09,-.02),  26, 26, 26)
        self._rail         = _part('cube', (.022,.012,.20),(0,.038,.04),   24, 24, 24)
        self._grip         = _part('cube', (.038,.07,.038),(0,-.075,.08),  28, 28, 28)
        self._muzzle_brake = _part('cube', (.038,.038,.04),(0,.012,.39),   18, 18, 18)
        self._flash        = _part('sphere', .06,          (0,.012,.43),  255,220, 80)
        self._flash.enabled  = False
        self._flash2       = _part('sphere', .03,          (0,.012,.43),  255,255,255)
        self._flash2.enabled = False
        # Ejection port marker — right side of receiver, bolt area
        self._eject_port = Entity(parent=self._body, position=(.8, .3, -.15))

        self.ammo      = self.MAG_SIZE
        self.reserve   = self.RESERVE
        self._cooldown = 0.0
        self.reloading = False
        self._reload_t = 0.0
        self._ads      = False
        self._bob_t    = 0.0
        self._sway     = Vec3(0, 0, 0)
        self._recoil   = 0.0

        # Sounds
        self._snd_shot   = base.loader.loadSfx('u_62htdrvg4y-gun-shot-359196.mp3')
        self._snd_reload = base.loader.loadSfx('reload_click.wav')
        self._snd_empty  = base.loader.loadSfx('empty_click.wav')
        self._snd_shot.setVolume(0.9)
        self._snd_reload.setVolume(0.7)
        self._snd_empty.setVolume(0.5)

    def try_shoot(self):
        if self.reloading or self._cooldown > 0:
            return
        if self.ammo == 0:
            self._snd_empty.play()
            self.start_reload()
            return
        self.ammo      -= 1
        self._cooldown  = self.FIRE_RATE
        self._recoil   += 1.4
        self._snd_shot.play()
        self._eject_shell()
        self._flash.enabled  = True
        self._flash2.enabled = True
        invoke(self._hide_flash, delay=.04)

        sp  = .006 if self._ads else .016
        dir = (camera.forward +
               Vec3(random.uniform(-sp, sp), random.uniform(-sp, sp), 0)).normalized()

        ignore_list = [player_ref, self,
                       self._body, self._barrel, self._hguard, self._stock,
                       self._mag, self._rail, self._grip, self._muzzle_brake,
                       self._flash, self._flash2]
        hit = raycast(camera.world_position, dir,
                      distance=self.RANGE, ignore=ignore_list)

        if hit.hit:
            if hasattr(hit.entity, 'take_damage'):
                hit.entity.take_damage(self.DAMAGE)
                if hud_ref:
                    hud_ref.show_hit_marker()
            else:
                decal = Entity(
                    model='quad',
                    color=color.rgba(10, 10, 10, 210),
                    scale=random.uniform(.04, .12),
                    position=hit.world_point + hit.world_normal * .003,
                )
                decal.look_at(decal.position + hit.world_normal)
                destroy(decal, delay=15)

        if hud_ref:
            hud_ref.refresh_ammo(self.ammo, self.reserve)

    def start_reload(self):
        if self.reloading or self.reserve == 0 or self.ammo == self.MAG_SIZE:
            return
        self.reloading = True
        self._reload_t = 2.3
        self._snd_reload.play()
        if hud_ref:
            hud_ref.show_reload(True)

    def update(self):
        dt = time.dt
        if self._cooldown > 0:
            self._cooldown = max(0, self._cooldown - dt)
        if self.reloading:
            self._reload_t -= dt
            if self._reload_t <= 0:
                self._finish_reload()

        self._ads = held_keys['right mouse']
        target    = self.ADS_POS if self._ads else self.HIP_POS
        camera.fov = lerp(camera.fov, 44 if self._ads else 80, dt * 10)

        moving = any(held_keys[k] for k in ('w','a','s','d'))
        if moving and not self.reloading:
            self._bob_t += dt * 7
            sway = Vec3(math.sin(self._bob_t) * .005,
                        abs(math.sin(self._bob_t)) * .003, 0)
        else:
            self._bob_t = lerp(self._bob_t, 0, dt * 4)
            sway = Vec3(0, 0, 0)
        self._sway = Vec3(
            lerp(self._sway.x, sway.x, dt * 8),
            lerp(self._sway.y, sway.y, dt * 8),
            0,
        )

        dest = target + self._sway
        self.position = Vec3(
            lerp(self.position.x, dest.x, dt * 14),
            lerp(self.position.y, dest.y, dt * 14),
            lerp(self.position.z, dest.z, dt * 14),
        )

        if self._recoil > 0:
            kick = min(self._recoil, dt * 22)
            player_ref.camera_pivot.rotation_x = max(
                -89, player_ref.camera_pivot.rotation_x - kick)
            self._recoil = max(0, self._recoil - dt * 16)

    def _eject_shell(self):
        pos = self._eject_port.world_position
        right   = camera.right
        up      = Vec3(0, 1, 0)
        forward = camera.forward
        vel = (right   * random.uniform(1.8, 2.8) +
               up      * random.uniform(1.2, 2.2) +
               forward * random.uniform(-.4, .2))
        _Shell(pos, vel)

    def _hide_flash(self):
        self._flash.enabled  = False
        self._flash2.enabled = False

    def _finish_reload(self):
        needed        = self.MAG_SIZE - self.ammo
        take          = min(needed, self.reserve)
        self.ammo    += take
        self.reserve -= take
        self.reloading = False
        if hud_ref:
            hud_ref.show_reload(False)
            hud_ref.refresh_ammo(self.ammo, self.reserve)
