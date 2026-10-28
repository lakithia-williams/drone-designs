"""Motor City drone show: 500 drones, one story.

Builds every formation from a color drawing, assigns drones to spots so paths stay short,
times each move so no drone goes faster than MAX_SPEED, checks spacing, and writes:
  output/show.json            keyframes for the web preview
  output/drones/drone_XXX.csv one flight path per drone (10 Hz), Skybrush CSV layout
"""
import json, math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.cluster.vq import kmeans2
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import pdist
from scipy.spatial import cKDTree

N = 500                 # drones
WIDTH_M = 150.0         # width of the picture in the sky, meters
BASE_ALT = 20.0         # lowest point of a formation, meters
CANVAS = (600, 300)     # drawing canvas, pixels
MAX_SPEED = 12.0        # m/s, top speed for any drone
MIN_TRANSITION = 2.5    # s
HOLD = 3.5              # s
MIN_SEP = 1.5           # m, required spacing
LAYERS = 13             # depth layers used to keep crossing paths apart
LAYER_GAP = 2.0         # m between layers
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

WHITE, GOLD, RED, BLUE, ORANGE, SILVER, DIM = (
    (255, 255, 255), (255, 190, 40), (230, 25, 35), (40, 110, 255),
    (255, 120, 20), (190, 205, 225), (45, 45, 70))


# ---------- drawing helpers (pixel canvas, y down) ----------

def canvas():
    img = Image.new("RGB", CANVAS, (0, 0, 0))
    return img, ImageDraw.Draw(img)


def text(d, s, size, color, cx, cy, spacing=10):
    f = ImageFont.truetype(FONT, size)
    l, t, r, b = d.multiline_textbbox((0, 0), s, font=f, align="center", spacing=spacing)
    d.multiline_text((cx - (r - l) / 2 - l, cy - (b - t) / 2 - t), s, font=f, fill=color,
                     align="center", spacing=spacing)


def P(ox, oy, k, pts):
    return [(ox + x * k, oy + y * k) for x, y in pts]


def draw_locomotive(d, ox, oy, k, c):
    w = max(9, int(9 * k))
    d.line(P(ox, oy, k, [(0, 110), (35, 50), (240, 50), (240, 0), (335, 0), (335, 110), (0, 110)]), fill=c, width=w)
    d.line(P(ox, oy, k, [(65, 50), (65, 2), (100, 2), (100, 50)]), fill=c, width=w)
    d.rectangle(P(ox, oy, k, [(258, 18), (317, 50)]), outline=c, width=w)
    for cx in (80, 155, 230, 300):
        d.ellipse(P(ox, oy, k, [(cx - 26, 112), (cx + 26, 164)]), outline=c, width=w)


def draw_jet(d, ox, oy, k, c):
    d.ellipse(P(ox, oy, k, [(0, 75), (400, 110)]), fill=c)
    d.polygon(P(ox, oy, k, [(160, 92), (250, 92), (190, 0)]), fill=c)
    d.polygon(P(ox, oy, k, [(160, 95), (250, 95), (190, 185)]), fill=c)
    d.polygon(P(ox, oy, k, [(360, 92), (400, 92), (410, 30)]), fill=c)


def draw_bike(d, ox, oy, k, c):
    w = max(9, int(10 * k))
    for cx in (70, 290):
        d.ellipse(P(ox, oy, k, [(cx - 70, 55), (cx + 70, 175)]), outline=c, width=w)
    d.line(P(ox, oy, k, [(70, 115), (155, 35), (260, 35), (180, 115), (70, 115)]), fill=c, width=w)
    d.line(P(ox, oy, k, [(180, 115), (155, 35)]), fill=c, width=w)
    d.line(P(ox, oy, k, [(260, 35), (290, 115)]), fill=c, width=w)
    d.line(P(ox, oy, k, [(135, 15), (180, 15)]), fill=c, width=w)
    d.line(P(ox, oy, k, [(155, 35), (150, 15)]), fill=c, width=w)
    d.line(P(ox, oy, k, [(260, 35), (270, 0), (300, 0)]), fill=c, width=w)


def draw_skyline(d, ox, oy, k, c):
    d.rectangle(P(ox, oy, k, [(215, 0), (265, 210)]), fill=c)                   # center tower
    for x0, top in ((170, 60), (275, 60), (140, 90), (305, 90)):
        d.rectangle(P(ox, oy, k, [(x0, top), (x0 + 35, 210)]), fill=c)
    for x0, top in ((30, 130), (75, 100), (380, 115), (425, 145)):
        d.rectangle(P(ox, oy, k, [(x0, top), (x0 + 35, 210)]), fill=c)


