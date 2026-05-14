"""Revolver — Colt Python style, 6 shots, fast double-action."""
from ursina import *
from game_utils import solid
from effects import blood_splat
import random, math, wave, struct, os
from panda3d.core import TransparencyAttrib

player_ref      = None
hud_ref         = None
animals_mod_ref = None


def _gen_wav(path, fn, dur=0.14, sr=22050):
    if os.path.exists(path):
        return
    n = int(sr * dur)
    data = [max(-32767, min(32767, int(fn(i / sr) * 32767))) for i in range(n)]
    with wave.open(path, 'w') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr)
        f.writeframes(struct.pack(f'<{n}h', *data))


def _build_sounds():
    def rev_shot(t):
        env   = math.exp(-t * 18)
        noise = random.uniform(-1, 1)
        punch = math.sin(2 * math.pi * 58 * t) * math.exp(-t * 9)
        crack = math.sin(2 * math.pi * 260 * t) * math.exp(-t * 28)
        return (noise * 0.22 + punch * 0.48 + crack * 0.30) * env * 0.94

    def cyl_click_fn(t):
        return math.sin(2 * math.pi * 540 * t) * math.exp(-t * 70) * 0.72

    def swing_fn(t):
        c1 = math.sin(2 * math.pi * 300 * t) * math.exp(-t * 42) * 0.62
        c2 = (math.sin(2 * math.pi * 175 * (t - 0.045)) *
              math.exp(-(t - 0.045) * 38) * 0.38) if t > 0.045 else 0
        return c1 + c2

    _gen_wav('revolver_shot.wav', rev_shot,     dur=0.16)
    _gen_wav('cyl_click.wav',     cyl_click_fn, dur=0.06)
    _gen_wav('cyl_swing.wav',     swing_fn,     dur=0.14)

_build_sounds()


class _RevSmoke(Entity):
    def __init__(self, position, velocity):
        g = random.randint(120, 165)
        super().__init__(
            model='sphere',
            color=color.rgba(g, g, g, 185),
            scale=random.uniform(0.010, 0.030),
            position=position,
        )
        self.setTransparency(TransparencyAttrib.M_alpha)
        self._vel      = velocity
        self._life     = random.uniform(0.65, 1.35)
        self._max_life = self._life
        self._grow     = random.uniform(0.042, 0.095)
        self._g        = g

    def update(self):
        dt = time.dt
        self._life -= dt
        if self._life <= 0:
            destroy(self); return
        self._vel.y  += 0.55 * dt
        self._vel    *= (1.0 - dt * 1.2)
        self.position += self._vel * dt
        gr = self._grow * dt
        self.scale = Vec3(self.scale_x + gr, self.scale_y + gr * 0.75, self.scale_z + gr)
        frac = max(0.0, self._life / self._max_life)
        self.color = color.rgba(self._g, self._g, self._g, int(frac * 168))


