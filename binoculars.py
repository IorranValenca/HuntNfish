"""Binoculars — hold right-click to zoom; left-click to tag an animal.
Tagged animals stay highlighted on the mini-map until they die or are collected."""
from ursina import *
from game_utils import solid
import math

player_ref      = None
hud_ref         = None
animals_mod_ref = None

# Module-level set of tagged animal entities; mini-map / HUD can read.
tagged_animals = set()


class Binoculars(Entity):
    HIP_POS  = Vec3(.22, -.20, .30)
    UP_POS   = Vec3(.00, -.10, .22)
    ZOOM_FOV = 18
    RANGE    = 400.0

    def __init__(self):
        super().__init__(parent=camera, position=self.HIP_POS)
        self._gun_root = Entity(parent=self)
        T_SHELL  = solid( 30,  34,  42)
        T_RUBBER = solid( 18,  18,  18)
        T_GLASS  = solid( 20,  60,  90)
        T_METAL  = solid( 80,  82,  88)
        T_STRAP  = solid( 60,  40,  22)

        def P(mdl, sc, pos, tex, **kw):
            return Entity(parent=self._gun_root, model=mdl,
                          scale=sc, position=pos, texture=tex, **kw)

        # Two barrel tubes
        for sx in (-.045, .045):
            P('cube', (.060, .060, .140), (sx, .000, .080), T_SHELL)
            P('cube', (.066, .066, .020), (sx, .000, .002), T_RUBBER)  # eyecup
            P('cube', (.072, .072, .024), (sx, .000, .156), T_RUBBER)  # obj rim
            P('cube', (.054, .054, .014), (sx, .000, .160), T_GLASS)   # lens
            # Focus ring
            P('cube', (.064, .064, .020), (sx, .000, .060), T_METAL)
        # Center bridge / hinge
        P('cube', (.040, .040, .120), (0, .000, .070), T_SHELL)
        P('sphere', .022,              (0, .000, .020), T_METAL)
        # Center focus wheel
        P('cube', (.034, .024, .024), (0, .020, .100), T_METAL)

        # Strap nub on top
        P('cube', (.018, .010, .014), (0, .032, .060), T_STRAP)

        self.state = 'ready'
        self._ads  = False
        self._sway = Vec3(0, 0, 0)
        self._bob_t = 0.0

    # ── Input ───────────────────────────────────────────────────────────────
    def try_shoot(self):
        """Left click = tag whatever animal is in the crosshair."""
        ignore = [player_ref, self, self._gun_root]
        hit = raycast(camera.world_position, camera.forward,
                      distance=self.RANGE, ignore=ignore)
        if hit.hit and hasattr(hit.entity, '_loot_display_name'):
            tagged_animals.add(hit.entity)
            name = hit.entity._loot_display_name
            dist = (camera.world_position - hit.world_point).length()
            if hud_ref:
                hud_ref.add_log(f'TAGGED  {name}  ({int(dist)} m)')

    def update(self):
        if not self.enabled:
            return
        dt = time.dt

        self._ads = bool(held_keys['right mouse'])
        target = self.UP_POS if self._ads else self.HIP_POS
        camera.fov = lerp(camera.fov, self.ZOOM_FOV if self._ads else 80, dt * 12)

        moving = any(held_keys[k] for k in ('w','a','s','d'))
        if moving and not self._ads:
            self._bob_t += dt * 5.5
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

        # Prune tagged animals that died / despawned
        if tagged_animals:
            for a in list(tagged_animals):
                if not a or getattr(a, 'state', '') == 'dead':
                    tagged_animals.discard(a)

    def on_disable(self):
        self._ads = False
        camera.fov = 80