def draw_stock_car(d, ox, oy, k, c):
    w = max(9, int(10 * k))
    d.line(P(ox, oy, k, [(48, 98), (0, 98), (5, 58), (120, 43), (170, 0), (300, 0), (342, 43),
                         (420, 53), (425, 98), (382, 98)]), fill=c, width=w)
    d.line(P(ox, oy, k, [(128, 98), (302, 98)]), fill=c, width=w)
    d.line(P(ox, oy, k, [(182, 10), (182, 43), (292, 43)]), fill=c, width=w)
    d.ellipse(P(ox, oy, k, [(205, 50), (255, 92)]), outline=c, width=w)       # door number roundel
    for cx in (88, 342):
        d.ellipse(P(ox, oy, k, [(cx - 38, 66), (cx + 38, 142)]), outline=c, width=w)


def draw_flag(d, ox, oy, sq):
    for r in range(5):
        for col in range(7):
            c = WHITE if (r + col) % 2 == 0 else DIM
            d.rectangle([ox + col * sq, oy + r * sq, ox + (col + 1) * sq - 3, oy + (r + 1) * sq - 3], fill=c)


# ---------- the scenes ----------

def s_name():
    img, d = canvas()
    text(d, "LAKITHIA\nWILLIAMS", 92, WHITE, 300, 115, spacing=14)
    text(d, "PMP", 62, GOLD, 300, 262)
    return img


def s_work():
    img, d = canvas()
    draw_jet(d, 177, 6, 0.6, BLUE)
    draw_locomotive(d, 25, 160, 0.75, ORANGE)
    draw_bike(d, 330, 168, 0.7, RED)
    return img


def s_born():
    img, d = canvas()
    text(d, "BORN IN\nMOTORCITY", 58, WHITE, 300, 62, spacing=6)
    draw_skyline(d, 128, 136, 0.75, SILVER)
    return img


def s_blood():
    img, d = canvas()
    text(d, "AUTOMOTIVE", 78, WHITE, 300, 75)
    text(d, "RUNS IN THE BLOOD", 50, RED, 300, 205)
    return img


def s_car():
    img, d = canvas()
    draw_stock_car(d, 129, 4, 0.75, BLUE)
    text(d, "NEXT LAP", 46, WHITE, 300, 152)
    text(d, "FORD RACING", 64, WHITE, 300, 238)
    return img


def s_race():
    img, d = canvas()
    text(d, "READY TO RACE", 62, WHITE, 300, 40)
    draw_flag(d, 160, 95, 40)
    return img


def from_image(img, seed=7, n=N):
    a = np.asarray(img).astype(int)
    lum = a.max(axis=2)
    ys, xs = np.nonzero(lum > 30)
    px = np.column_stack([xs, ys]).astype(float)
    cent, _ = kmeans2(px, n, minit="++", seed=np.random.default_rng(seed), iter=40)
    cent = relax(cent, px, n=n)
    cent = repair(cent, px, MIN_SEP * 1.1 / (WIDTH_M / CANVAS[0]))
    cols = [tuple(int(v) for v in a[int(y), int(x)]) for x, y in cent]
    scale = WIDTH_M / CANVAS[0]
    x = (cent[:, 0] - CANVAS[0] / 2) * scale
    z = (CANVAS[1] - cent[:, 1]) * scale + BASE_ALT
    return np.column_stack([x, np.zeros(n), z]), cols


def relax(p, px, rounds=250, n=N):
    """Spread points apart while keeping each one on the drawing."""
    tree = cKDTree(px)
    target = math.sqrt(len(px) / n) * 1.05     # ideal spacing in pixels
    for _ in range(rounds):
        pairs = cKDTree(p).query_pairs(target, output_type="ndarray")
        if len(pairs) == 0:
            break
        dvec = p[pairs[:, 0]] - p[pairs[:, 1]]
        r = np.linalg.norm(dvec, axis=1) + 1e-6
        f = (0.25 * (target - r) / r)[:, None] * dvec
        move = np.zeros_like(p)
        np.add.at(move, pairs[:, 0], f)
        np.add.at(move, pairs[:, 1], -f)
        _, idx = tree.query(p + move)
        p = px[idx]
    return p


