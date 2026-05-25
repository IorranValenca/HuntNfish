"""Deer, Rabbit, Wolf, Fox, Bear AI."""
from ursina import *
from game_utils import solid
import random, math

player_ref         = None
player_damage_fn   = None   # callable(amount) — set from main_hunt.py
player_noise_mult  = 1.0    # 1.0 = walking, 1.5 = sprinting, <1 = crouching

all_deer    = []
all_rabbits = []
all_wolves  = []
all_foxes   = []
all_bears   = []
all_birds   = []
lootable_deer = []   # shared pool for all lootable animals


def _face(entity, target_pos):
    dx = target_pos.x - entity.x
    dz = target_pos.z - entity.z
    entity.rotation_y = math.degrees(math.atan2(dx, dz))


def _hpbar(parent, width=1.4, y_off=0.75):
    bg = Entity(parent=parent, model='quad',
                color=color.rgba(20, 20, 20, 180),
                scale=(width, .10), position=(0, y_off, 0),
                billboard=True, always_on_top=True)
    bar = Entity(parent=parent, model='quad',
                 color=color.rgb(220, 60, 60),
                 scale=(width - .10, .07), position=(0, y_off, 0),
                 billboard=True, always_on_top=True)
    bar.origin_x = -.5
    bar.x = -(width / 2) + .05
    return bg, bar


# ─── Deer ──────────────────────────────────────────────────────────────────

