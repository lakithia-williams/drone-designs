"""Re-checks the exported flight files: speed, spacing, altitude. Also draws a contact sheet."""
import json, glob, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial.distance import pdist
show = json.load(open('output/show.json'))
files = sorted(glob.glob('output/drones/*.csv'))
data = np.stack([np.loadtxt(f, delimiter=',', skiprows=1) for f in files])
P = data[:, :, 1:4]
v = np.linalg.norm(np.diff(P, axis=1), axis=2) / 0.1
sep = min(pdist(P[:, k]).min() for k in range(P.shape[1]))
print(f"{len(files)} drones, {P.shape[1]} samples, max speed {v.max():.2f} m/s, "
      f"min spacing {sep:.2f} m, max altitude {P[:, :, 2].max():.1f} m, duration {show['duration']:.0f} s")
if len(sys.argv) > 1:
    kfs = [k for k in show['keyframes'] if not k['scene'].endswith('-leg')]
    W, H, cols = 360, 220, 4
    rows = (len(kfs) + cols - 1) // cols
    sheet = Image.new('RGB', (W * cols, H * rows), (5, 8, 20)); d = ImageDraw.Draw(sheet)
    for n, k in enumerate(kfs):
        p = np.array(k['pos']); ox, oy = (n % cols) * W, (n // cols) * H
        flat = k['scene'] in ('ground', 'climb', 'descend', 'land')
        for (x, y, z), c in zip(p, k['col']):
            u = ox + W / 2 + x * 2.3; w = oy + H - 12 - ((y + 26) * 3 if flat else z * 2.3 - 40)
            d.ellipse([u - 1.6, w - 1.6, u + 1.6, w + 1.6], fill=tuple(c) if tuple(c) != (40, 40, 60) else (90, 90, 120))
        d.text((ox + 6, oy + 4), k['scene'], fill=(200, 200, 200))
    sheet.save(sys.argv[1])