def repair(p, px, need, limit=3000):
    """Move the most crowded drone to the emptiest spot on the drawing until spacing is met."""
    p = p.copy()
    for _ in range(limit):
        d, i = cKDTree(p).query(p, k=2)
        worst = d[:, 1].argmin()
        if d[worst, 1] >= need:
            break
        gap, _ = cKDTree(np.delete(p, worst, 0)).query(px)
        p[worst] = px[gap.argmax()]
    return p


def ground_grid():
    g = np.array([(i, j) for i in range(25) for j in range(20)], float)
    pts = np.column_stack([(g[:, 0] - 12) * 2.5, (g[:, 1] - 9.5) * 2.5, np.zeros(N)])
    return pts, [DIM] * N


def lifted(z):
    p, c = ground_grid()
    return p + [0, 0, z], c


# (key, caption, (points, colors))
LINKEDIN = "https://linkedin.com/in/lakithia-williams"
QR_MODULE = 1.9         # m between QR squares


def s_qr():
    """LinkedIn QR code. Drones light the squares a printed code would have dark, so it reads
    light-on-dark (an inverted code). Drones left over spell CONNECT underneath."""
    import segno
    m = np.array(segno.make(LINKEDIN, error="m", micro=False).matrix, bool)
    rows, cols_ = np.nonzero(m)
    size = m.shape[0]
    x = (cols_ - (size - 1) / 2) * QR_MODULE
    z = (size - 1 - rows) * QR_MODULE + BASE_ALT + 22   # 4+ squares of dark sky between code and CONNECT
    pts = np.column_stack([x, np.zeros(len(x)), z])
    rest = N - len(pts)
    img, d = canvas()
    text(d, "CONNECT", 40, GOLD, 300, 268)
    tp, tc = from_image(img, n=rest)
    return np.vstack([pts, tp]), [WHITE] * len(pts) + tc


SCENES = [
    ("name", "Lakithia Williams, PMP", from_image(s_name())),
    ("born", "Born in MotorCity", from_image(s_born())),
    ("blood", "Automotive runs in the blood", from_image(s_blood())),
    ("work", "Norfolk Southern, UTC Aerospace and Collins Aerospace, Peloton", from_image(s_work())),
    ("car", "Next lap: Ford Racing", from_image(s_car())),
    ("race", "Ready to race", from_image(s_race())),
    ("qr", "Scan to connect on LinkedIn", s_qr()),
    ("land", "Landing", ground_grid()),
]


def closest(pos, leg, layer, steps):
    """Smallest gap between any two drones during a move."""
    best = 1e9
    for sv in np.linspace(0, 1, steps):
        e = 3 * sv * sv - 2 * sv ** 3
        p = pos + (leg - pos) * e
        p[:, 1] += layer * math.sin(math.pi * sv)
        best = min(best, cKDTree(p).query(p, k=2)[0][:, 1].min())
    return best


def peak_speed(pos, leg, layer, dur):
    pk = 0.0
    for u in np.linspace(0, 1, 101):
        vel = (leg - pos) * 6 * u * (1 - u) / dur
        vel[:, 1] += layer * math.pi * math.cos(math.pi * u) / dur
        pk = max(pk, np.linalg.norm(vel, axis=1).max())
    return pk