class Deer(Entity):
    SP_WALK  = 1.4
    SP_FLEE  = 7.5
    ALERT_D  = 38
    FLEE_D   = 18

    def __init__(self, position):
        super().__init__(
            model='cube',
            color=color.rgba(0, 0, 0, 0),
            scale=(0.7, 1.1, 1.7),
            position=position,
            collider='box',
        )
        T_BROWN  = solid(140, 95,  52)
        T_DARK   = solid(100, 65,  30)
        T_TAN    = solid(210, 185, 130)
        T_BLACK  = solid( 28, 22,  18)
        T_ANTLER = solid(165, 130,  70)

        Entity(parent=self, model='cube', texture=T_BROWN,
               scale=(.92, .50, .95), position=(0, .05, 0))
        Entity(parent=self, model='cube', texture=T_BROWN,
               scale=(.22, .35, .22), position=(0, .32, .30))
        self._head = Entity(parent=self, model='cube', texture=T_DARK,
                            scale=(.26, .22, .38), position=(0, .44, .50))
        Entity(parent=self, model='cube', texture=T_TAN,
               scale=(.15, .12, .18), position=(0, .40, .67))
        Entity(parent=self, model='cube', texture=T_TAN,
               scale=(.06, .14, .06), position=( .16, .52, .50))
        Entity(parent=self, model='cube', texture=T_TAN,
               scale=(.06, .14, .06), position=(-.16, .52, .50))
        Entity(parent=self, model='cube', texture=T_TAN,
               scale=(.18, .15, .08), position=(0, .12, -.46))
        for lx, lz in ((.25, .28), (-.25, .28), (.25, -.28), (-.25, -.28)):
            Entity(parent=self, model='cube', texture=T_BROWN,
                   scale=(.14, .45, .14), position=(lx, -.27, lz))
            Entity(parent=self, model='cube', texture=T_BLACK,
                   scale=(.12, .12, .12), position=(lx, -.52, lz))

        if random.random() < 0.5:
            for side in (-1, 1):
                bx = side * 0.10
                Entity(parent=self, model='cube', texture=T_ANTLER,
                       scale=(.04, .22, .04), position=(bx, .62, .50))
                Entity(parent=self, model='cube', texture=T_ANTLER,
                       scale=(.04, .14, .04),
                       position=(bx + side * .08, .72, .52),
                       rotation_z=side * -28)
                Entity(parent=self, model='cube', texture=T_ANTLER,
                       scale=(.04, .12, .04),
                       position=(bx + side * .04, .68, .55),
                       rotation_z=side * -15, rotation_x=20)

        self._hbar_bg, self._hbar = _hpbar(self, width=1.4, y_off=0.75)

        self.hp      = 100
        self.state   = random.choice(['graze', 'walk'])
        self._move_t   = random.uniform(0, 4)
        self._move_dir = Vec3(random.uniform(-1, 1), 0, random.uniform(-1, 1)).normalized()
        self._head_t   = 0.0
        self._anim_t   = random.uniform(0, math.pi * 2)
        self._los_t    = random.uniform(0, .35)
        self._graze_t  = random.uniform(2, 6)
        self._flee_t   = 0.0
        self._speed_mult = random.uniform(0.88, 1.14)
        self.lootable          = False
        self._loot_weight      = 0.0
        self._loot_grade       = 0
        self._loot_display_name = ''
        all_deer.append(self)

    def take_damage(self, amount, shooter_pos=None):
        self.hp -= amount
        self._hbar.scale_x = max(0, self.hp / 100) * 1.3
        if self.hp <= 0:
            self._die()
        else:
            self.spook()

    def spook(self, propagate=True):
        if self.state != 'dead':
            self.state   = 'flee'
            self._flee_t = 7.0
            if propagate:
                # Panic spreads through the herd
                for d in all_deer:
                    if d is self or d.state in ('flee', 'dead'):
                        continue
                    if (d.position - self.position).length() < 18:
                        d.spook(propagate=False)

    def _die(self):
        self.state    = 'dead'
        self.collider = None
        if self in all_deer:
            all_deer.remove(self)
        self._hbar_bg.enabled = False
        self._hbar.enabled    = False

        w = round(random.uniform(45, 175), 1)
        if   w < 65:  g = 1
        elif w < 95:  g = 2
        elif w < 130: g = 3
        else:         g = 4
        self._loot_weight       = w
        self._loot_grade        = g
        self._loot_display_name = ('Young Buck' if g == 1 else 'Buck' if g == 2
                                   else 'Big Buck' if g == 3 else 'Trophy Buck')
        self.lootable = True
        lootable_deer.append(self)

        self.animate_rotation((0, self.rotation_y, 90),
                              duration=0.5, curve=curve.linear)
        self.animate_y(self.y - 0.35, duration=0.55, curve=curve.linear)
        destroy(self, delay=60)

    def update(self):
        if self.state == 'dead':
            return
        dt = time.dt

        self._los_t -= dt
        if self._los_t <= 0 and player_ref:
            self._los_t = 0.25
            d = (player_ref.position - self.position).length()
            if d < self.FLEE_D * player_noise_mult:
                self.spook()
            elif d < self.ALERT_D * player_noise_mult:
                if self.state not in ('flee', 'alert'):
                    self.state = 'alert'
            elif self.state == 'alert':
                self.state = 'graze'

        if self.state == 'flee':
            self._flee_update(dt)
        elif self.state == 'alert':
            self._alert_update(dt)
        else:
            self._wander_update(dt)

    def _herd_bias(self, radius=12):
        center = Vec3(0, 0, 0)
        sep    = Vec3(0, 0, 0)
        n = 0
        for other in all_deer:
            if other is self or other.state == 'dead':
                continue
            diff = other.position - self.position
            dist = diff.length()
            if dist < radius:
                center += other.position
                n += 1
                if dist < 3.5 and dist > 0.01:
                    sep -= diff.normalized() * (3.5 - dist)
        if n == 0:
            return Vec3(0, 0, 0)
        cohesion = (center / n - self.position)
        cohesion.y = 0
        if cohesion.length() > 0.01:
            cohesion = cohesion.normalized() * 0.35
        sep.y = 0
        return cohesion + sep

    def _flee_update(self, dt):
        if not player_ref:
            return
        away = (self.position - player_ref.position)
        away.y = 0
        if away.length() < 0.01:
            away = Vec3(random.uniform(-1, 1), 0, random.uniform(-1, 1))
        away = away.normalized()
        self._move(away, self.SP_FLEE * self._speed_mult, dt)
        self._walk_anim(dt, self.SP_FLEE)
        self._flee_t = max(0.0, self._flee_t - dt)
        if (self._flee_t <= 0 and player_ref
                and (player_ref.position - self.position).length() > 55):
            self.state = 'walk'

    def _alert_update(self, dt):
        if player_ref:
            _face(self, player_ref.position)
        self._head.rotation_x = -15

    def _wander_update(self, dt):
        self._head.rotation_x = 0
        self._move_t -= dt
        if self._move_t <= 0:
            if self.state == 'graze':
                self.state   = 'walk'
                self._move_t = random.uniform(3, 7)
                base_dir = Vec3(random.uniform(-1, 1), 0,
                                random.uniform(-1, 1)).normalized()
                herd = self._herd_bias()
                blended = base_dir * 0.55 + herd
                if blended.length() > 0.01:
                    self._move_dir = blended.normalized()
                else:
                    self._move_dir = base_dir
            else:
                self.state   = 'graze'
                self._move_t = random.uniform(4, 9)

        if self.state == 'walk':
            self._move(self._move_dir, self.SP_WALK * self._speed_mult, dt)
            self._walk_anim(dt, self.SP_WALK)
        else:
            self._graze_t -= dt
            self._head.rotation_x = math.sin(time.time() * 1.2) * 18

    def _move(self, direction, speed, dt):
        new_pos = self.position + direction * speed * dt
        new_pos.x = clamp(new_pos.x, -210, 210)
        new_pos.z = clamp(new_pos.z, -210, 210)
        self.position = new_pos
        _face(self, self.position + direction)

    def _walk_anim(self, dt, speed):
        self._anim_t += dt * speed * 2.2
        self.rotation_z = math.sin(self._anim_t) * 3.5


# ─── Rabbit ────────────────────────────────────────────────────────────────

