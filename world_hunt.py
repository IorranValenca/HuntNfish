"""Open-world terrain — atmospheric build with mountains, reeds, lily pads,
wildflowers, stumps, fallen logs, and drifting clouds."""
from ursina import *
from ursina.models.procedural.cone     import Cone
from ursina.models.procedural.cylinder import Cylinder
from game_utils import solid
import random, math

LAKE_X0, LAKE_X1 = 38, 95
LAKE_Z0, LAKE_Z1 = -28, 28

# Trader's lodge — proximity trigger and door position for the shop
CABIN_POS = Vec3(-24, 0, 22)   # cabin centre
CABIN_DOOR_POS = Vec3(-24, 1.0, 25.6)   # in front of door

def is_water(x, z):
    return LAKE_X0 < x < LAKE_X1 and LAKE_Z0 < z < LAKE_Z1

def _clear(x, z):
    if is_water(x, z): return True
    if 29 < x < 103 and -37 < z < 37: return True
    if abs(x) < 14 and abs(z) < 14:   return True
    # Keep the cabin clearing free of trees / clutter
    if (CABIN_POS.x - 10) < x < (CABIN_POS.x + 10) and \
       (CABIN_POS.z - 10) < z < (CABIN_POS.z + 14):
        return True
    return False


def _build_cabin():
    cx, cz = CABIN_POS.x, CABIN_POS.z
    T_LOG   = solid(118,  75,  38)
    T_LOG_D = solid( 80,  50,  22)
    T_ROOF  = solid( 70,  38,  20)
    T_ROOF2 = solid( 92,  52,  30)
    T_DOOR  = solid( 50,  28,  14)
    T_WIN   = solid(255, 220, 110)
    T_STONE = solid( 92,  88,  82)
    T_DARK  = solid( 30,  22,  16)
    T_SIGN  = solid(150,  92,  35)

    # Stone foundation
    Entity(model='cube', scale=(7.0, 0.30, 6.6),
           position=(cx, 0.15, cz),
           texture=T_STONE, collider='box')

    # Walls — front, back, sides (with door / windows cut implicitly by overlays)
    # Back wall (away from spawn)
    Entity(model='cube', scale=(7.0, 3.0, 0.20),
           position=(cx, 1.65, cz - 3.10),
           texture=T_LOG, collider='box')
    # Left wall
    Entity(model='cube', scale=(0.20, 3.0, 6.4),
           position=(cx - 3.40, 1.65, cz),
           texture=T_LOG, collider='box')
    # Right wall
    Entity(model='cube', scale=(0.20, 3.0, 6.4),
           position=(cx + 3.40, 1.65, cz),
           texture=T_LOG, collider='box')
    # Front wall — split into 3 pieces around the door
    Entity(model='cube', scale=(2.3, 3.0, 0.20),     # left of door
           position=(cx - 2.35, 1.65, cz + 3.10),
           texture=T_LOG, collider='box')
    Entity(model='cube', scale=(2.3, 3.0, 0.20),     # right of door
           position=(cx + 2.35, 1.65, cz + 3.10),
           texture=T_LOG, collider='box')
    Entity(model='cube', scale=(1.4, 0.9, 0.20),     # header above door
           position=(cx,        2.70, cz + 3.10),
           texture=T_LOG, collider='box')

    # Log seam highlights (horizontal darker stripes)
    for sy in (0.50, 1.05, 1.60, 2.15, 2.70):
        for sx, sz, w, d in [
            (cx,         cz - 3.10, 7.0, 0.05),     # back
            (cx,         cz + 3.10, 7.0, 0.05),     # front (visible at seams)
            (cx - 3.40,  cz,        0.05, 6.4),     # left
            (cx + 3.40,  cz,        0.05, 6.4),     # right
        ]:
            Entity(model='cube', scale=(w, 0.04, d),
                   position=(sx, sy, sz),
                   texture=T_LOG_D)

    # Door (recessed dark cube)
    Entity(model='cube', scale=(1.30, 2.10, 0.10),
           position=(cx, 1.35, cz + 3.16),
           texture=T_DOOR, collider='box')
    # Door handle
    Entity(model='sphere', scale=0.08,
           position=(cx + 0.45, 1.35, cz + 3.22),
           texture=T_STONE)

    # Two windows with lit glow
    for wx in (-2.30, 2.30):
        Entity(model='cube', scale=(1.10, 0.90, 0.06),     # frame
               position=(cx + wx, 1.95, cz + 3.14),
               texture=T_DARK)
        Entity(model='cube', scale=(0.92, 0.74, 0.04),     # glow
               position=(cx + wx, 1.95, cz + 3.16),
               texture=T_WIN)
        # Mullions
        Entity(model='cube', scale=(0.04, 0.78, 0.05),
               position=(cx + wx, 1.95, cz + 3.17),
               texture=T_DARK)
        Entity(model='cube', scale=(0.96, 0.04, 0.05),
               position=(cx + wx, 1.95, cz + 3.17),
               texture=T_DARK)

    # Roof — two slanted planes meeting at the ridge
    Entity(model='cube', scale=(7.6, 0.18, 4.2),
           position=(cx - 1.6, 3.95, cz),
           texture=T_ROOF, rotation_x=-32, collider='box')
    Entity(model='cube', scale=(7.6, 0.18, 4.2),
           position=(cx + 1.6, 3.95, cz),
           texture=T_ROOF, rotation_x= 32, collider='box')
    # Ridge cap
    Entity(model='cube', scale=(7.7, 0.20, 0.30),
           position=(cx, 4.60, cz),
           texture=T_ROOF2)
    # Roof gable triangles (filled with cubes — simpler than triangles)
    Entity(model='cube', scale=(0.18, 1.40, 6.4),
           position=(cx, 3.85, cz),
           texture=T_LOG)

    # Chimney
    Entity(model='cube', scale=(0.80, 1.80, 0.80),
           position=(cx + 2.80, 4.20, cz - 1.20),
           texture=T_STONE, collider='box')
    Entity(model='cube', scale=(0.95, 0.18, 0.95),
           position=(cx + 2.80, 5.20, cz - 1.20),
           texture=T_DARK)

    # Porch slab + 2 posts + low railing
    Entity(model='cube', scale=(4.6, 0.20, 1.40),
           position=(cx, 0.40, cz + 3.80),
           texture=T_LOG, collider='box')
    for px in (-2.10, 2.10):
        Entity(model='cube', scale=(0.16, 2.00, 0.16),
               position=(cx + px, 1.50, cz + 4.40),
               texture=T_LOG_D, collider='box')
    # Porch roof
    Entity(model='cube', scale=(4.8, 0.12, 1.60),
           position=(cx, 2.55, cz + 4.30),
           texture=T_ROOF)
    # Low railing on each side
    for rx_sign in (-1, 1):
        Entity(model='cube', scale=(0.06, 0.55, 1.20),
               position=(cx + rx_sign * 2.10, 0.95, cz + 4.10),
               texture=T_LOG_D)

    # Lanterns flanking the door
    for lx in (-0.95, 0.95):
        Entity(model='cube', scale=(0.18, 0.28, 0.18),
               position=(cx + lx, 2.15, cz + 3.30),
               texture=T_DARK)
        Entity(model='sphere', scale=0.14,
               position=(cx + lx, 2.15, cz + 3.30),
               texture=T_WIN)

    # Wooden sign on a post
    Entity(model='cube', scale=(0.10, 1.40, 0.10),
           position=(cx - 4.40, 0.70, cz + 4.20),
           texture=T_LOG_D, collider='box')
    Entity(model='cube', scale=(1.70, 0.70, 0.06),
           position=(cx - 4.40, 1.65, cz + 4.20),
           texture=T_SIGN, collider='box')
    # Decorative carved letters on the sign (dark planks)
    Entity(model='cube', scale=(1.40, 0.10, 0.02),
           position=(cx - 4.40, 1.75, cz + 4.17),
           texture=T_DARK)
    Entity(model='cube', scale=(1.40, 0.08, 0.02),
           position=(cx - 4.40, 1.55, cz + 4.17),
           texture=T_DARK)

    # Small wood stack out front
    for i in range(5):
        Entity(model='cube', scale=(0.18, 0.18, 1.20),
               position=(cx + 3.50, 0.40 + i * 0.18, cz + 1.50),
               texture=T_LOG_D)
    for i in range(4):
        Entity(model='cube', scale=(0.18, 0.18, 1.20),
               position=(cx + 3.50, 0.49 + i * 0.18, cz + 1.50 - 0.18),
               texture=T_LOG)

