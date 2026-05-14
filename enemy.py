"""
Enemy AI — humanoid model + animations.
States: PATROL -> ALERTED -> ATTACK -> DEAD
"""
from ursina import *
from ursina import Texture as UrsinaTexture
from panda3d.core import Texture as P3DTex, PNMImage
import random, math, wave, struct, os

# ── Texture helper ────────────────────────────────────────────────────────────
_tex_cache = {}

def _solid(r, g, b):
    if (r, g, b) not in _tex_cache:
        img = PNMImage(1, 1)
        img.set_xel(0, 0, r / 255, g / 255, b / 255)
        p3d = P3DTex()
        p3d.load(img)
        p3d.set_magfilter(P3DTex.FT_nearest)
        p3d.set_minfilter(P3DTex.FT_nearest)
        ut = UrsinaTexture(p3d)
        ut._cached_image = None
        _tex_cache[(r, g, b)] = ut
    return _tex_cache[(r, g, b)]

# ── Sound generation ──────────────────────────────────────────────────────────
def _gen_wav(path, fn, dur=0.10, sr=22050):
    if os.path.exists(path):
        return
    n = int(sr * dur)
    data = [max(-32767, min(32767, int(fn(i / sr) * 32767))) for i in range(n)]
    with wave.open(path, 'w') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr)
        f.writeframes(struct.pack(f'<{n}h', *data))

_gen_wav('enemy_shot.wav',
         lambda t: (random.uniform(-1,1)*0.5 + math.sin(2*math.pi*45*t)*0.5)
                   * math.exp(-t*22) * 0.85)
_gen_wav('enemy_alert.wav',
         lambda t: math.sin(2*math.pi*600*t) * math.exp(-t*18) * 0.5)

_snd_shot  = None
_snd_alert = None

def _load_sounds():
    global _snd_shot, _snd_alert
    if _snd_shot is None:
        _snd_shot = base.loader.loadSfx('enemy_shot.wav')
        _snd_shot.setVolume(0.8)
    if _snd_alert is None:
        _snd_alert = base.loader.loadSfx('enemy_alert.wav')
        _snd_alert.setVolume(0.5)

# ── Helpers ───────────────────────────────────────────────────────────────────
def _face(entity, target_pos):
    dx = target_pos.x - entity.x
    dz = target_pos.z - entity.z
    entity.rotation_y = math.degrees(math.atan2(dx, dz))

# ── Module-level refs ─────────────────────────────────────────────────────────
player_ref  = None
hud_ref     = None
on_kill_cb  = None
all_enemies = []

SPAWN_POINTS = [
    ( 30,1, 45),(-30,1, 45),( 30,1,-45),(-30,1,-45),
    ( 45,1, 15),(-45,1, 15),( 45,1,-15),(-45,1,-15),
    (  0,1, 50),(  0,1,-50),( 50,1,  0),(-50,1,  0),
    ( 38,1, 38),(-38,1, 38),( 38,1,-38),(-38,1,-38),
    ( 20,1, 50),(-20,1, 50),( 20,1,-50),(-20,1,-50),
]

# (sp_patrol, sp_attack, hp, shoot_cd, dmg, det_range, burst)
VARIANTS = {
    'grunt':  (1.8, 3.8, 100, 1.2, 12, 42, 2),
    'heavy':  (1.2, 2.5, 220, 1.8, 22, 34, 1),
    'runner': (2.8, 5.5,  60, 0.9,  8, 46, 3),
}

