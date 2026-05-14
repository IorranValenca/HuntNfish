"""Side-by-side hunting shotgun — 5-shell pump, 8-pellet spread."""
from ursina import *
from game_utils import solid
from effects import blood_splat
import math, random

player_ref      = None
hud_ref         = None
animals_mod_ref = None


class Shotgun(Entity):
    MAG_SIZE  = 5
    DAMAGE    = 26   # per pellet
    PELLETS   = 8
    SPREAD    = 0.060
    RANGE     = 60.0
    FIRE_CD   = 0.80     # pump between shots
    RELOAD_PER = 0.55    # per shell
    HIP_POS   = Vec3(.20, -.18, .28)
    ADS_POS   = Vec3(.00, -.075, .22)
    ADS_FOV   = 55

    def __init__(self):
        super().__init__(parent=camera, position=self.HIP_POS)
        self._gun_root = Entity(parent=self)
        T_BLUED  = solid( 18,  22,  30)
        T_STEEL  = solid( 52,  58,  70)
        T_RECV   = solid( 30,  34,  42)
        T_WOOD   = solid(110,  62,  18)
        T_WOOD2  = solid( 70,  38,  10)
        T_RUBBER = solid( 20,  20,  20)
        T_GOLD   = solid(190, 150,  60)

        def P(mdl, sc, pos, tex, **kw):
            return Entity(parent=self._gun_root, model=mdl,
                          scale=sc, position=pos, texture=tex, **kw)

        # Twin barrels (side-by-side) — wider than rifle barrel
        self._barrel = P('cube', (.042, .034, .380), ( 0, .020, .230), T_BLUED)
        P('cube', (.014, .034, .380), ( 0, .020, .230), T_RECV)    # rib between
        # Front bead
        P('sphere', .009, ( 0, .042, .415), T_GOLD)

        # Receiver block
        self._body = P('cube', (.050, .054, .120), ( 0, .020, .060), T_RECV)
        P('cube', (.044, .010, .118), ( 0, .046, .060), T_BLUED)
        # Trigger guard
        P('cube', (.038, .008, .055), ( 0, -.020, .052), T_STEEL)
        P('cube', (.038, .032, .008), ( 0, -.040, .025), T_STEEL)
        P('cube', (.038, .032, .008), ( 0, -.040, .075), T_STEEL)
        # Twin triggers
        P('cube', (.006, .024, .008), (-.010, -.026, .046), T_GOLD)
        P('cube', (.006, .024, .008), ( .010, -.026, .056), T_GOLD)
        # Tang & opening lever (lever sits behind tang)
        P('cube', (.018, .010, .046), ( 0, .046, .025), T_BLUED)
        P('cube', (.012, .024, .010), ( 0, .060, .020), T_GOLD)
        # Hammer pins
        for hx in (-.010, .010):
            P('sphere', .008, (hx, .030, .010), T_GOLD)

        # Forend (under barrels — wood)
        P('cube', (.054, .034, .200), ( 0, -.018, .240), T_WOOD)
        P('cube', (.060, .015, .200), ( 0, -.034, .240), T_WOOD2)
        # Forend cap
        P('cube', (.058, .036, .020), ( 0, -.018, .340), T_STEEL)

        # Buttstock — straight English style
        self._stock = P('cube', (.040, .085, .060), ( 0, .000, -.025), T_WOOD)
        P('cube', (.044, .120, .180), ( 0, -.012, -.130), T_WOOD)
        P('cube', (.040, .070, .020), ( 0, .010, -.222), T_WOOD2)
        P('cube', (.046, .080, .014), ( 0, .010, -.230), T_RUBBER)

        # Sling studs
        P('cube', (.006, .024, .006), ( 0, -.030, .200), T_STEEL)
        P('cube', (.006, .024, .006), ( 0, -.058, -.190), T_STEEL)

        # Muzzle flash & shell eject port
        self._flash = Entity(parent=self, model='sphere', scale=.075,
                             position=(0, .020, .430),
                             texture=solid(255, 215, 70),
                             enabled=False)
        self._eject = Entity(parent=self, position=(.030, .032, .060))

        # State
        self.ammo      = self.MAG_SIZE
        self.state     = 'ready'    # ready | reloading
        self._fire_cd  = 0.0
        self._reload_t = 0.0
        self._ads      = False
        self._sway     = Vec3(0, 0, 0)
        self._bob_t    = 0.0
        self._recoil   = 0.0

        try:
            self._snd_shot = base.loader.loadSfx('u_62htdrvg4y-gun-shot-359196.mp3')
            self._snd_shot.setVolume(1.0)
        except Exception:
            self._snd_shot = None
        try:
            self._snd_reload = base.loader.loadSfx('RevolverReload.mp3')
            self._snd_reload.setVolume(0.6)
        except Exception:
            self._snd_reload = None

    # ── Input bridge ────────────────────────────────────────────────────────
    def try_shoot(self):
        if self.state != 'ready' or self.ammo == 0 or self._fire_cd > 0:
            return
        self.ammo    -= 1
        self._fire_cd = self.FIRE_CD
        self._recoil  = 4.0
        if self._snd_shot: self._snd_shot.play()
        self._flash.enabled = True
        invoke(setattr, self._flash, 'enabled', False, delay=.06)

        ignore = [player_ref, self, self._gun_root,
                  self._body, self._barrel, self._stock,
                  self._flash, self._eject]

        kill_credits = {}        # entity -> True if we should credit kill
        hit_anything = False
        for _ in range(self.PELLETS):
            sp = self.SPREAD * (0.45 if self._ads else 1.0)
            dir = (camera.forward +
                   Vec3(random.uniform(-sp, sp),
                        random.uniform(-sp, sp), 0)).normalized()
            hit = raycast(camera.world_position, dir,
                          distance=self.RANGE, ignore=ignore)
            if not hit.hit:
                continue
            hit_anything = True
            if hasattr(hit.entity, 'take_damage'):
                target  = hit.entity
                head_y  = target.y + target.scale_y * 0.30
                is_head = hit.world_point.y > head_y
                dmg     = self.DAMAGE * (1.6 if is_head else 1.0)
                dist    = (camera.world_position - hit.world_point).length()
                pre_hp  = getattr(target, 'hp', 1)
                target.take_damage(dmg, camera.world_position)
                blood_splat(hit.world_point, n=6, intensity=0.85)
                died = (getattr(target, 'state', '') == 'dead'
                        or getattr(target, 'hp', 1) <= 0)
                if died and pre_hp > 0:
                    name = getattr(target, '_loot_display_name', 'Animal')
                    kill_credits[target] = (name, dist, is_head)

        if hud_ref:
            hud_ref.register_shot()
            if kill_credits:
                # Only register a single kill for the volley (the biggest target)
                target, (name, dist, is_head) = next(iter(kill_credits.items()))
                hud_ref.register_kill(name, dist, is_head)
            elif hit_anything:
                hud_ref.register_hit(False)
            else:
                hud_ref.register_miss()
            hud_ref.refresh_ammo(self.ammo, self.state, self.MAG_SIZE)

        if animals_mod_ref:
            animals_mod_ref.spook_all(camera.world_position, 60)

    def try_reload(self):
        if self.state != 'ready' or self.ammo >= self.MAG_SIZE:
            return
        self.state     = 'reloading'
        self._reload_t = self.RELOAD_PER
        if self._snd_reload: self._snd_reload.play()
        if hud_ref:
            hud_ref.refresh_ammo(self.ammo, self.state, self.MAG_SIZE)

    # ── Update ──────────────────────────────────────────────────────────────
    def update(self):
        if not self.enabled:
            return
        dt = time.dt
        self._fire_cd = max(0.0, self._fire_cd - dt)

        if self.state == 'reloading':
            self._reload_t -= dt
            if self._reload_t <= 0:
                self.ammo = min(self.MAG_SIZE, self.ammo + 1)
                if hud_ref:
                    hud_ref.refresh_ammo(self.ammo, self.state, self.MAG_SIZE)
                if self.ammo >= self.MAG_SIZE:
                    self.state = 'ready'
                    if hud_ref:
                        hud_ref.refresh_ammo(self.ammo, self.state, self.MAG_SIZE)
                else:
                    self._reload_t = self.RELOAD_PER
                    if self._snd_reload: self._snd_reload.play()

        # ADS
        self._ads = bool(held_keys['right mouse'])
        target = self.ADS_POS if self._ads else self.HIP_POS
        camera.fov = lerp(camera.fov, self.ADS_FOV if self._ads else 80, dt * 10)

        moving = any(held_keys[k] for k in ('w','a','s','d'))
        if moving and not self._ads:
            self._bob_t += dt * 5.5
            sway = Vec3(math.sin(self._bob_t) * .005,
                        abs(math.sin(self._bob_t)) * .003, 0)
        else:
            sway = Vec3(0, 0, 0)
        self._sway = Vec3(lerp(self._sway.x, sway.x, dt*8),
                          lerp(self._sway.y, sway.y, dt*8), 0)
        dest = target + self._sway
        self.position = Vec3(lerp(self.x, dest.x, dt*12),
                             lerp(self.y, dest.y, dt*12),
                             lerp(self.z, dest.z, dt*12))

        # Recoil (vertical camera kick)
        if self._recoil > 0 and player_ref:
            kick = min(self._recoil, dt * 32)
            player_ref.camera_pivot.rotation_x = max(
                -89, player_ref.camera_pivot.rotation_x - kick)
            self._recoil = max(0, self._recoil - dt * 16)

    def on_disable(self):
        self._ads = False
        camera.fov = 80