# Texture palettes — limit unique textures so GPU state changes stay rare.
_T_TRUNK  = [solid(72+i*5, 52+i*3, 30+i*2) for i in range(6)]
_T_PINE   = [solid(28+i*5, 105+i*7, 18+i*4) for i in range(6)]
_T_OAK    = [solid(36+i*6, 100+i*7, 20+i*5) for i in range(6)]
_T_BUSH   = [solid(33+i*5,  92+i*9, 23+i*4) for i in range(6)]
_T_ROCK   = [solid(98+i*6,  94+i*5, 82+i*4) for i in range(4)]
_T_FLOWER = [solid(255, 220,  60),  # yellow
             solid(245, 245, 235),  # white
             solid(232, 142, 178),  # pink
             solid(210,  60,  50),  # red
             solid(155,  88, 200)]  # purple
_T_REED   = solid(106, 130,  58)
_T_LILY   = solid( 56, 130,  64)
_T_LILY_F = solid(248, 232, 240)
_T_SNOW   = solid(238, 244, 252)
_T_MTN    = solid(105, 110,  95)
_T_STUMP  = solid( 88,  65,  38)
_T_CLOUD  = solid(248, 250, 252)


class _Cloud(Entity):
    """Cube cluster that drifts slowly across the sky and wraps around."""
    def __init__(self, position, scale, vel):
        super().__init__(model='cube', scale=scale, position=position,
                         texture=_T_CLOUD)
        self._v = vel

    def update(self):
        self.x += self._v * time.dt
        if self.x > 260:
            self.x = -260