# ─────────────────────────────────────────────────────────────────────────────
class Enemy(Entity):

    def __init__(self, position, variant='grunt'):
        v = VARIANTS[variant]
        (self.sp_patrol, self.sp_attack, hp,
         self.shoot_cd, self.dmg, self.det_range, self.burst) = v
        self.variant = variant

        # ── Textures by variant ──────────────────────────────────────────
        palettes = {
            'grunt': dict(
                uni  = _solid( 70,  85,  55),
                pant = _solid( 55,  70,  42),
                boot = _solid( 42,  32,  22),
                glv  = _solid( 60,  75,  48),
                skin = _solid(185, 140, 100),
            ),
            'heavy': dict(
                uni  = _solid( 50,  55,  80),
                pant = _solid( 38,  42,  65),
                boot = _solid( 28,  28,  30),
                glv  = _solid( 44,  48,  70),
                skin = _solid(175, 135,  95),
            ),
            'runner': dict(
                uni  = _solid(175, 140,  80),
                pant = _solid(140, 110,  58),
                boot = _solid( 75,  55,  32),
                glv  = _solid(160, 125,  68),
                skin = _solid(190, 145, 105),
            ),
        }
        C = palettes[variant]

        # ── Root entity: invisible collider box ───────────────────────────
        super().__init__(
            model='cube',
            color=color.rgba(0, 0, 0, 0),
            position=position,
            scale=(0.85, 1.85, 0.85),
            collider='box',
        )

        # ── Build humanoid in LOCAL space ─────────────────────────────────
        # Parent scale: (0.85, 1.85, 0.85)
        # local y=0.5 → top of entity   local y=-0.5 → ground
        # local x=±0.5 → sides

        # Torso
        self._torso = Entity(parent=self, model='cube', texture=C['uni'],
                             scale=(.90, .28, .58), position=(0,  .10, 0))
        # Hips
        Entity(parent=self, model='cube', texture=C['pant'],
               scale=(.92, .13, .58), position=(0, -.07, 0))
        # Neck
        Entity(parent=self, model='cube', texture=C['skin'],
               scale=(.18, .04, .18), position=(0,  .27, 0))
        # Head
        self.head = Entity(parent=self, model='sphere', texture=C['skin'],
                           scale=(.44, .20, .44), position=(0,  .36, 0))

        # Variant extras
        if variant == 'heavy':
            # Helmet
            Entity(parent=self, model='cube', texture=_solid(35,35,45),
                   scale=(.50, .09, .50), position=(0, .42, 0))
            Entity(parent=self, model='cube', texture=_solid(30,30,40),
                   scale=(.46, .10, .20), position=(0, .36, -.18))  # visor
            # Chest plate
            Entity(parent=self, model='cube', texture=_solid(40,45,65),
                   scale=(.88, .20, .14), position=(0, .10, -.27))
        elif variant == 'runner':
            # Headband
            Entity(parent=self, model='cube', texture=_solid(180,50,50),
                   scale=(.46, .03, .46), position=(0, .30, 0))

        # ── Leg pivots (pivot = hip joint) ───────────────────────────────
        self._l_leg = Entity(parent=self, position=(-.23, -.12, 0))
        self._r_leg = Entity(parent=self, position=( .23, -.12, 0))

        for pivot, side in ((self._l_leg, -1), (self._r_leg, 1)):
            Entity(parent=pivot, model='cube', texture=C['pant'],
                   scale=(.30, .23, .30), position=(0, -.115, 0))   # thigh
            Entity(parent=pivot, model='cube', texture=C['pant'],
                   scale=(.27, .22, .27), position=(0, -.345, 0))   # shin
            Entity(parent=pivot, model='cube', texture=C['boot'],
                   scale=(.30, .07, .42), position=(0, -.47,  .025)) # boot

        # ── Arm pivots (pivot = shoulder joint) ──────────────────────────
        self._l_arm = Entity(parent=self, position=(-.50, .22, 0))
        self._r_arm = Entity(parent=self, position=( .50, .22, 0))

        for pivot in (self._l_arm, self._r_arm):
            Entity(parent=pivot, model='cube', texture=C['uni'],
                   scale=(.27, .19, .27), position=(0, -.095, 0))   # upper arm
            Entity(parent=pivot, model='cube', texture=C['glv'],
                   scale=(.24, .17, .24), position=(0, -.275, 0))   # forearm
            Entity(parent=pivot, model='cube', texture=C['skin'],
                   scale=(.23, .07, .20), position=(0, -.375, 0))   # hand

        # Muzzle flash on right arm tip
        self._flash = Entity(parent=self._r_arm, model='sphere',
                             texture=_solid(255, 230, 80),
                             scale=.18, position=(0, -.46, .1),
                             enabled=False)

        # Floating HP bar
        self._hbar_bg = Entity(parent=self, model='quad',
                               scale=(1.3, .12), position=(0, .85, 0),
                               billboard=True, color=color.rgba(20,20,20,180),
                               always_on_top=True)
        self._hbar = Entity(parent=self, model='quad',
                            scale=(1.2, .09), position=(0, .85, 0),
                            billboard=True, color=color.rgb(220, 50, 50),
                            always_on_top=True)
        self._hbar.origin_x = -.5
        self._hbar.x        = -.6

        # List of body parts to flash on hit
        self._flash_parts = [self._torso, self.head]

        # ── State ────────────────────────────────────────────────────────
        self.hp         = hp
        self.max_hp     = hp
        self.state      = 'patrol'
        self._shoot_t   = random.uniform(0, self.shoot_cd)
        self._los_t     = random.uniform(0, .3)
        self._lost_t    = 0.0
        self._patrol_t  = 0.0
        self._pre_aim_t = 0.0
        self._burst_left = 0
        self._burst_t    = 0.0
        self._strafe_dir = random.choice((-1, 1))
        self._strafe_t   = 0.0
        self._anim_t     = random.uniform(0, math.pi * 2)  # offset so enemies aren't synced
        self._aim_blend  = 0.0   # 0=idle, 1=fully aimed
        self._patrol_dir = Vec3(random.uniform(-1,1), 0, random.uniform(-1,1)).normalized()

        all_enemies.append(self)

    # ── Damage / death ───────────────────────────────────────────────────────

    def take_damage(self, amount):
        self.hp -= amount
        self._hbar.scale_x = max(0, self.hp / self.max_hp) * 1.2

        # Flash body white briefly
        white = _solid(255, 255, 255)
        orig = [(p, p.texture) for p in self._flash_parts]
        for p, _ in orig:
            p.texture = white
        def _restore(pairs=orig):
            for part, tex in pairs:
                part.texture = tex
        invoke(_restore, delay=.08)

        # Immediately become aggressive
        if self.state == 'patrol':
            self.state      = 'alerted'
            self._pre_aim_t = 0.3
            self._lost_t    = 6.0
        if self.hp <= 0:
            self._die()

    def _die(self):
        self.state    = 'dead'
        self.collider = None
        if self in all_enemies:
            all_enemies.remove(self)
        self.animate_rotation((0, self.rotation_y, 88),
                              duration=.4, curve=curve.linear)
        self.animate_y(-.5, duration=.45, curve=curve.linear)
        destroy(self, delay=8)
        if on_kill_cb:
            on_kill_cb()

    # ── LOS ──────────────────────────────────────────────────────────────────

    def _has_los(self):
        if not player_ref:
            return False
        to_p = player_ref.position - self.position
        dist = to_p.length()
        if dist > self.det_range:
            return False
        check_dist = max(0.1, dist - 1.2)
        hit = raycast(
            self.position + Vec3(0, .9, 0),
            to_p.normalized(),
            distance=check_dist,
            ignore=[self, self.head, self._hbar, self._hbar_bg,
                    self._flash] + all_enemies,
        )
        return not hit.hit

    # ── Movement / AI ────────────────────────────────────────────────────────

    def _patrol_update(self, dt):
        self._patrol_t += dt
        if self._patrol_t > random.uniform(3, 6):
            self._patrol_dir = Vec3(random.uniform(-1,1), 0,
                                    random.uniform(-1,1)).normalized()
            self._patrol_t = 0
        move = self._patrol_dir * self.sp_patrol * dt
        new  = self.position + move
        if abs(new.x) < 54 and abs(new.z) < 54:
            self.position += move
        else:
            self._patrol_dir = -self._patrol_dir
        if move.length() > 0:
            _face(self, self.position + move)
        self._walk_anim(dt, self.sp_patrol)
        self._idle_arms(dt)

    def _alerted_update(self, dt):
        if not player_ref:
            return
        _face(self, player_ref.position)
        self._pre_aim_t -= dt
        self._aim_blend = min(1.0, self._aim_blend + dt * 4)
        self._idle_arms(dt)  # hold position, arms raising
        if self._pre_aim_t <= 0:
            self.state = 'attack'

    def _attack_update(self, dt):
        if not player_ref:
            return
        to_p = player_ref.position - self.position
        dist = to_p.length()

        # Strafe
        self._strafe_t -= dt
        if self._strafe_t <= 0:
            self._strafe_dir = random.choice((-1, 1))
            self._strafe_t   = random.uniform(1.5, 3.0)
        if dist > 6:
            perp = Vec3(-to_p.z, 0, to_p.x).normalized()
            dir  = (to_p.normalized() + perp * self._strafe_dir * 0.4).normalized()
            self.position += dir * self.sp_attack * dt
        _face(self, player_ref.position)

        self._walk_anim(dt, self.sp_attack)
        self._aim_arms(dt)

        # Burst fire
        if self._burst_left > 0:
            self._burst_t -= dt
            if self._burst_t <= 0:
                self._fire(dist)
                self._burst_left -= 1
                self._burst_t = 0.10
            return

        self._shoot_t += dt
        if self._shoot_t >= self.shoot_cd and dist < self.det_range:
            self._shoot_t    = 0
            self._burst_left = self.burst - 1
            self._burst_t    = 0.10
            self._fire(dist)

    # ── Shooting ─────────────────────────────────────────────────────────────

    def _fire(self, dist):
        _load_sounds()
        _snd_shot.play()

        self._flash.enabled = True
        invoke(setattr, self._flash, 'enabled', False, delay=.06)

        origin = self.position + Vec3(0, .9, 0)
        target = (player_ref.position + Vec3(0, 1, 0)) if player_ref else origin

        spread = max(.03, .12 - dist * .002)
        direction = (target - origin).normalized()
        direction += Vec3(random.uniform(-spread, spread),
                          random.uniform(-spread, spread),
                          random.uniform(-spread, spread))
        direction = direction.normalized()

        ignore = [self, self.head, self._hbar, self._hbar_bg,
                  self._flash] + all_enemies
        wall_hit = raycast(origin, direction,
                           distance=max(1, dist - 1.0), ignore=ignore)

        # Tracer
        end    = wall_hit.world_point if wall_hit.hit else origin + direction * 55
        mid    = (origin + end) / 2
        length = (end - origin).length()
        tracer = Entity(model='cube', texture=_solid(255, 235, 140),
                        position=mid, scale=(.025, .025, length))
        tracer.look_at(end)
        destroy(tracer, delay=0.055)

        # Damage
        if not wall_hit.hit and player_ref and hud_ref:
            hud_ref.take_damage(self.dmg)

    # ── Animation ────────────────────────────────────────────────────────────

    def _walk_anim(self, dt, speed):
        """Swing legs + counter-swing arms while walking."""
        self._anim_t += dt * speed * 2.5
        t     = self._anim_t
        swing = math.sin(t) * 30

        self._l_leg.rotation_x =  swing
        self._r_leg.rotation_x = -swing

        # Arms counter-swing while walking; blend with aim when attacking
        walk_arm = math.sin(t) * 18 * (1 - self._aim_blend)
        self._l_arm.rotation_x = -walk_arm
        self._r_arm.rotation_x =  walk_arm

    def _idle_arms(self, dt):
        """Gentle idle sway for arms when not walking."""
        t = time.time() * 1.1 + id(self) * 0.3
        idle = math.sin(t) * 4 * (1 - self._aim_blend)
        self._l_arm.rotation_x = lerp(self._l_arm.rotation_x, idle, dt * 3)
        self._r_arm.rotation_x = lerp(self._r_arm.rotation_x, -idle, dt * 3)

    def _aim_arms(self, dt):
        """Both arms raise forward when aiming."""
        self._aim_blend = min(1.0, self._aim_blend + dt * 5)
        target_r = -40 * self._aim_blend   # right arm (gun arm) raises forward
        target_l = -25 * self._aim_blend   # left arm slightly less
        self._r_arm.rotation_x = lerp(self._r_arm.rotation_x, target_r, dt * 8)
        self._l_arm.rotation_x = lerp(self._l_arm.rotation_x, target_l, dt * 8)

    # ── Main update ──────────────────────────────────────────────────────────

    def update(self):
        if self.state == 'dead':
            return
        dt = time.dt

        # LOS check on 0.25s timer
        self._los_t -= dt
        if self._los_t <= 0:
            self._los_t = .25
            if self._has_los():
                if self.state == 'patrol':
                    _load_sounds()
                    _snd_alert.play()
                    self.state      = 'alerted'
                    self._pre_aim_t = random.uniform(.3, .7)
                self._lost_t = 4.0

        if self.state == 'alerted':
            self._lost_t -= dt
            if self._lost_t <= 0:
                self.state = 'patrol'
            else:
                self._alerted_update(dt)

        elif self.state == 'attack':
            self._lost_t -= dt
            if self._lost_t <= 0:
                self.state      = 'patrol'
                self._aim_blend = 0.0
            else:
                self._attack_update(dt)

        else:
            self._aim_blend = max(0.0, self._aim_blend - dt * 3)
            self._patrol_update(dt)

        # Enemy separation
        for other in all_enemies:
            if other is self:
                continue
            delta = self.position - other.position
            if delta.length() < 1.6:
                push = delta.normalized() * (1.6 - delta.length()) * .5
                self.position += Vec3(push.x, 0, push.z)

# ── Spawn ─────────────────────────────────────────────────────────────────────

def spawn_wave(wave_number):
    count = min(5 + wave_number * 2, 16)
    used  = [e.position for e in all_enemies]
    spots = [Vec3(*s) for s in SPAWN_POINTS]
    random.shuffle(spots)
    spawned = 0
    for spot in spots:
        if spawned >= count:
            break
        if any((spot - u).length() < 5 for u in used):
            continue
        variant = 'grunt'
        if wave_number >= 2 and spawned % 4 == 3:
            variant = 'heavy'
        if wave_number >= 3 and spawned % 5 == 4:
            variant = 'runner'
        Enemy(spot, variant)
        spawned += 1