class Rabbit(Entity):
    SP_HOP  = 3.5
    SP_FLEE = 9.0
    FLEE_D  = 14
    _BASE_Y = 0.14   # keeps box-collider bottom flush with ground

    def __init__(self, position):
        super().__init__(
            model='cube',
            color=color.rgba(0, 0, 0, 0),
            scale=(0.30, 0.28, 0.44),
            position=position,
            collider='box',
        )
        T_FUR   = solid(200, 185, 162)
        T_WHITE = solid(242, 240, 236)
        T_PINK  = solid(218, 155, 152)
        T_EYE   = solid(22,  12,   8)

        Entity(parent=self, model='sphere', texture=T_FUR,
               scale=(.88, .74, .96), position=(0, .04, 0))
        Entity(parent=self, model='sphere', texture=T_FUR,
               scale=(.60, .58, .60), position=(0, .33, .30))
        Entity(parent=self, model='sphere', texture=T_WHITE,
               scale=(.32, .28, .34), position=(0, .25, .46))
        Entity(parent=self, model='sphere', texture=T_PINK,
               scale=(.12, .10, .10), position=(0, .25, .58))
        for ex in (-.18, .18):
            Entity(parent=self, model='sphere', texture=T_EYE,
                   scale=(.12, .12, .08), position=(ex, .37, .38))
        for ex in (-.14, .14):
            Entity(parent=self, model='cube', texture=T_FUR,
                   scale=(.10, .54, .08), position=(ex, .62, .22))
            Entity(parent=self, model='cube', texture=T_PINK,
                   scale=(.06, .46, .04), position=(ex, .64, .23))
        Entity(parent=self, model='sphere', texture=T_WHITE,
               scale=(.24, .20, .18), position=(0, .10, -.44))
        for lx in (-.15, .15):
            Entity(parent=self, model='cube', texture=T_FUR,
                   scale=(.10, .28, .10), position=(lx, -.18, .12))
            Entity(parent=self, model='cube', texture=T_FUR,
                   scale=(.10, .14, .28), position=(lx, -.30, -.10))

        self.hp      = 25
        self.state   = random.choice(['graze', 'hop'])
        self._move_t    = random.uniform(0, 3)
        self._move_dir  = Vec3(random.uniform(-1, 1), 0, random.uniform(-1, 1)).normalized()
        self._hop_t     = random.uniform(0, math.pi * 2)
        self._los_t     = random.uniform(0, .25)
        self._flee_t    = 0.0
        self._speed_mult = random.uniform(0.90, 1.16)
        self.lootable          = False
        self._loot_weight      = 0.0
        self._loot_grade       = 1
        self._loot_display_name = 'Rabbit'
        all_rabbits.append(self)

    def take_damage(self, amount, shooter_pos=None):
        self.hp -= amount
        if self.hp <= 0:
            self._die()
        else:
            self.spook()

    def spook(self):
        if self.state != 'dead':
            self.state   = 'flee'
            self._flee_t = 6.0

    def _die(self):
        self.state    = 'dead'
        self.collider = None
        if self in all_rabbits:
            all_rabbits.remove(self)
        self._loot_weight = round(random.uniform(0.8, 2.6), 1)
        self._loot_grade  = 1
        self.lootable     = True
        lootable_deer.append(self)
        self.animate_rotation((0, self.rotation_y, 90), duration=0.3, curve=curve.linear)
        self.animate_y(self.y - 0.06, duration=0.35, curve=curve.linear)
        destroy(self, delay=60)

    def update(self):
        if self.state == 'dead':
            return
        dt = time.dt

        self._los_t -= dt
        if self._los_t <= 0 and player_ref:
            self._los_t = 0.20
            d = (player_ref.position - self.position).length()
            if d < self.FLEE_D * player_noise_mult:
                self.state   = 'flee'
                self._flee_t = 6.0

        if self.state == 'flee':
            self._flee_update(dt)
        else:
            self._wander_update(dt)

    def _flee_update(self, dt):
        if not player_ref:
            return
        away = (self.position - player_ref.position)
        away.y = 0
        if away.length() < 0.01:
            away = Vec3(random.uniform(-1, 1), 0, random.uniform(-1, 1))
        away = away.normalized()
        self._hop_move(away, self.SP_FLEE * self._speed_mult, dt)
        self._flee_t = max(0.0, self._flee_t - dt)
        if self._flee_t <= 0:
            self.state = 'graze'

    def _wander_update(self, dt):
        self._move_t -= dt
        if self._move_t <= 0:
            if self.state == 'graze':
                self.state     = 'hop'
                self._move_t   = random.uniform(1.5, 4)
                self._move_dir = Vec3(random.uniform(-1, 1), 0,
                                      random.uniform(-1, 1)).normalized()
            else:
                self.state   = 'graze'
                self._move_t = random.uniform(2, 6)
        if self.state == 'hop':
            self._hop_move(self._move_dir, self.SP_HOP * self._speed_mult, dt)

    def _hop_move(self, direction, speed, dt):
        self._hop_t += dt * speed * 4.0
        hop_y = max(0.0, math.sin(self._hop_t) * 0.18)
        new_pos = self.position + direction * speed * dt
        new_pos.x = clamp(new_pos.x, -210, 210)
        new_pos.z = clamp(new_pos.z, -210, 210)
        new_pos.y = self._BASE_Y + hop_y
        self.position = new_pos
        _face(self, self.position + direction)


# ─── Wolf ──────────────────────────────────────────────────────────────────