def _pine(x, z):
    h  = random.uniform(7, 17)
    tw = random.uniform(0.28, 0.52)
    Entity(model=Cylinder(6), scale=(tw, h, tw), position=(x, 0, z),
           texture=random.choice(_T_TRUNK), collider='box')
    fw = h * 0.56
    fh = h * 0.74
    Entity(model=Cone(8), scale=(fw, fh, fw),
           position=(x, h * 0.16, z),
           texture=random.choice(_T_PINE))


def _oak(x, z):
    h  = random.uniform(5, 12)
    tw = random.uniform(0.45, 0.88)
    fw = random.uniform(3.0, 5.8)
    fh = random.uniform(2.5, 4.6)
    Entity(model=Cylinder(6), scale=(tw, h, tw), position=(x, 0, z),
           texture=random.choice(_T_TRUNK), collider='box')
    Entity(model='sphere', scale=(fw, fh, fw),
           position=(x, h + fh * 0.35, z),
           texture=random.choice(_T_OAK))


def _bush(x, z):
    sc = random.uniform(0.8, 1.9)
    Entity(model='sphere', scale=(sc, sc * 0.60, sc),
           position=(x, sc * 0.30, z),
           texture=random.choice(_T_BUSH))


def _stump(x, z):
    sc = random.uniform(0.6, 1.1)
    Entity(model=Cylinder(8), scale=(sc, sc * 0.5, sc),
           position=(x, 0, z),
           texture=_T_STUMP, collider='box')


def _fallen_log(x, z):
    length = random.uniform(3.5, 6.5)
    tw     = random.uniform(0.45, 0.80)
    log = Entity(model=Cylinder(6), scale=(tw, length, tw),
                 position=(x, tw * 0.5, z),
                 texture=random.choice(_T_TRUNK), collider='box')
    log.rotation_x = 90
    log.rotation_y = random.uniform(0, 360)


def _flower_patch(x, z):
    tex = random.choice(_T_FLOWER)
    for _ in range(random.randint(4, 8)):
        ox = random.uniform(-1.1, 1.1)
        oz = random.uniform(-1.1, 1.1)
        h  = random.uniform(0.18, 0.36)
        Entity(model='cube', scale=(0.10, h, 0.10),
               position=(x + ox, h * 0.5, z + oz),
               texture=tex)


def _reed(x, z):
    h = random.uniform(0.7, 1.6)
    w = random.uniform(0.05, 0.10)
    Entity(model='cube', scale=(w, h, w),
           position=(x, h * 0.5, z),
           texture=_T_REED)


def _lily(x, z):
    sc = random.uniform(0.5, 1.1)
    Entity(model=Cylinder(10), scale=(sc, 0.04, sc),
           position=(x, 0.08, z),
           texture=_T_LILY)
    if random.random() < 0.25:
        Entity(model='sphere', scale=0.18,
               position=(x + sc * 0.15, 0.18, z),
               texture=_T_LILY_F)


def _mountain(x, z, base_w, height):
    Entity(model=Cone(8),
           scale=(base_w, height, base_w),
           position=(x, 0, z),
           texture=_T_MTN)
    cap_h = height * 0.30
    cap_w = base_w * 0.45
    Entity(model=Cone(8),
           scale=(cap_w, cap_h, cap_w),
           position=(x, height - cap_h * 0.6, z),
           texture=_T_SNOW)