class Revolver(Entity):
    MAG_SIZE   = 6
    DAMAGE     = 38           # noticeably less than rifle (85) — close-range sidearm
    RANGE      = 160.0
    HIP_POS    = Vec3(.18, -.15, .26)
    ADS_POS    = Vec3(.002, -.095, .21)
    ADS_FOV    = 52
    RELOAD_DUR = 2.8
    FIRE_CD    = 0.20

    def __init__(self):
        super().__init__(parent=camera, position=self.HIP_POS)

        # Colt Police Positive .38 Spl palette
        BLUED   = solid( 15,  18,  26)   # deep police blue-black
        PLATE   = solid( 22,  27,  36)   # sideplate — slightly lighter
        STEEL   = solid( 50,  58,  70)   # small parts / screws / ejector
        CHROME  = solid(162, 166, 172)   # cylinder (brushed nickel)
        CYL_RIM = solid( 72,  78,  88)   # cylinder rim rings (darker)
        WALNUT  = solid(132,  74,  24)   # grip panels
        WALNT2  = solid( 92,  50,  14)   # darker grain accent
        METAL   = solid( 30,  35,  44)   # backstrap / grip strap

        self._gun_root = Entity(parent=self)

        def P(mdl, sc, pos, tex):
            return Entity(parent=self._gun_root, model=mdl,
                          scale=sc, position=pos, texture=tex)

        # ── Frame body ───────────────────────────────────────────────────
        # Main action block (houses cylinder window)
        P('cube', (.052, .084, .088), ( 0,  .000,  .016), BLUED)
        # Top strap (slim bar over cylinder)
        P('cube', (.046, .016, .092), ( 0,  .050,  .016), BLUED)
        # Barrel stub / barrel seat where barrel threads in
        P('cube', (.046, .030, .020), ( 0,  .030,  .064), BLUED)
        # Grip frame (angled down from action body)
        P('cube', (.044, .088, .036), ( 0, -.042, -.010), BLUED)
        # Recoil shield (back plate of cylinder window)
        P('cube', (.054, .080, .007), ( 0,  .000, -.028), BLUED)
        # Sideplate (right side — slightly lighter to show panel seam)
        P('cube', (.004, .080, .086), (.027,  .000,  .016), PLATE)
        # Crane pivot block
        P('cube', (.010, .022, .010), (.026,  .006,  .016), STEEL)

        # ── Barrel (4-inch, plain round — no Python rib) ─────────────────
        # Main barrel tube — slightly tapered feel via two cubes
        P('cube', (.021, .021, .195), ( 0,  .030,  .172), BLUED)
        P('cube', (.018, .018, .080), ( 0,  .030,  .213), BLUED)   # slight taper near muzzle
        # Small ejector rod shroud underneath (quarter-round lug)
        P('cube', (.013, .010, .178), ( 0,  .010,  .170), BLUED)
        P('cube', (.013, .006, .080), ( 0,  .008,  .213), BLUED)   # thinner near muzzle
        # Muzzle face (slightly wider crown)
        P('cube', (.026, .026, .008), ( 0,  .030,  .267), STEEL)
        # Front sight blade (thin vertical fin)
        P('cube', (.003, .018, .005), ( 0,  .044,  .260), BLUED)
        # Rear sight notch (shallow groove block)
        P('cube', (.022, .006, .008), ( 0,  .044,  .058), STEEL)

        # ── Cylinder (.38 Spl — smaller diameter than .357 Python) ───────
        self._cylinder = Entity(
            parent=self._gun_root,
            model='cylinder', texture=CHROME,
            scale=(.064, .060, .060),
            position=(0, .006, .016),
            rotation_x=90,
        )
        # Front / rear rims
        P('cube', (.068, .068, .005), ( 0, .006,  .048), CYL_RIM)
        P('cube', (.068, .068, .005), ( 0, .006, -.014), CYL_RIM)
        # Cylinder flute shadow strips (suggest flutes on surface)
        for ang in range(0, 360, 60):
            rad = math.radians(ang)
            ox  =  math.cos(rad) * 0.034
            oy  =  math.sin(rad) * 0.034
            P('cube', (.005, .005, .046), (ox, .006 + oy, .016), BLUED)
        # Ejector rod
        P('cube', (.007, .007, .058), ( 0, -.020,  .016), STEEL)
        # Crane arm (yoke that swings cylinder out)
        P('cube', (.004, .036, .010), (.026,  .006,  .016), STEEL)

        # ── Trigger guard (oval/rounded — wider gap than Python) ──────────
        P('cube', (.032, .006, .054), ( 0, -.046,  .034), BLUED)   # front bar
        P('cube', (.032, .034, .007), ( 0, -.074,  .008), BLUED)   # bottom arc
        P('cube', (.032, .006, .020), ( 0, -.074,  .038), BLUED)   # rear bar
        # Trigger guard corner radius suggestions
        P('cube', (.032, .018, .009), ( 0, -.062,  .060), BLUED)   # front-top curve
        P('cube', (.032, .018, .009), ( 0, -.062, -.014), BLUED)   # rear-top curve

        # ── Trigger & hammer ─────────────────────────────────────────────
        P('cube', (.006, .022, .010), ( 0, -.050,  .026), STEEL)   # trigger blade
        # Hammer (compact — Police Positive has smaller spur than Python)
        P('cube', (.018, .022, .015), ( 0,  .032,  .058), BLUED)   # hammer body
        P('cube', (.020, .008, .012), ( 0,  .044,  .052), STEEL)   # serrated spur face
        P('cube', (.016, .012, .010), ( 0,  .040,  .060), BLUED)   # spur body

        # ── Grip — round butt, compact walnut panels ──────────────────────
        # Upper grip panels
        P('cube', (.040, .102, .072), ( 0, -.042, -.048), WALNUT)
        # Lower grip (narrows toward butt)
        P('cube', (.038, .076, .055), ( 0, -.024, -.082), WALNUT)
        # Round butt — sphere for the curved bottom end
        P('sphere',(.040, .030, .046), ( 0, -.010, -.116), WALNUT)
        # Grip grain accent (darker stripe down back)
        P('cube', (.010, .095, .010), ( 0, -.020, -.040), WALNT2)
        # Metal backstrap (thin blued strap behind grip)
        P('cube', (.036, .108, .009), ( 0,  .000, -.084), METAL)
        P('cube', (.034, .030, .008), ( 0,  .000, -.118), METAL)   # butt cap
        # Grip screws (silver medallions)
        P('sphere', .007, ( .021, -.038, -.052), STEEL)
        P('sphere', .007, (-.021, -.038, -.052), STEEL)

        # ── Muzzle flash ─────────────────────────────────────────────────
        self._flash = Entity(parent=self, model='sphere', scale=.030,
                             position=(0, .030, .278),
                             texture=solid(255, 215, 75))
        self._flash.enabled = False

        self._eject_port = Entity(parent=self, position=(.038, .006, .016))

        # ── State ─────────────────────────────────────────────────────────
        self.ammo      = self.MAG_SIZE
        self.state     = 'ready'
        self._phase_t  = 0.0
        self._fire_cd  = 0.0
        self._recoil   = 0.0
        self._ads      = False
        self._bob_t    = 0.0
        self._sway     = Vec3(0, 0, 0)
        self._cyl_rot  = 0.0

        self._snd_shot  = base.loader.loadSfx('Revolvershot.mp3')
        self._snd_click = base.loader.loadSfx('cyl_click.wav')
        self._snd_swing = base.loader.loadSfx('RevolverReload.mp3')
        self._snd_shot.setVolume(1.0)
        self._snd_click.setVolume(0.75)
        self._snd_swing.setVolume(0.90)

    # ── Shooting ─────────────────────────────────────────────────────────

    def try_shoot(self):
        if self.state != 'ready' or self.ammo == 0 or self._fire_cd > 0:
            return
        self.ammo    -= 1
        self._fire_cd = self.FIRE_CD
        self._recoil  = 2.2
        self._snd_shot.play()
        self._snd_click.play()
        self._flash.enabled = True
        invoke(setattr, self._flash, 'enabled', False, delay=.04)
        self._spawn_smoke()

        self._cyl_rot            += 60.0
        self._cylinder.rotation_z = self._cyl_rot

        sp  = .013 if self._ads else .018
        dir = (camera.forward +
               Vec3(random.uniform(-sp, sp), random.uniform(-sp, sp), 0)).normalized()
        ignore = [player_ref, self, self._gun_root, self._flash, self._eject_port]
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
                        n=18 if is_head else 11,
                        intensity=1.3 if is_head else 0.9)

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
                               scale=random.uniform(.04, .12),
                               position=hit.world_point + hit.world_normal * .003)
                decal.look_at(decal.position + hit.world_normal)
                destroy(decal, delay=20)

        if animals_mod_ref:
            animals_mod_ref.spook_all(camera.world_position, 50)
        if hud_ref:
            hud_ref.refresh_ammo(self.ammo, self.state, self.MAG_SIZE)

    def try_reload(self):
        if self.state != 'ready' or self.ammo >= self.MAG_SIZE:
            return
        self.state    = 'reloading'
        self._phase_t = self.RELOAD_DUR
        self._snd_swing.play()
        if hud_ref: hud_ref.refresh_ammo(self.ammo, self.state, self.MAG_SIZE)

    def _spawn_smoke(self):
        origin = self._flash.world_position
        fwd    = camera.forward
        for _ in range(6):
            vel = (fwd * random.uniform(0.3, 1.1) +
                   Vec3(random.uniform(-0.35, 0.35),
                        random.uniform(0.06, 0.40),
                        random.uniform(-0.35, 0.35)))
            offset = Vec3(random.uniform(-0.02, 0.02),
                          random.uniform(-0.01, 0.02),
                          random.uniform(-0.02, 0.02))
            _RevSmoke(origin + offset, vel)

    # ── Update ────────────────────────────────────────────────────────────

    def update(self):
        dt = time.dt
        self._fire_cd = max(0.0, self._fire_cd - dt)

        if self.state == 'reloading':
            self._phase_t -= dt
            if self._phase_t <= 0:
                self.ammo     = self.MAG_SIZE
                self.state    = 'ready'
                self._cyl_rot = 0.0
                self._cylinder.rotation_z = 0.0
                if hud_ref: hud_ref.refresh_ammo(self.ammo, self.state, self.MAG_SIZE)

        prev_ads  = self._ads
        self._ads = bool(held_keys['right mouse'])

        target   = self.ADS_POS if self._ads else self.HIP_POS
        fov_tgt  = self.ADS_FOV if self._ads else 80
        camera.fov = lerp(camera.fov, fov_tgt, dt * 12)

        moving = any(held_keys[k] for k in ('w', 'a', 's', 'd'))
        if moving and not self._ads:
            self._bob_t += dt * 6
            sway = Vec3(math.sin(self._bob_t) * .005,
                        abs(math.sin(self._bob_t)) * .003, 0)
        else:
            sway = Vec3(0, 0, 0)
        self._sway = Vec3(lerp(self._sway.x, sway.x, dt * 8),
                          lerp(self._sway.y, sway.y, dt * 8), 0)
        dest = target + self._sway
        self.position = Vec3(lerp(self.x, dest.x, dt * 14),
                             lerp(self.y, dest.y, dt * 14),
                             lerp(self.z, dest.z, dt * 14))

        if self._recoil > 0 and player_ref:
            kick = min(self._recoil, dt * 20)
            player_ref.camera_pivot.rotation_x = max(
                -89, player_ref.camera_pivot.rotation_x - kick)
            self._recoil = max(0, self._recoil - dt * 16)

    def on_disable(self):
        self._ads  = False
        camera.fov = 80