class Wolf(Entity):
    SP_PATROL = 1.8
    SP_CHASE  = 9.0
    SP_FLEE   = 10.5
    ALERT_D   = 30
    CHASE_D   = 18
    ATTACK_D  = 1.9
    DAMAGE    = 20
    ATK_CD    = 1.3
    FAR_SHOT  = 22   # farther than this → flee; closer → enrage

    def __init__(self, position):
        super().__init__(
            model='cube',
            color=color.rgba(0, 0, 0, 0),
            scale=(0.80, 0.95, 1.85),
            position=position,
            collider='box',
        )
        T_FUR    = solid( 88,  85,  78)
        T_DARK   = solid( 52,  50,  44)
        T_BELLY  = solid(168, 160, 145)
        T_EYE    = solid(210, 150,  18)
        T_NOSE   = solid( 22,  18,  16)

        Entity(parent=self, model='cube', texture=T_FUR,
               scale=(.90, .54, .94), position=(0, .05, 0))
        Entity(parent=self, model='cube', texture=T_BELLY,
               scale=(.60, .32, .72), position=(0, -.06, .02))
        Entity(parent=self, model='cube', texture=T_FUR,
               scale=(.30, .40, .30), position=(0, .31, .32))
        self._head = Entity(parent=self, model='cube', texture=T_FUR,
                            scale=(.38, .32, .44), position=(0, .45, .54))
        Entity(parent=self, model='cube', texture=T_DARK,
               scale=(.24, .20, .30), position=(0, .38, .76))
        Entity(parent=self, model='sphere', texture=T_NOSE,
               scale=(.09, .08, .08), position=(0, .38, .90))
        for ex in (-.14, .14):
            Entity(parent=self, model='sphere', texture=T_EYE,
                   scale=(.09, .09, .07), position=(ex, .50, .70))
            Entity(parent=self, model='cube', texture=T_FUR,
                   scale=(.11, .20, .07), position=(ex, .62, .54),
                   rotation_z=ex * 80)
        Entity(parent=self, model='cube', texture=T_FUR,
               scale=(.13, .14, .52), position=(0, .26, -.52), rotation_x=32)
        Entity(parent=self, model='cube', texture=T_FUR,
               scale=(.11, .11, .28), position=(0, .44, -.74), rotation_x=-18)
        for lx, lz in ((.22, .26), (-.22, .26), (.22, -.26), (-.22, -.26)):
            Entity(parent=self, model='cube', texture=T_FUR,
                   scale=(.16, .52, .16), position=(lx, -.33, lz))
            Entity(parent=self, model='cube', texture=T_DARK,
                   scale=(.14, .15, .14), position=(lx, -.62, lz))

        self._hbar_bg, self._hbar = _hpbar(self, width=1.6, y_off=0.82)

        self.hp          = 120
        self.state       = 'patrol'
        self._move_t     = random.uniform(0, 4)
        self._move_dir   = Vec3(random.uniform(-1, 1), 0, random.uniform(-1, 1)).normalized()
        self._los_t      = random.uniform(0, .3)
        self._atk_cd     = 0.0
        self._flee_t     = 0.0
        self._anim_t     = random.uniform(0, math.pi * 2)
        self._aggressive = False
        self._speed_mult = random.uniform(0.88, 1.12)
        self.lootable          = False
        self._loot_weight      = 0.0
        self._loot_grade       = 2
        self._loot_display_name = 'Gray Wolf'
        all_wolves.append(self)

    def _alert_pack(self, radius=55):
        """Recruit nearby pack members to chase the player."""
        for w in all_wolves:
            if w is self or w.state == 'dead':
                continue
            if (w.position - self.position).length() < radius:
                w._aggressive = True
                if w.state != 'chase':
                    w.state = 'chase'

    def take_damage(self, amount, shooter_pos=None):
        self.hp -= amount
        self._hbar.scale_x = max(0, self.hp / 120) * 1.5
        if self.hp <= 0:
            self._die(); return

        if shooter_pos is not None:
            d = (shooter_pos - self.position).length()
            if d < self.FAR_SHOT:
                self._aggressive = True
                self.state = 'chase'
                self._alert_pack()
            else:
                if not self._aggressive:
                    self.state   = 'flee'
                    self._flee_t = 8.0
        else:
            self._aggressive = True
            self.state = 'chase'
            self._alert_pack()

    def _die(self):
        self.state    = 'dead'
        self.collider = None
        if self in all_wolves:
            all_wolves.remove(self)
        self._hbar_bg.enabled = False
        self._hbar.enabled    = False
        self._loot_weight = round(random.uniform(28, 65), 1)
        self._loot_grade  = 2
        self.lootable     = True
        lootable_deer.append(self)
        self.animate_rotation((0, self.rotation_y, 90), duration=0.5, curve=curve.linear)
        self.animate_y(self.y - 0.40, duration=0.55, curve=curve.linear)
        destroy(self, delay=60)

    def update(self):
        if self.state == 'dead':
            return
        dt = time.dt
        self._atk_cd = max(0.0, self._atk_cd - dt)

        self._los_t -= dt
        if self._los_t <= 0 and player_ref:
            self._los_t = 0.22
            d = (player_ref.position - self.position).length()
            if self.state != 'flee':
                if d < self.CHASE_D * player_noise_mult or self._aggressive:
                    prev = self.state
                    self.state = 'chase'
                    if prev != 'chase':
                        self._alert_pack()
                elif d < self.ALERT_D * player_noise_mult:
                    if self.state == 'patrol':
                        self.state = 'alert'
                elif self.state == 'alert':
                    self.state = 'patrol'

        if self.state == 'flee':
            self._flee_update(dt)
        elif self.state in ('chase', 'alert'):
            self._chase_update(dt)
        else:
            self._patrol_update(dt)

    def _flee_update(self, dt):
        if not player_ref:
            return
        away = (self.position - player_ref.position)
        away.y = 0
        if away.length() < 0.01:
            away = Vec3(random.uniform(-1, 1), 0, random.uniform(-1, 1))
        away = away.normalized()
        self._move(away, self.SP_FLEE * self._speed_mult, dt)
        self._walk_anim(dt, self.SP_FLEE)
        self._flee_t = max(0.0, self._flee_t - dt)
        if (self._flee_t <= 0 and player_ref
                and (player_ref.position - self.position).length() > 60):
            self.state = 'patrol'

    def _chase_update(self, dt):
        if not player_ref:
            return
        d = (player_ref.position - self.position).length()
        if d <= self.ATTACK_D:
            if self._atk_cd <= 0:
                self._atk_cd = self.ATK_CD
                if player_damage_fn:
                    player_damage_fn(self.DAMAGE)
        else:
            toward = (player_ref.position - self.position)
            toward.y = 0
            if toward.length() > 0.01:
                toward = toward.normalized()
            self._move(toward, self.SP_CHASE * self._speed_mult, dt)
            self._walk_anim(dt, self.SP_CHASE)
        self._head.rotation_x = -12

    def _patrol_update(self, dt):
        self._head.rotation_x = 0
        self._move_t -= dt
        if self._move_t <= 0:
            self._move_t   = random.uniform(3, 8)
            self._move_dir = Vec3(random.uniform(-1, 1), 0,
                                  random.uniform(-1, 1)).normalized()
            self.state = random.choice(['patrol', 'patrol', 'idle'])
        if self.state == 'patrol':
            self._move(self._move_dir, self.SP_PATROL * self._speed_mult, dt)
            self._walk_anim(dt, self.SP_PATROL)

    def _move(self, direction, speed, dt):
        new_pos = self.position + direction * speed * dt
        new_pos.x = clamp(new_pos.x, -210, 210)
        new_pos.z = clamp(new_pos.z, -210, 210)
        self.position = new_pos
        _face(self, self.position + direction)

    def _walk_anim(self, dt, speed):
        self._anim_t += dt * speed * 1.8
        self.rotation_z = math.sin(self._anim_t) * 2.5


