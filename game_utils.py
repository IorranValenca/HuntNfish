"""Shared 1x1 pixel texture helper — avoids the Ursina color/shader bug."""
from ursina import Texture as UrsinaTexture
from panda3d.core import Texture as P3DTex, PNMImage

_tex_cache = {}

def solid(r, g, b):
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
