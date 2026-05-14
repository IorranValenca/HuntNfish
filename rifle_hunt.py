"""Bolt-action hunting rifle — Remington 700 style with proper scope view."""
from ursina import *
from game_utils import solid
from effects import blood_splat
import random, math, wave, struct, os
from panda3d.core import PNMImage, Texture as P3DTex, TransparencyAttrib
from ursina import Texture as UrsinaTexture

player_ref      = None
hud_ref         = None
animals_mod_ref = None


def _gen_wav(path, fn, dur=0.18, sr=22050):
    if os.path.exists(path):
        return
    n = int(sr * dur)
    data = [max(-32767, min(32767, int(fn(i / sr) * 32767))) for i in range(n)]
    with wave.open(path, 'w') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr)
        f.writeframes(struct.pack(f'<{n}h', *data))


def _build_sounds():
    def rifle_shot(t):
        env   = math.exp(-t * 14)
        noise = random.uniform(-1, 1)
        punch = math.sin(2 * math.pi * 38 * t) * math.exp(-t * 10)
        boom  = math.sin(2 * math.pi * 18 * t) * math.exp(-t * 6)
        return (noise * 0.35 + punch * 0.40 + boom * 0.25) * env * 0.95

    def bolt_back_fn(t):
        return math.sin(2 * math.pi * 240 * t) * math.exp(-t * 55) * 0.65

    def bolt_fwd_fn(t):
        return math.sin(2 * math.pi * 310 * t) * math.exp(-t * 58) * 0.80

    def insert_fn(t):
        c1 = math.sin(2 * math.pi * 480 * t) * math.exp(-t * 80) * 0.55
        c2 = (math.sin(2 * math.pi * 380 * (t - 0.06)) *
              math.exp(-(t - 0.06) * 70) * 0.45) if t > 0.06 else 0
        return c1 + c2

    # rifle_shot uses the real MP3 file — no WAV generation needed
    _gen_wav('bolt_back.wav',     bolt_back_fn, dur=0.12)
    _gen_wav('bolt_fwd.wav',      bolt_fwd_fn,  dur=0.10)
    _gen_wav('bullet_insert.wav', insert_fn,    dur=0.14)

_build_sounds()


def _make_scope_overlay_tex(aspect=16/9, size=256, scope_r=0.30):
    """Black RGBA texture with a circular transparent cutout.
    The circle is computed in screen-space so it appears perfectly round."""
    img = PNMImage(size, size)
    img.add_alpha()
    img.fill(0, 0, 0)
    img.alpha_fill(1.0)
    soft = scope_r * 1.08
    for y in range(size):
        for x in range(size):
            sx = (x / size - 0.5) * aspect
            sy = (y / size - 0.5)
            d  = math.sqrt(sx * sx + sy * sy)
            if d < scope_r:
                img.set_alpha(x, y, 0.0)
            elif d < soft:
                img.set_alpha(x, y, min(1.0, (d - scope_r) / (soft - scope_r)))
    p3d = P3DTex()
    p3d.load(img)
    p3d.set_magfilter(P3DTex.FT_linear)
    p3d.set_minfilter(P3DTex.FT_linear)
    ut = UrsinaTexture(p3d)
    ut._cached_image = None
    return ut


class _Shell(Entity):
    _TEX = None
    def __init__(self, position, velocity):
        if _Shell._TEX is None:
            _Shell._TEX = solid(195, 145, 48)
        super().__init__(model='cube', texture=_Shell._TEX,
                         scale=(.013, .013, .048), position=position)
        self._vel      = velocity
        self._spin     = random.uniform(350, 650)
        self._lifetime = 6.0
        self._bounced  = False

    def update(self):
        dt = time.dt
        self._lifetime -= dt
        if self._lifetime <= 0:
            destroy(self); return
        self._vel.y -= 12.0 * dt
        new_pos = Vec3(self.x + self._vel.x * dt,
                       self.y + self._vel.y * dt,
                       self.z + self._vel.z * dt)
        if new_pos.y <= 0.02:
            new_pos.y = 0.02
            if not self._bounced:
                self._vel.y = abs(self._vel.y) * 0.28
                self._vel.x *= 0.4; self._vel.z *= 0.4
                self._bounced = True
            else:
                self._vel = Vec3(0, 0, 0)
        self.position = new_pos
        self.rotation_z += self._spin * dt