# ─── Fox ───────────────────────────────────────────────────────────────────

class Fox(Entity):
    SP_TROT = 2.2
    SP_FLEE = 11.0
    FLEE_D  = 24

    def __init__(self, position):
        super().__init__(
            model='cube',
            color=color.rgba(0, 0, 0, 0),
            scale=(0.50, 0.60, 1.10),
            position=position,
            collider='box',
        )
        T_RED   = solid(195,  88,  28)
        T_WHITE = solid(235, 230, 218)
        T_BLACK = solid( 26,  22,  18)
        T_EYE   = solid( 40, 160,  40)

        Entity(parent=self, model='cube', texture=T_RED,
               scale=(.88, .54, .92), position=(0, .05, 0))
        Entity(parent=self, model='cube', texture=T_WHITE,
               scale=(.55, .30, .68), position=(0, -.06, .02))
        Entity(parent=self, model='cube', texture=T_RED,
               scale=(.24, .34, .24), position=(0, .30, .32))
        self._head = Entity(parent=self, model='cube', texture=T_RED,
                            scale=(.30, .26, .40), position=(0, .42, .52))
        Entity(parent=self, model='cube', texture=T_WHITE,
               scale=(.18, .16, .30), position=(0, .36, .70))
        Entity(parent=self, model='sphere', texture=T_BLACK,
               scale=(.07, .06, .06), position=(0, .36, .84))
        for ex in (-.12, .12):
            Entity(parent=self, model='sphere', texture=T_EYE,
                   scale=(.07, .07, .05), position=(ex, .46, .64))
            Entity(parent=self, model='cube', texture=T_BLACK,
                   scale=(.08, .22, .06), position=(ex, .60, .50),
                   rotation_z=ex * 85)
        # Bushy tail
        Entity(parent=self, model='cube', texture=T_RED,
               scale=(.14, .14, .55), position=(0, .22, -.56), rotation_x=38)
        Entity(parent=self, model='sphere', texture=T_WHITE,
               scale=(.22, .18, .22), position=(0, .44, -.80))
        for lx, lz in ((.16, .22), (-.16, .22), (.16, -.22), (-.16, -.22)):
            Entity(parent=self, model='cube', texture=T_RED,
                   scale=(.11, .40, .11), position=(lx, -.25, lz))
            Entity(parent=self, model='cube', texture=T_BLACK,
                   scale=(.10, .11, .10), position=(lx, -.48, lz))

        self.hp      = 40
        self.state   = random.choice(['trot', 'idle'])
        self._move_t    = random.uniform(0, 3)
        self._move_dir  = Vec3(random.uniform(-1, 1), 0, random.uniform(-1, 1)).normalized()
        self._anim_t    = random.uniform(0, math.pi * 2)
        self._los_t     = random.uniform(0, .25)
        self._flee_t    = 0.0
        self._speed_mult = random.uniform(0.92, 1.14)
        self.lootable          = False
        self._loot_weight      = 0.0
        self._loot_grade       = 1
        self._loot_display_name = 'Red Fox'
        all_foxes.append(self)

    def take_damage(self, amount, shooter_pos=None):
        self.hp -= amount
        if self.hp <= 0:
            self._die()
        else:
            self.state   = 'flee'
            self._flee_t = 10.0

    def _die(self):
        self.state    = 'dead'
        self.collider = None
        if self in all_foxes:
            all_foxes.remove(self)
        self._loot_weight       = round(random.uniform(3.5, 8.5), 1)
        self._loot_grade        = 1
        self._loot_display_name = 'Red Fox'
        self.lootable           = True
        lootable_deer.append(self)
        self.animate_rotation((0, self.rotation_y, 90), duration=0.4, curve=curve.linear)
        self.animate_y(self.y - 0.22, duration=0.45, curve=curve.linear)
        destroy(self, delay=60)

    def update(self):
        if self.state == 'dead':
            return
        dt = time.dt

        self._los_t -= dt
        if self._los_t <= 0 and player_ref:
            self._los_t = 0.22
            d = (player_ref.position - self.position).length()
            if d < self.FLEE_D * player_noise_mult:
                self.state   = 'flee'
                self._flee_t = 7.0

        if self.state == 'flee':
            self._flee_update(dt)
        else:
            self._wander_update(dt)

    def _flee_update(self, dt):
        if not player_ref:
            return
        away = (self.position - player_ref.position)
        away.y = 0
        if away.length() < 0.01:
            away = Vec3(random.uniform(-1, 1), 0, random.uniform(-1, 1))
        away = away.normalized()
        self._move(away, self.SP_FLEE * self._speed_mult, dt)
        self._walk_anim(dt, self.SP_FLEE)
        self._flee_t = max(0.0, self._flee_t - dt)
        if self._flee_t <= 0:
            self.state = 'idle'

    def _wander_update(self, dt):
        self._move_t -= dt
        if self._move_t <= 0:
            if self.state == 'idle':
                self.state   = 'trot'
                self._move_t = random.uniform(2, 5)
                self._move_dir = Vec3(random.uniform(-1, 1), 0,
                                      random.uniform(-1, 1)).normalized()
            else:
                self.state   = 'idle'
                self._move_t = random.uniform(3, 7)
        if self.state == 'trot':
            self._move(self._move_dir, self.SP_TROT * self._speed_mult, dt)
            self._walk_anim(dt, self.SP_TROT)

    def _move(self, direction, speed, dt):
        new_pos = self.position + direction * speed * dt
        new_pos.x = clamp(new_pos.x, -210, 210)
        new_pos.z = clamp(new_pos.z, -210, 210)
        self.position = new_pos
        _face(self, self.position + direction)

    def _walk_anim(self, dt, speed):
        self._anim_t += dt * speed * 2.0
        self.rotation_z = math.sin(self._anim_t) * 2.0