def build_world():
    random.seed(9)

    # ── Sky ────────────────────────────────────────────────────────────
    window.color = color.rgb(0.53, 0.72, 0.88)
    base.setBackgroundColor(0.53, 0.72, 0.88)

    # Ground
    Entity(model='plane', scale=480, texture=solid(68, 105, 44), collider='box')

    # Lake
    lx = (LAKE_X0 + LAKE_X1) / 2
    lz = (LAKE_Z0 + LAKE_Z1) / 2
    lw = LAKE_X1 - LAKE_X0
    ld = LAKE_Z1 - LAKE_Z0
    Entity(model='cube', scale=(lw, 0.10, ld), position=(lx, 0.01, lz),
           texture=solid(18, 62, 128))
    Entity(model='cube', scale=(lw, 0.03, ld), position=(lx, 0.04, lz),
           texture=solid(48, 112, 185))
    Entity(model='cube', scale=(lw + 6, 0.06, ld + 6), position=(lx, 0.005, lz),
           texture=solid(190, 168, 110), collider=None)
    Entity(model='cube', scale=(3.5, 0.05, 40), position=(20, 0.02, 0),
           texture=solid(148, 118, 72), collider=None)

    # Dock
    Entity(model='cube', scale=(2.5, 0.22, 11),
           position=(LAKE_X0 - 1.25, 0.18, 0),
           texture=solid(145, 100, 55), collider='box')
    for dz in (-4, -2, 0, 2, 4):
        Entity(model='cube', scale=(.28, 1.5, .28),
               position=(LAKE_X0 - 0.6, -0.55, dz),
               texture=solid(110, 75, 40), collider='box')

    # Trader's Lodge
    _build_cabin()

    # Lily pads scattered on lake surface
    for _ in range(26):
        x = random.uniform(LAKE_X0 + 3, LAKE_X1 - 3)
        z = random.uniform(LAKE_Z0 + 3, LAKE_Z1 - 3)
        _lily(x, z)

    # Reeds around shore (just outside the lake rectangle)
    for _ in range(110):
        angle = random.uniform(0, math.pi * 2)
        offset = random.uniform(0.4, 2.2)
        rx = (lw / 2 + offset) * math.cos(angle)
        rz = (ld / 2 + offset) * math.sin(angle)
        _reed(lx + rx, lz + rz)

    # Trees — 2 entities each (trunk + canopy)
    spawned = 0
    for _ in range(340):
        if spawned >= 220: break
        x = random.uniform(-205, 205)
        z = random.uniform(-205, 205)
        if _clear(x, z): continue
        if random.random() < 0.42:
            _pine(x, z)
        else:
            _oak(x, z)
        spawned += 1

    # Bushes — 1 entity each, no collider
    spawned = 0
    for _ in range(160):
        if spawned >= 80: break
        x = random.uniform(-190, 190)
        z = random.uniform(-190, 190)
        if _clear(x, z): continue
        _bush(x, z)
        spawned += 1

    # Stumps & fallen logs — adds forest variety, with colliders
    spawned = 0
    for _ in range(40):
        if spawned >= 16: break
        x = random.uniform(-180, 180)
        z = random.uniform(-180, 180)
        if _clear(x, z): continue
        if random.random() < 0.45:
            _fallen_log(x, z)
        else:
            _stump(x, z)
        spawned += 1

    # Wildflower patches scattered through fields
    spawned = 0
    for _ in range(120):
        if spawned >= 55: break
        x = random.uniform(-180, 180)
        z = random.uniform(-180, 180)
        if _clear(x, z): continue
        _flower_patch(x, z)
        spawned += 1

    # Shore rocks (collider kept — players walk around the lake edge)
    for _ in range(22):
        angle = random.uniform(0, math.pi * 2)
        rx = (lw / 2 + random.uniform(2, 5)) * math.cos(angle)
        rz = (ld / 2 + random.uniform(2, 5)) * math.sin(angle)
        sc = random.uniform(0.3, 1.2)
        Entity(model='sphere', scale=(sc, sc * 0.58, sc),
               position=(lx + rx, sc * 0.28, lz + rz),
               texture=random.choice(_T_ROCK), collider='box')

    # Scattered field rocks (no collider — decorative)
    spawned = 0
    for _ in range(80):
        if spawned >= 25: break
        x = random.uniform(-190, 190)
        z = random.uniform(-190, 190)
        if _clear(x, z): continue
        sc = random.uniform(0.2, 0.9)
        Entity(model='sphere', scale=(sc, sc * 0.58, sc),
               position=(x, sc * 0.29, z),
               texture=random.choice(_T_ROCK))
        spawned += 1

    # ── Cone mountains with snow caps (replace boxy backdrops) ─────────
    for x, z, bw, h in [
        ( 248,    0, 38, 95),
        (-248,    0, 38, 95),
        (   0,  248, 38, 95),
        (   0, -248, 38, 95),
        ( 200,  200, 26, 68),
        (-200,  200, 26, 68),
        ( 200, -200, 26, 68),
        (-200, -200, 26, 68),
        ( 270,  120, 22, 55),
        (-270, -120, 22, 55),
        ( 120,  270, 22, 55),
        (-120, -270, 22, 55),
    ]:
        _mountain(x, z, bw, h)

    # ── Drifting clouds high above ─────────────────────────────────────
    for _ in range(22):
        cx = random.uniform(-250, 250)
        cz = random.uniform(-250, 250)
        cy = random.uniform(115, 160)
        sw = random.uniform(22, 48)
        sh = random.uniform(4, 8)
        sd = random.uniform(16, 36)
        vel = random.uniform(0.4, 1.2)
        _Cloud((cx, cy, cz), (sw, sh, sd), vel)