class _SmokePuff(Entity):
    def __init__(self, position, velocity):
        g = random.randint(128, 175)
        super().__init__(
            model='sphere',
            color=color.rgba(g, g, g, 200),
            scale=random.uniform(0.015, 0.042),
            position=position,
        )
        self.setTransparency(TransparencyAttrib.M_alpha)
        self._vel      = velocity
        self._life     = random.uniform(0.8, 1.7)
        self._max_life = self._life
        self._grow     = random.uniform(0.055, 0.130)
        self._g        = g

    def update(self):
        dt = time.dt
        self._life -= dt
        if self._life <= 0:
            destroy(self); return
        self._vel.y += 0.55 * dt          # buoyancy
        self._vel   *= (1.0 - dt * 1.1)  # drag / turbulence damping
        self.position += self._vel * dt
        gr = self._grow * dt
        self.scale = Vec3(self.scale_x + gr,
                          self.scale_y + gr * 0.75,
                          self.scale_z + gr)
        frac = max(0.0, self._life / self._max_life)
        self.color = color.rgba(self._g, self._g, self._g, int(frac * 185))


class BoltRifle(Entity):
    MAG_SIZE = 5
    DAMAGE   = 85
    RANGE    = 400.0
    HIP_POS  = Vec3(.19, -.14, .25)
    ADS_POS  = Vec3(.00, -.070, .18)
    ADS_FOV  = 8      # strong zoom through scope

    BOLT_BACK_DUR = 0.26
    BOLT_FWD_DUR  = 0.22
    INSERT_DUR    = 0.58
    CLOSE_DUR     = 0.24

    _BZ_HOME   =  0.00
    _BZ_BACK   = -0.130
    _BR_CLOSED =  0.0
    _BR_OPEN   =  70.0

    def __init__(self):
        super().__init__(parent=camera, position=self.HIP_POS)

        # ── Gun model root ────────────────────────────────────────────────
        self._gun_root = Entity(parent=self)

        def P(mdl, sc, pos, tex, **kw):
            return Entity(parent=self._gun_root, model=mdl,
                          scale=sc, position=pos, texture=tex, **kw)
        def Cy(sc, pos, tex):
            # sc = (x_diam, length, z_diam); cube wants (x, z_diam, length)
            return Entity(parent=self._gun_root, model='cube',
                          scale=(sc[0], sc[2], sc[1]), position=pos, texture=tex)

        # ── Palette ──────────────────────────────────────────────────────
        BLUED  = solid( 10,  14,  22)
        RECEIV = solid( 22,  26,  36)
        STEEL  = solid( 52,  58,  70)
        CHROME = solid(158, 163, 172)
        WALNUT = solid(115,  64,  18)
        SCOPEB = solid( 16,  20,  30)
        SCOPG  = solid( 18,  52,  80)
        RUBBER = solid( 20,  20,  20)

        # ── Barrel ────────────────────────────────────────────────────────
        self._barrel = Cy((.026, .200, .026), ( 0, .016, .160), BLUED)
        Cy((.018, .110, .018),                ( 0, .016, .320), BLUED)
        # Front sight
        P('cube', (.014, .014, .016),         ( 0, .032, .380), STEEL)

        # ── Receiver ─────────────────────────────────────────────────────
        self._body = P('cube', (.048, .048, .102), ( 0, .016, .058), RECEIV)
        P('cube', (.006, .030, .058),              (.028, .020, .068), STEEL)  # ejection port
        Cy((.052, .016, .052),                     ( 0, .016, .110), BLUED)    # barrel nut

        # ── Bolt ─────────────────────────────────────────────────────────
        self._bolt_group = Entity(parent=self._gun_root)
        self._bolt = Entity(parent=self._bolt_group, model='cube', texture=CHROME,
                            scale=(.020, .020, .082), position=(0, .016, .060))
        Entity(parent=self._bolt_group, model='cube', texture=STEEL,
               scale=(.034, .009, .009), position=(.022, .018, .044))
        Entity(parent=self._bolt_group, model='cube', texture=STEEL,
               scale=(.009, .030, .009), position=(.040, .004, .044))
        Entity(parent=self._bolt_group, model='sphere', texture=CHROME,
               scale=.022, position=(.040, -.010, .044))

        # ── Magazine ─────────────────────────────────────────────────────
        P('cube', (.032, .054, .050),              ( 0, -.018, .048), RECEIV)

        # ── Trigger guard + trigger ────────────────────────────────────────
        P('cube', (.036, .007, .058),              ( 0, -.024, .048), STEEL)
        P('cube', (.036, .034, .008),              ( 0, -.044, .020), STEEL)
        P('cube', (.036, .034, .008),              ( 0, -.044, .062), STEEL)
        P('cube', (.008, .036, .010),              ( 0, -.032, .040), CHROME)  # trigger

        # ── Picatinny rail ─────────────────────────────────────────────────
        P('cube', (.030, .011, .098),              ( 0, .044, .055), STEEL)

        # ── Scope rings ───────────────────────────────────────────────────
        for _rz in (.088, .024):
            Cy((.034, .018, .034),                 ( 0, .062, _rz), STEEL)
            P('cube', (.044, .007, .016),          ( 0, .078, _rz), CHROME)

        # ── Scope ─────────────────────────────────────────────────────────
        Cy((.032, .098, .032),                     ( 0, .068, .055), SCOPEB)   # main tube
        Cy((.016, .020, .016),                     ( 0, .084, .056), SCOPEB)   # elevation turret
        P('cube', (.024, .020, .020),              (.022, .074, .042), SCOPEB) # windage turret
        Cy((.044, .030, .044),                     ( 0, .068, .106), SCOPEB)   # obj bell
        P('sphere', (.046, .009, .046),            ( 0, .068, .124), SCOPG)    # obj lens
        Cy((.040, .026, .040),                     ( 0, .068, .010), SCOPEB)   # eyepiece
        P('sphere', (.030, .007, .030),            ( 0, .068, -.006), SCOPG)   # eye lens

        # ── Stock ─────────────────────────────────────────────────────────
        P('cube', (.038, .028, .200),              ( 0, -.002, .090), WALNUT)  # forend
        P('cube', (.044, .044, .114),              ( 0,  .010, .002), WALNUT)  # bedding
        self._stock = P('cube', (.034, .090, .042), ( 0, -.032, -.012), WALNUT) # grip
        P('cube', (.036, .052, .048),              ( 0, -.002, -.046), WALNUT) # wrist
        P('cube', (.030, .042, .122),              ( 0,  .026, -.106), WALNUT) # cheekpiece
        P('cube', (.034, .062, .140),              ( 0,  .000, -.116), WALNUT) # main stock
        P('cube', (.034, .072, .018),              ( 0,  .004, -.190), WALNUT) # butt
        P('cube', (.036, .074, .014),              ( 0,  .004, -.202), RUBBER) # buttpad

        # ── Muzzle flash & eject ─────────────────────────────────────────
        self._flash = Entity(parent=self, model='sphere', scale=.060,
                             position=(0, .016, .420),
                             texture=solid(255, 215, 70))
        self._flash.enabled = False
        self._muzzle = self._flash
        self._eject  = Entity(parent=self, position=(.030, .022, .068))

        # ── Scope overlay (camera.ui) ─────────────────────────────────────
        asp = window.aspect_ratio
        _ov_tex = _make_scope_overlay_tex(aspect=asp, size=128, scope_r=0.30)
        self._scope_overlay = Entity(parent=camera.ui, model='quad',
                                     texture=_ov_tex, scale=(asp, 1.0),
                                     z=-0.02, enabled=False)
        self._scope_overlay.setTransparency(TransparencyAttrib.M_alpha)

        # Duplex reticle (thin inner lines + thick outer posts)
        RT = solid(8, 8, 8)
        r_args = dict(model='quad', texture=RT, z=-0.01, enabled=False)
        self._ret_hl = Entity(parent=camera.ui, scale=(.110, .0020),
                              position=(-.125, 0), **r_args)
        self._ret_hr = Entity(parent=camera.ui, scale=(.110, .0020),
                              position=( .125, 0), **r_args)
        self._ret_vt = Entity(parent=camera.ui, scale=(.0020, .100),
                              position=(0,  .115), **r_args)
        self._ret_vb = Entity(parent=camera.ui, scale=(.0020, .100),
                              position=(0, -.115), **r_args)
        # Fine centre lines
        self._ret_hc = Entity(parent=camera.ui, scale=(.060, .0010),
                              **r_args)
        self._ret_vc = Entity(parent=camera.ui, scale=(.0010, .060),
                              **r_args)
        self._scope_ui = [self._scope_overlay,
                          self._ret_hl, self._ret_hr,
                          self._ret_vt, self._ret_vb,
                          self._ret_hc, self._ret_vc]

        # ── State ────────────────────────────────────────────────────────
        self.ammo  = self.MAG_SIZE
        self.state = 'ready'
        self._phase_t  = 0.0
        self._recoil   = 0.0
        self._ads      = False
        self._bob_t    = 0.0
        self._sway     = Vec3(0, 0, 0)
        self._r_hold_t = 0.0
        self._r_prev   = False
        self._r_loading = False

        self._snd_shot   = base.loader.loadSfx('u_62htdrvg4y-gun-shot-359196.mp3')
        self._snd_back   = base.loader.loadSfx('bolt_back.wav')
        self._snd_fwd    = base.loader.loadSfx('dragon-studio-gun-reload-2-504027.mp3')
        self._snd_insert  = base.loader.loadSfx('bullet_insert.wav')
        self._snd_chamber = base.loader.loadSfx('u_96j4yp891e-chamber-368898.mp3')
        self._snd_shot.setVolume(1.0)
        self._snd_back.setVolume(0.85)
        self._snd_fwd.setVolume(0.85)
        self._snd_insert.setVolume(0.75)
        self._snd_chamber.setVolume(0.90)

    # ── Shooting ─────────────────────────────────────────────────────────

    def try_shoot(self):
        if self.state != 'ready' or self.ammo == 0:
            return
        self.ammo   -= 1
        self.state   = 'needs_bolt'
        self._recoil = 3.5
        self._snd_shot.play()
        self._flash.enabled = True
        invoke(setattr, self._flash, 'enabled', False, delay=.05)
        self._eject_shell()
        self._spawn_smoke()

        sp  = .0008 if self._ads else .009
        dir = (camera.forward +
               Vec3(random.uniform(-sp, sp), random.uniform(-sp, sp), 0)).normalized()
        ignore = [player_ref, self, self._gun_root,
                  self._body, self._barrel, self._stock, self._bolt,
                  self._flash, self._muzzle, self._eject]
        hit = raycast(camera.world_position, dir, distance=self.RANGE, ignore=ignore)

        if hud_ref: hud_ref.register_shot()

        if hit.hit and hasattr(hit.entity, 'take_damage'):
            target  = hit.entity
            head_y  = target.y + target.scale_y * 0.30
            is_head = hit.world_point.y > head_y
            dmg     = self.DAMAGE * (1.7 if is_head else 1.0)
            dist    = (camera.world_position - hit.world_point).length()

            target.take_damage(dmg, camera.world_position)
            blood_splat(hit.world_point,
                        n=22 if is_head else 13,
                        intensity=1.4 if is_head else 1.0)

            died = getattr(target, 'state', '') == 'dead' \
                   or getattr(target, 'hp', 1) <= 0
            if hud_ref:
                if died:
                    name = getattr(target, '_loot_display_name', 'Animal')
                    hud_ref.register_kill(name, dist, is_head)
                else:
                    hud_ref.register_hit(is_head)
        else:
            if hud_ref: hud_ref.register_miss()
            if hit.hit:
                decal = Entity(model='quad', color=color.rgba(10, 10, 10, 200),
                               scale=random.uniform(.04, .14),
                               position=hit.world_point + hit.world_normal * .003)
                decal.look_at(decal.position + hit.world_normal)
                destroy(decal, delay=20)

        if animals_mod_ref:
            animals_mod_ref.spook_all(camera.world_position, 70)
        if hud_ref:
            hud_ref.refresh_ammo(self.ammo, self.state)

    # ── Animation helpers ────────────────────────────────────────────────

    def _set_bolt(self, z_off, rot_z):
        self._bolt_group.z          = z_off
        self._bolt_group.rotation_z = rot_z

    def _start_bolt_back(self):
        self.state    = 'bolt_back'
        self._phase_t = self.BOLT_BACK_DUR
        self._snd_back.play()

    def _start_bolt_fwd(self):
        self.state    = 'bolt_forward'
        self._phase_t = self.BOLT_FWD_DUR
        self._eject_shell()
        self._snd_fwd.play()

    def _open_for_loading(self):
        self.state      = 'loading_open'
        self._r_loading = True
        self._set_bolt(self._BZ_BACK, self._BR_OPEN)
        self._snd_back.play()
        if hud_ref: hud_ref.refresh_ammo(self.ammo, self.state)

    def _start_insert(self):
        self.state    = 'inserting'
        self._phase_t = self.INSERT_DUR
        self._snd_chamber.play()

    def _finish_insert(self):
        self.ammo = min(self.ammo + 1, self.MAG_SIZE)
        if hud_ref: hud_ref.refresh_ammo(self.ammo, 'loading_open')
        if self.ammo >= self.MAG_SIZE:
            self._close_bolt()
        else:
            self.state = 'loading_open'

    def _close_bolt(self):
        self.state      = 'bolt_close'
        self._phase_t   = self.CLOSE_DUR
        self._r_loading = False
        self._snd_fwd.play()

    def _spawn_smoke(self):
        origin = self._flash.world_position
        fwd    = camera.forward
        for _ in range(10):
            vel = (fwd * random.uniform(0.4, 1.6) +
                   Vec3(random.uniform(-0.45, 0.45),
                        random.uniform(0.08, 0.55),
                        random.uniform(-0.45, 0.45)))
            offset = Vec3(random.uniform(-0.03, 0.03),
                          random.uniform(-0.01, 0.03),
                          random.uniform(-0.03, 0.03))
            _SmokePuff(origin + offset, vel)

    def _eject_shell(self):
        pos = self._eject.world_position
        vel = (camera.right  * random.uniform(1.6, 2.6) +
               Vec3(0, 1, 0) * random.uniform(1.0, 2.0) +
               camera.forward * random.uniform(-.5, .2))
        _Shell(pos, vel)

    # ── Main update ──────────────────────────────────────────────────────

    def update(self):
        dt = time.dt

        # ── R key hold / tap detection ────────────────────────────────
        r = bool(held_keys['r'])
        if r and not self._r_prev:
            self._r_hold_t = 0.0
        elif r:
            self._r_hold_t += dt
            if (self._r_hold_t > 0.45 and not self._r_loading
                    and self.state in ('needs_bolt', 'empty', 'ready')
                    and self.ammo < self.MAG_SIZE):
                if self.state == 'needs_bolt':
                    self._eject_shell()
                self._open_for_loading()
        elif not r and self._r_prev:
            if self._r_loading:
                if self.state == 'loading_open':
                    self._close_bolt()
            elif self._r_hold_t < 0.45:
                if self.state == 'needs_bolt':
                    self._start_bolt_back()
                elif self.state in ('empty', 'ready') and self.ammo < self.MAG_SIZE:
                    self.state    = 'reloading'
                    self._phase_t = 3.2
                    if hud_ref: hud_ref.refresh_ammo(self.ammo, 'reloading')
            self._r_hold_t = 0.0
        self._r_prev = r

        # ── Animation states ──────────────────────────────────────────
        if self.state == 'bolt_back':
            self._phase_t -= dt
            frac = 1.0 - max(0.0, self._phase_t) / self.BOLT_BACK_DUR
            self._set_bolt(lerp(self._BZ_HOME, self._BZ_BACK, frac),
                           lerp(self._BR_CLOSED, self._BR_OPEN, frac))
            if self._phase_t <= 0:
                self._set_bolt(self._BZ_BACK, self._BR_OPEN)
                self._start_bolt_fwd()

        elif self.state == 'bolt_forward':
            self._phase_t -= dt
            frac = 1.0 - max(0.0, self._phase_t) / self.BOLT_FWD_DUR
            self._set_bolt(lerp(self._BZ_BACK, self._BZ_HOME, frac),
                           lerp(self._BR_OPEN, self._BR_CLOSED, frac))
            if self._phase_t <= 0:
                self._set_bolt(self._BZ_HOME, self._BR_CLOSED)
                self.state = 'ready' if self.ammo > 0 else 'empty'
                if hud_ref: hud_ref.refresh_ammo(self.ammo, self.state)

        elif self.state == 'loading_open':
            if r and self.ammo < self.MAG_SIZE:
                self._start_insert()

        elif self.state == 'inserting':
            self._phase_t -= dt
            nudge = math.sin(self._phase_t / self.INSERT_DUR * math.pi) * 0.007
            self._set_bolt(self._BZ_BACK + nudge, self._BR_OPEN)
            if self._phase_t <= 0:
                self._set_bolt(self._BZ_BACK, self._BR_OPEN)
                self._finish_insert()

        elif self.state == 'bolt_close':
            self._phase_t -= dt
            frac = 1.0 - max(0.0, self._phase_t) / self.CLOSE_DUR
            self._set_bolt(lerp(self._BZ_BACK, self._BZ_HOME, frac),
                           lerp(self._BR_OPEN, self._BR_CLOSED, frac))
            if self._phase_t <= 0:
                self._set_bolt(self._BZ_HOME, self._BR_CLOSED)
                self.state      = 'ready'
                self._r_loading = False
                if hud_ref: hud_ref.refresh_ammo(self.ammo, self.state)

        elif self.state == 'reloading':
            self._phase_t -= dt
            if self._phase_t <= 0:
                self.ammo  = self.MAG_SIZE
                self.state = 'ready'
                if hud_ref: hud_ref.refresh_ammo(self.ammo, self.state)

        # ── ADS — scope view ─────────────────────────────────────────
        prev_ads = self._ads
        self._ads = bool(held_keys['right mouse'])
        if self._ads != prev_ads:
            self._gun_root.enabled = not self._ads
            for e in self._scope_ui:
                e.enabled = self._ads

        target = self.ADS_POS if self._ads else self.HIP_POS
        fov_target = self.ADS_FOV if self._ads else 80
        camera.fov = lerp(camera.fov, fov_target, dt * 12)

        # ── Bob / sway (hip only) ─────────────────────────────────────
        moving = any(held_keys[k] for k in ('w', 'a', 's', 'd'))
        if moving and not self._ads:
            self._bob_t += dt * 6
            sway = Vec3(math.sin(self._bob_t) * .004,
                        abs(math.sin(self._bob_t)) * .002, 0)
        else:
            sway = Vec3(0, 0, 0)
        self._sway = Vec3(lerp(self._sway.x, sway.x, dt * 8),
                          lerp(self._sway.y, sway.y, dt * 8), 0)
        dest = target + self._sway
        self.position = Vec3(lerp(self.x, dest.x, dt * 12),
                             lerp(self.y, dest.y, dt * 12),
                             lerp(self.z, dest.z, dt * 12))

        # ── Recoil ────────────────────────────────────────────────────
        if self._recoil > 0 and player_ref:
            kick = min(self._recoil, dt * 28)
            player_ref.camera_pivot.rotation_x = max(
                -89, player_ref.camera_pivot.rotation_x - kick)
            self._recoil = max(0, self._recoil - dt * 14)

    def on_disable(self):
        # Hide scope UI when switching tools
        for e in self._scope_ui:
            e.enabled = False
        self._gun_root.enabled = True
        self._ads = False
        camera.fov = 80