# ─── Bear ──────────────────────────────────────────────────────────────────

class Bear(Entity):
    SP_LUMBER = 1.2
    SP_CHARGE = 11.5
    SP_FLEE   = 8.0
    ALERT_D   = 22
    CHARGE_D  = 14
    ATTACK_D  = 2.2
    DAMAGE    = 35
    ATK_CD    = 1.8
    FAR_SHOT  = 28

    def __init__(self, position):
        super().__init__(
            model='cube',
            color=color.rgba(0, 0, 0, 0),
            scale=(1.20, 1.40, 2.20),
            position=position,
            collider='box',
        )
        T_FUR  = solid( 48,  36,  26)
        T_DARK = solid( 28,  20,  14)
        T_SNOT = solid(105,  78,  55)
        T_EYE  = solid( 18,  12,   8)

        Entity(parent=self, model='cube', texture=T_FUR,
               scale=(.92, .58, .95), position=(0, .06, 0))
        Entity(parent=self, model='cube', texture=T_FUR,
               scale=(.38, .46, .38), position=(0, .35, .34))
        self._head = Entity(parent=self, model='sphere', texture=T_FUR,
                            scale=(.55, .48, .56), position=(0, .52, .58))
        Entity(parent=self, model='sphere', texture=T_SNOT,
               scale=(.28, .22, .28), position=(0, .44, .78))
        Entity(parent=self, model='sphere', texture=T_DARK,
               scale=(.12, .10, .10), position=(0, .44, .91))
        for ex in (-.20, .20):
            Entity(parent=self, model='sphere', texture=T_EYE,
                   scale=(.10, .10, .08), position=(ex, .58, .72))
            Entity(parent=self, model='sphere', texture=T_FUR,
                   scale=(.16, .14, .12), position=(ex, .66, .54))
        Entity(parent=self, model='sphere', texture=T_DARK,
               scale=(.16, .22, .18), position=(0, .16, -.52))
        for lx, lz in ((.30, .30), (-.30, .30), (.30, -.30), (-.30, -.30)):
            Entity(parent=self, model='cube', texture=T_FUR,
                   scale=(.24, .62, .24), position=(lx, -.36, lz))
            Entity(parent=self, model='cube', texture=T_DARK,
                   scale=(.22, .18, .22), position=(lx, -.70, lz))

        self._hbar_bg, self._hbar = _hpbar(self, width=2.0, y_off=0.95)

        self.hp          = 300
        self.state       = 'lumber'
        self._move_t     = random.uniform(0, 5)
        self._move_dir   = Vec3(random.uniform(-1, 1), 0, random.uniform(-1, 1)).normalized()
        self._los_t      = random.uniform(0, .35)
        self._atk_cd     = 0.0
        self._flee_t     = 0.0
        self._anim_t     = random.uniform(0, math.pi * 2)
        self._enraged    = False
        self._speed_mult = random.uniform(0.92, 1.08)
        self._stand_t    = 0.0    # >0 while rearing up in alert
        self.lootable          = False
        self._loot_weight      = 0.0
        self._loot_grade       = 4
        self._loot_display_name = 'Black Bear'
        all_bears.append(self)

    def take_damage(self, amount, shooter_pos=None):
        self.hp -= amount
        self._hbar.scale_x = max(0, self.hp / 300) * 1.9
        if self.hp <= 0:
            self._die(); return

        if shooter_pos is not None:
            d = (shooter_pos - self.position).length()
            if d < self.FAR_SHOT:
                self._enraged = True
                self.state    = 'charge'
            else:
                if not self._enraged:
                    self.state   = 'flee'
                    self._flee_t = 5.0
        else:
            self._enraged = True
            self.state    = 'charge'

    def _die(self):
        self.state    = 'dead'
        self.collider = None
        if self in all_bears:
            all_bears.remove(self)
        self._hbar_bg.enabled = False
        self._hbar.enabled    = False
        self._loot_weight = round(random.uniform(120, 280), 1)
        self._loot_grade  = 4
        self.lootable     = True
        lootable_deer.append(self)
        self.animate_rotation((0, self.rotation_y, 90), duration=0.6, curve=curve.linear)
        self.animate_y(self.y - 0.60, duration=0.65, curve=curve.linear)
        destroy(self, delay=60)

    def update(self):
        if self.state == 'dead':
            return
        dt = time.dt
        self._atk_cd = max(0.0, self._atk_cd - dt)

        self._los_t -= dt
        if self._los_t <= 0 and player_ref:
            self._los_t = 0.25
            d = (player_ref.position - self.position).length()
            if self.state != 'flee':
                if d < self.CHARGE_D * player_noise_mult or self._enraged:
                    self.state = 'charge'
                elif d < self.ALERT_D * player_noise_mult:
                    if self.state == 'lumber':
                        self.state    = 'alert'
                        self._stand_t = 2.2   # 2.2s rear-up before deciding
                elif self.state == 'alert':
                    self.state = 'lumber'

        if self.state == 'flee':
            self._flee_update(dt)
        elif self.state == 'alert':
            self._alert_update(dt)
        elif self.state == 'charge':
            self._charge_update(dt)
        else:
            self._lumber_update(dt)

    def _flee_update(self, dt):
        self.rotation_x = lerp(self.rotation_x, 0, dt * 5)
        if not player_ref:
            return
        away = (self.position - player_ref.position)
        away.y = 0
        if away.length() < 0.01:
            away = Vec3(random.uniform(-1, 1), 0, random.uniform(-1, 1))
        away = away.normalized()
        self._move(away, self.SP_FLEE * self._speed_mult, dt)
        self._walk_anim(dt, self.SP_FLEE)
        self._flee_t = max(0.0, self._flee_t - dt)
        if self._flee_t <= 0:
            self._enraged = True   # bear always comes back angry
            self.state    = 'charge'

    def _alert_update(self, dt):
        # Rear up on hind legs, face player, growl-pose
        if player_ref:
            _face(self, player_ref.position)
        self.rotation_x = lerp(self.rotation_x, -28, dt * 3.5)
        self._head.rotation_x = lerp(self._head.rotation_x, -10, dt * 4)
        self._stand_t = max(0.0, self._stand_t - dt)
        if self._stand_t <= 0:
            # After standing, commit to charging
            self._enraged = True
            self.state    = 'charge'

    def _charge_update(self, dt):
        # Drop back to all fours
        self.rotation_x = lerp(self.rotation_x, 0, dt * 6)
        if not player_ref:
            return
        d = (player_ref.position - self.position).length()
        if d <= self.ATTACK_D:
            if self._atk_cd <= 0:
                self._atk_cd = self.ATK_CD
                if player_damage_fn:
                    player_damage_fn(self.DAMAGE)
        else:
            toward = (player_ref.position - self.position)
            toward.y = 0
            if toward.length() > 0.01:
                toward = toward.normalized()
            self._move(toward, self.SP_CHARGE * self._speed_mult, dt)
            self._walk_anim(dt, self.SP_CHARGE)
        self._head.rotation_x = -15

    def _lumber_update(self, dt):
        self.rotation_x = lerp(self.rotation_x, 0, dt * 5)
        self._head.rotation_x = 0
        self._move_t -= dt
        if self._move_t <= 0:
            self._move_t   = random.uniform(4, 10)
            self._move_dir = Vec3(random.uniform(-1, 1), 0,
                                  random.uniform(-1, 1)).normalized()
            self.state = random.choice(['lumber', 'lumber', 'rest'])
        if self.state == 'lumber':
            self._move(self._move_dir, self.SP_LUMBER * self._speed_mult, dt)
            self._walk_anim(dt, self.SP_LUMBER)

    def _move(self, direction, speed, dt):
        new_pos = self.position + direction * speed * dt
        new_pos.x = clamp(new_pos.x, -210, 210)
        new_pos.z = clamp(new_pos.z, -210, 210)
        self.position = new_pos
        _face(self, self.position + direction)

    def _walk_anim(self, dt, speed):
        self._anim_t += dt * speed * 1.4
        self.rotation_z = math.sin(self._anim_t) * 4.0


