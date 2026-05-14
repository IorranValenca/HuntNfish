"""
Auto-orient a GLTF weapon model and save a ready-to-use BAM.

Usage:
    python bake_model.py <gltf_path> <out_bam_path> [--flip]

Examples:
    python bake_model.py model_rifle/scene.gltf   model_rifle/ready.bam
    python bake_model.py model_revolver/scene.gltf model_revolver/ready.bam
    python bake_model.py model_rod/scene.gltf      model_rod/ready.bam  --flip

The script finds which axis the model's longest dimension runs along,
then applies the roll/pitch needed so that axis points along Panda3D Z
(= Ursina +Z = forward).  Pass --flip if the muzzle end ends up pointing
backward after the first bake.
"""
import sys
from direct.showbase.ShowBase import ShowBase
from panda3d.core import Point3

base = ShowBase()

args    = sys.argv[1:]
src     = args[0]
dst     = args[1]
do_flip = '--flip' in args

model = base.loader.loadModel(src)
if not model:
    print(f'ERROR: could not load {src}')
    sys.exit(1)

model.flattenStrong()
mn, mx = Point3(), Point3()
model.calcTightBounds(mn, mx)
sz = mx - mn
print(f'Original bounds  X={sz.x:.3f}  Y={sz.y:.3f}  Z={sz.z:.3f}')

longest = max(sz.x, sz.y, sz.z)

# Rotate the longest axis onto Panda3D Z (= Ursina forward).
# R=roll rotates around Y; H=heading rotates around Z.
if abs(sz.x - longest) < 0.01:
    # Barrel along X  →  R=90 moves X to +Z
    rot = (0, 0, 90 if not do_flip else -90)
    print('Barrel axis: X  →  applying R=90')
elif abs(sz.y - longest) < 0.01:
    # Barrel along Y  →  P=-90 moves Y to +Z  (P=pitch rotates around X)
    rot = (0, -90 if not do_flip else 90, 0)
    print('Barrel axis: Y  →  applying P=-90')
else:
    # Already along Z
    rot = (0, 180 if do_flip else 0, 0)
    print('Barrel axis: Z  →  no roll/pitch needed')

m2 = base.loader.loadModel(src)
m2.setHpr(*rot)
m2.flattenStrong()

mn2, mx2 = Point3(), Point3()
m2.calcTightBounds(mn2, mx2)
sz2 = mx2 - mn2
print(f'After rotation   X={sz2.x:.3f}  Y={sz2.y:.3f}  Z={sz2.z:.3f}')
print(f'Muzzle at Z={mx2.z:.3f}  (should be positive for forward barrel)')

m2.writeBamFile(dst)
print(f'Saved: {dst}')
