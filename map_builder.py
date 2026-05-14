"""
Military compound map for FPS Combat Zone.
"""
from ursina import *
from ursina import Texture as UrsinaTexture
from panda3d.core import Texture as P3DTex, PNMImage

# ── Solid-colour texture helper ──────────────────────────────────────────────
_tex_cache = {}

def _solid(r, g, b):
    """Return a cached 1×1 UrsinaTexture of the given RGB (0-255) colour."""
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


# ── Colour palette ──────────────────────────────────────────────────────────
T_GROUND   = _solid(58,  68,  42)
T_CONCRETE = _solid(118, 110, 95)
T_CONC2    = _solid(103, 97,  84)
T_DARK     = _solid(78,  73,  62)
T_SANDBAG  = _solid(172, 158, 102)
T_CRATE    = _solid(122, 103, 72)
T_BARREL   = _solid(55,  78,  55)
T_ROAD     = _solid(48,  48,  48)
T_METAL    = _solid(60,  65,  70)


def _box(pos, sc, tex, collide=True):
    return Entity(model='cube', texture=tex, position=pos, scale=sc,
                  collider='box' if collide else None)


def build_map():
    # Ground
    Entity(model='plane', scale=140, texture=T_GROUND, collider='box')

    # Roads
    _box((0, .01, 0),   (6, .02, 120),   T_ROAD, False)
    _box((0, .01, 0),   (120, .02, 6),   T_ROAD, False)

    # Perimeter walls
    for pos, sc in [
        (( 58, 3.5,   0), (1,  7, 118)),
        ((-58, 3.5,   0), (1,  7, 118)),
        ((  0, 3.5,  58), (118, 7, 1)),
        ((  0, 3.5, -58), (118, 7, 1)),
    ]:
        _box(pos, sc, T_CONCRETE)

    # Buildings
    for pos, sc, tex in [
        (( 0,  4,  22),  (20, 8, 10),  T_CONCRETE),
        ((-24,  3,  18),  (12, 6, 10),  T_CONC2),
        (( 24,  3,  18),  (12, 6, 10),  T_CONC2),
        ((-26, 3.5,-18),  (10, 7, 12),  T_DARK),
        (( 26, 3.5,-18),  (10, 7, 12),  T_DARK),
        ((  0, 2.5,-30),  (22, 5,  8),  T_CONCRETE),
        ((-42, 2.5,  5),  ( 8, 5, 20),  T_CONC2),
        (( 42, 2.5,  5),  ( 8, 5, 20),  T_CONC2),
        ((-14,   2, -8),  ( 6, 4,  6),  T_DARK),
        (( 14,   2, -8),  ( 6, 4,  6),  T_DARK),
        ((  0,   2,  38), (14, 4,  6),  T_CONC2),
    ]:
        _box(pos, sc, tex)

    # Watchtowers
    for cx, cz in [(50, 50), (-50, 50), (50, -50), (-50, -50)]:
        _box((cx,  5,  cz),   (3, 10, 3),   T_CONCRETE)
        _box((cx, 10.5, cz),  (5, .5, 5),   T_DARK)
        for rx, rz, sw, sd in [
            ( 2.4,   0, .15, 5.3), (-2.4,   0, .15, 5.3),
            (   0, 2.4, 5.3, .15), (   0, -2.4, 5.3, .15),
        ]:
            _box((cx+rx, 11.3, cz+rz), (sw, 1.6, sd), T_DARK, False)

    # Sandbag walls
    for pos, sc in [
        (( 6,   .55,  3),   (4.5, 1.1, 1.2)),
        ((-6,   .55,  3),   (4.5, 1.1, 1.2)),
        (( 3,   .55, -3),   (1.2, 1.1, 4.5)),
        ((-3,   .55, -3),   (1.2, 1.1, 4.5)),
        (( 11,  .55, -2),   (4,   1.1, 1.2)),
        ((-11,  .55, -2),   (4,   1.1, 1.2)),
        ((  0,  .55,  11),  (6,   1.1, 1.2)),
        ((  0,  .55, -11),  (6,   1.1, 1.2)),
        (( 19,  .55,  6),   (1.2, 1.1, 5)),
        ((-19,  .55,  6),   (1.2, 1.1, 5)),
        ((  0,  .55,  32),  (8,   1.1, 1.2)),
        (( 9,   .55,-22),   (1.2, 1.1, 4)),
        ((-9,   .55,-22),   (1.2, 1.1, 4)),
        (( 31,  .55, -8),   (1.2, 1.1, 6)),
        ((-31,  .55, -8),   (1.2, 1.1, 6)),
        (( 0,   .55, -42),  (10,  1.1, 1.2)),
        (( 15,  .55,  32),  (1.2, 1.1, 4)),
        ((-15,  .55,  32),  (1.2, 1.1, 4)),
    ]:
        _box(pos, sc, T_SANDBAG)

    # Crates
    for x, z in [(4,8),(-4,8),(13,12),(-13,12),(21,-5),(-21,-5),
                 (5,-15),(-5,-15),(26,30),(-26,30),(8,-35),(-8,-35)]:
        _box((x, .5, z), (1.4, 1, 1.4), T_CRATE)

    # Barrels
    for x, z in [(8,6),(-8,6),(15,-4),(-15,-4),(3,19),(-3,-19),(29,-2),(-29,-2),(0,-15)]:
        _box((x, .7, z), (.8, 1.4, .8), T_BARREL)

    # Metal barriers
    for pos, sc in [
        (( 12, .5, 0),  (3.5, 1, .4)),
        ((-12, .5, 0),  (3.5, 1, .4)),
        ((  0, .5, 12), (.4, 1, 3.5)),
        ((  0, .5,-12), (.4, 1, 3.5)),
        (( 35, .5, 35), (3.5, 1, .4)),
        ((-35, .5,-35), (3.5, 1, .4)),
    ]:
        _box(pos, sc, T_METAL)

    # Light poles
    for x, z in [(20,20),(-20,20),(20,-20),(-20,-20),(0,0)]:
        _box((x, 3.5, z), (.2, 7, .2),    T_METAL, False)
        _box((x, 7.2, z), (1, .15, .15),  T_METAL, False)