def build():
    os.makedirs(os.path.join(OUT, "drones"), exist_ok=True)
    pos, colors = SCENES[0][2][0].copy(), list(SCENES[0][2][1])
    segments, problems = [], []
    t = HOLD   # the show opens on the first picture, already lit
    keyframes = [{"t": 0.0, "scene": SCENES[0][0], "caption": SCENES[0][1],
                  "pos": pos.round(2).tolist(), "col": colors}]
    max_speed_seen, min_sep_seen = 0.0, 1e9
    for key, caption, (pts, tgt_cols) in SCENES[1:]:
        sep = pdist(pts).min()
        min_sep_seen = min(min_sep_seen, sep)
        if sep < MIN_SEP:
            problems.append(f"{key}: formation spacing {sep:.2f} m")
        cost = ((pos[:, None, :] - pts[None, :, :]) ** 2).sum(-1)
        _, c = linear_sum_assignment(cost)
        target = pts[c]
        new_cols = [tgt_cols[j] for j in c]
        # Moves between the flat launch grid and an upright picture go in two legs so
        # paths never cross: first slide within your own depth row, then change depth.
        if key == "name":
            legs = [np.column_stack([target[:, 0], pos[:, 1], target[:, 2]]), target]
        elif key == "land":
            # three legs so no paths cross: slide to your landing row, drop to 12 m over your pad, set down
            legs = [np.column_stack([pos[:, 0], target[:, 1], pos[:, 2]]),
                    np.column_stack([target[:, 0], target[:, 1], np.full(N, 12.0)]), target]
        else:
            legs = [target]
        for li, leg in enumerate(legs):
            last = li == len(legs) - 1
            if len(legs) == 1 and key not in ("climb", "land"):
                # try several ways of handing out depth layers and keep the one with the most room
                rng = np.random.default_rng(11)
                options = [np.argsort(np.argsort(pos[:, 0] + a * pos[:, 2])) for a in (0.37, -0.6, 1.7)]
                options += [rng.permutation(N) for _ in range(30)]
                best = None
                for order in options:
                    lay = ((order % LAYERS) - (LAYERS - 1) / 2) * LAYER_GAP
                    room = closest(pos, leg, lay, 121)
                    if best is None or room > best[0]:
                        best = (room, lay)
                layer = best[1]
            else:
                layer = np.zeros(N)
            dur = MIN_TRANSITION if (last or key == "land") else 1.5
            while peak_speed(pos, leg, layer, dur) > MAX_SPEED:
                dur += 0.5
            pk = peak_speed(pos, leg, layer, dur)
            dmin = closest(pos, leg, layer, 201)
            min_sep_seen = min(min_sep_seen, dmin)
            if dmin < MIN_SEP:
                problems.append(f"into {key} leg {li}: {dmin:.2f} m")
            max_speed_seen = max(max_speed_seen, pk)
            segments.append({"start": t, "dur": dur, "layer": layer.round(2).tolist()})
            t += dur
            pos = leg
            keyframes.append({"t": t, "scene": key if last else key + "-leg", "caption": caption,
                              "pos": pos.round(2).tolist(), "col": new_cols if last else colors})
        colors = new_cols
        t += 0 if key == "land" else (8.0 if key == "qr" else HOLD)   # extra time to scan
    show = {"drones": N, "duration": t, "maxSpeed": round(max_speed_seen, 2),
            "minSeparation": round(min_sep_seen, 2), "keyframes": keyframes, "segments": segments}
    with open(os.path.join(OUT, "show.json"), "w") as f:
        json.dump(show, f, separators=(",", ":"))
    write_csvs(show)
    return show, problems


def sample(show, time):
    kf, seg = show["keyframes"], show["segments"]
    for i, s in enumerate(seg):
        a, b = kf[i], kf[i + 1]
        if time < s["start"]:
            return np.array(a["pos"]), a["col"]
        if time <= s["start"] + s["dur"]:
            u = (time - s["start"]) / s["dur"]
            e = 3 * u * u - 2 * u ** 3
            p = np.array(a["pos"]) + (np.array(b["pos"]) - np.array(a["pos"])) * e
            p[:, 1] += np.array(s["layer"]) * math.sin(math.pi * u)
            cols = [tuple(int(ca[k] + (cb[k] - ca[k]) * e) for k in range(3))
                    for ca, cb in zip(a["col"], b["col"])]
            return p, cols
    return np.array(kf[-1]["pos"]), kf[-1]["col"]


def write_csvs(show):
    for f in os.listdir(os.path.join(OUT, "drones")):
        os.remove(os.path.join(OUT, "drones", f))
    times = np.arange(0, show["duration"] + 1e-9, 0.1)
    rows = [[] for _ in range(N)]
    for tm in times:
        p, cols = sample(show, tm)
        for i in range(N):
            rows[i].append(f"{int(round(tm * 1000))},{p[i,0]:.2f},{p[i,1]:.2f},{p[i,2]:.2f},{cols[i][0]},{cols[i][1]},{cols[i][2]}")
    for i in range(N):
        with open(os.path.join(OUT, "drones", f"drone_{i+1:03d}.csv"), "w") as f:
            f.write("Time [msec],x [m],y [m],z [m],Red,Green,Blue\n" + "\n".join(rows[i]) + "\n")


if __name__ == "__main__":
    show, problems = build()
    print(f"duration {show['duration']:.0f} s, max speed {show['maxSpeed']} m/s, "
          f"min separation {show['minSeparation']} m")
    print("problems:", problems or "none")