# ─── Bird ──────────────────────────────────────────────────────────────────

class Bird(Entity):
    """Tiny songbird — sits on the ground, flutters away when you get close."""
    FLEE_D = 7.0

    def __init__(self, position):
        super().__init__(model=None, color=color.rgba(0, 0, 0, 0),
                         position=position)
        plumage = random.choice([
            solid(195, 130,  40),  # robin orange
            solid( 60,  85, 165),  # bluebird
            solid(195,  55,  55),  # cardinal red
            solid( 70,  72,  78),  # dark sparrow
            solid(225, 210,  90),  # finch yellow
        ])
        Entity(parent=self, model='sphere', texture=plumage,
               scale=(.18, .15, .26), position=(0, .14, 0))
        Entity(parent=self, model='sphere', texture=plumage,
               scale=(.12, .12, .12), position=(0, .26, .10))
        Entity(parent=self, model='cube', texture=solid(220, 180, 40),
               scale=(.04, .04, .07), position=(0, .26, .19))
        for ex in (-.04, .04):
            Entity(parent=self, model='sphere', texture=solid(10, 8, 6),
                   scale=(.025, .025, .025), position=(ex, .28, .14))
        for sx in (-.10, .10):
            Entity(parent=self, model='cube', texture=plumage,
                   scale=(.04, .03, .14), position=(sx, .16, -.02))

        self._home    = Vec3(*position)
        self._state   = 'perched'
        self._t       = random.uniform(0, math.pi * 2)
        self._flap_t  = 0.0
        self._fly_dir = Vec3(0, 0, 0)
        self._life    = 0.0
        all_birds.append(self)

    def update(self):
        if not player_ref:
            return
        dt = time.dt
        self._t += dt

        if self._state == 'perched':
            # Subtle head bob
            self.rotation_y += math.sin(self._t * 1.6) * 12 * dt
            d = (player_ref.position - self.position).length()
            if d < self.FLEE_D:
                self._state = 'flying'
                away = (self.position - player_ref.position)
                away.y = 0
                if away.length() < 0.01:
                    away = Vec3(random.uniform(-1, 1), 0, random.uniform(-1, 1))
                self._fly_dir = away.normalized()
                self._life = 5.5
        elif self._state == 'flying':
            self._life -= dt
            self.position += self._fly_dir * 6.5 * dt
            self.y = lerp(self.y, self._home.y + 14, dt * 1.2)
            self._flap_t += dt * 22
            # Wing-flap wiggle via rotation_z
            self.rotation_z = math.sin(self._flap_t) * 18
            if self._life <= 0:
                if self in all_birds:
                    all_birds.remove(self)
                destroy(self)


