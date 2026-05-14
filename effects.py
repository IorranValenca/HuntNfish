"""Shared visual effects — blood splat, etc."""
from ursina import *
from game_utils import solid
import random

_T_BLOOD_A = None
_T_BLOOD_B = None
_T_BLOOD_C = None


def _init():
    global _T_BLOOD_A, _T_BLOOD_B, _T_BLOOD_C
    if _T_BLOOD_A is None:
        _T_BLOOD_A = solid(118,  16,  16)
        _T_BLOOD_B = solid(180,  24,  24)
        _T_BLOOD_C = solid( 88,  10,  10)


class _BloodDrop(Entity):
    def __init__(self, position, velocity, tex, size):
        super().__init__(model='sphere', texture=tex,
                         scale=size, position=position)
        self._vel  = velocity
        self._life = random.uniform(0.55, 1.05)
        self._stuck = False

    def update(self):
        dt = time.dt
        self._life -= dt
        if self._life <= 0:
            destroy(self); return
        if self._stuck:
            return
        self._vel.y -= 18.0 * dt
        self.position += self._vel * dt
        if self.y <= 0.02:
            self.y = 0.02
            self._stuck = True
            self.scale_y = self.scale_y * 0.35


def blood_splat(world_pos, n=14, intensity=1.0):
    """Spawn a red particle burst at a hit location."""
    _init()
    for _ in range(n):
        v = Vec3(random.uniform(-2.6, 2.6),
                 random.uniform(0.9, 4.2),
                 random.uniform(-2.6, 2.6)) * intensity
        tex  = random.choice([_T_BLOOD_A, _T_BLOOD_B, _T_BLOOD_C])
        size = random.uniform(0.05, 0.11) * intensity
        _BloodDrop(world_pos, v, tex, size)