# ─── Spawn ─────────────────────────────────────────────────────────────────

def spawn_animals():
    # Deer
    for pos in [(-30, 1, 50), (-55, 1, 35), (-18, 1, 65), (-62, 1, 50), (25, 1, 72)]:
        Deer(Vec3(*pos))

    # Rabbits — small, open fields (y=_BASE_Y so collider sits on ground)
    for pos in [
        (-42, 0.14, 18), (15, 0.14, -35), (-80, 0.14, -20), (55, 0.14, -60),
        (-110, 0.14, 45), (90, 0.14, 30), (-30, 0.14, -80),
    ]:
        Rabbit(Vec3(*pos))

    # Wolves — forest edges, groups
    for pos in [
        (-85, 1, 70), (-95, 1, 55), (-70, 1, 85),   # pack 1
        (60, 1, -90), (75, 1, -75),                   # pack 2
    ]:
        Wolf(Vec3(*pos))

    # Foxes — scattered
    for pos in [(-50, 0.5, -55), (110, 0.5, -40), (-120, 0.5, -60)]:
        Fox(Vec3(*pos))

    # Bears — deep forest, rare
    for pos in [(-150, 1, 100), (130, 1, -130)]:
        Bear(Vec3(*pos))

    # Songbirds scattered around the world
    _bird_seed = random.Random(31)
    for _ in range(38):
        bx = _bird_seed.uniform(-180, 180)
        bz = _bird_seed.uniform(-180, 180)
        # Avoid lake bounds (38..95 x, -28..28 z) and path corridor
        if 36 < bx < 105 and -30 < bz < 30:
            continue
        if abs(bx) < 12 and abs(bz) < 12:
            continue
        Bird(Vec3(bx, 0.25, bz))


# ─── Module-level helpers ──────────────────────────────────────────────────

def update_all(dt):
    pass   # animals use Ursina auto-update


def spook_all(position, radius):
    for animal in list(all_deer) + list(all_rabbits):
        if (animal.position - position).length() < radius:
            animal.spook() if hasattr(animal, 'spook') else None
    for wolf in list(all_wolves):
        if (wolf.position - position).length() < radius:
            wolf._aggressive = True
            wolf.state = 'chase'
    for bear in list(all_bears):
        if (bear.position - position).length() < radius * 0.6:
            bear._enraged = True
            bear.state    = 'charge'


def get_lootable_near(position, radius=2.8):
    best, best_d = None, radius
    stale = []
    for animal in list(lootable_deer):
        try:
            d = (animal.position - position).length()
        except (AssertionError, AttributeError):
            # Entity was destroyed (60s timeout) — drop from the list
            stale.append(animal)
            continue
        if d < best_d:
            best, best_d = animal, d
    for s in stale:
        if s in lootable_deer:
            lootable_deer.remove(s)
    return best


def collect_deer(animal):
    if animal in lootable_deer:
        lootable_deer.remove(animal)
    animal.lootable = False
    destroy(animal)
