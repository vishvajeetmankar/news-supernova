"""2D 'puppet' anchor v2: full-res cutout + audio-driven mouth (shape + daant/jeebh), blink, brow, head roll/nod/turn, breathing.
MediaPipe FaceMesh landmarks + OpenCV warps. 30 sec ka clip ~1 min me (XTalker 36 min leta tha)."""
import math, random, subprocess
from pathlib import Path
import numpy as np, cv2

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "assets" / "anchor.png"
FPS = 25
UP_IN = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308]    # inner upper lip
LO_IN = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308]    # inner lower lip
EYE_SPECS = [  # corner A, corner B, upper contour (A->B), lower contour (A->B)
    (33, 133, [33, 246, 161, 160, 159, 158, 157, 173, 133], [33, 7, 163, 144, 145, 153, 154, 155, 133]),
    (362, 263, [362, 398, 384, 385, 386, 387, 388, 466, 263], [362, 382, 381, 380, 374, 373, 390, 249, 263]),
]
BROWS = [[70, 63, 105, 66, 107], [336, 296, 334, 293, 300]]

def _ss(x, a, b):
    t = np.clip((x - a) / (b - a + 1e-9), 0, 1); return t * t * (3 - 2 * t)

def _gs(x, sigma):
    k = np.arange(-int(sigma * 3) - 1, int(sigma * 3) + 2); w = np.exp(-0.5 * (k / sigma) ** 2); w /= w.sum()
    return np.convolve(np.pad(x, (len(k) // 2, len(k) // 2), mode="edge"), w, mode="valid")[:len(x)]

def features(wav, fps=FPS):
    """Awaaz se per-frame: open (loudness, relative dB), cen (spectral centroid 0..1: 0 gol/'oo', 1 chauda/'ee,s')."""
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(wav), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0
    hop = 16000 // fps; n = max(len(a) // hop, 1); fr = a[:n * hop].reshape(n, hop)
    db = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-4)
    lo, hi = np.percentile(db, 22), np.percentile(db, 96)
    t = np.clip((db - lo) / (hi - lo + 1e-6), 0, 1)
    t = np.where(t < 0.12, 0.0, t) ** 1.25
    S = np.abs(np.fft.rfft(fr * np.hanning(hop), axis=1)); f = np.fft.rfftfreq(hop, 1 / 16000)
    cen = np.clip(((S * f).sum(1) / (S.sum(1) + 1e-9) - 600) / 2600, 0, 1)
    env = np.zeros_like(t); o = 0.0
    for i, v in enumerate(t):                              # fast attack, slower release
        o = v if v > o else o * 0.5 + v * 0.5; env[i] = o
    return env, _gs(cen, 1.5)

class Puppet:
    def __init__(self, path=IMG, seed=7):
        im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if im.ndim == 2: im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
        if im.shape[2] == 3: im = np.dstack([im, np.full(im.shape[:2], 255, np.uint8)])
        straight = cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA); self.h, self.w = straight.shape[:2]; self.straight = straight
        a = straight[:, :, 3:4].astype(np.float32) / 255.0                     # premultiplied: fringe nahi aata
        self.rgba = np.dstack([(straight[:, :, :3] * a).astype(np.uint8), straight[:, :, 3]])
        self.rng = random.Random(seed); self.m = None
        self._landmarks(); self._prep_mouth(); self._prep_eyes(); self._prep_head()

    # ---------------- geometry ----------------
    def _landmarks(self):
        import mediapipe as mp
        fm = mp.solutions.face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True)
        res = fm.process(self.straight[:, :, :3]); fm.close()
        if not res.multi_face_landmarks: raise RuntimeError("anchor image me chehra detect nahi hua")
        self.L = np.array([(p.x * self.w, p.y * self.h) for p in res.multi_face_landmarks[0].landmark], np.float32)

    def _roi(self, x0, y0, x1, y1):
        x0, y0 = max(int(x0), 0), max(int(y0), 0); x1, y1 = min(int(x1), self.w), min(int(y1), self.h)
        Y, X = np.mgrid[y0:y1, x0:x1].astype(np.float32); return (x0, y0, x1, y1), X, Y

    def _prep_mouth(self):
        L = self.L; ax = L[291] - L[61]
        self.mw = float(np.linalg.norm(ax)); self.u = ax / self.mw; self.n = np.array([-self.u[1], self.u[0]], np.float32)
        self.c = (L[13] + L[14]) / 2; self.cv = float((L[152] - self.c) @ self.n)
        up, lo = L[UP_IN], L[LO_IN]
        uu, uv = (up - self.c) @ self.u, (up - self.c) @ self.n; lu, lv = (lo - self.c) @ self.u, (lo - self.c) @ self.n
        ol = np.argsort(lu); sv = (uv + np.interp(uu, lu[ol], lv[ol])) / 2; os_ = np.argsort(uu)
        self.seam_u, self.seam_v = uu[os_], sv[os_]
        self.roi, self.X, self.Y = self._roi(self.c[0] - 1.8 * self.mw, self.c[1] - 1.0 * self.mw, self.c[0] + 1.8 * self.mw, L[152][1] + 0.7 * self.mw)
        self.Mf = self._mfield(self.X, self.Y)
        self.dmax = 0.20 * self.mw

    def _mfield(self, X, Y):
        U = (X - self.c[0]) * self.u[0] + (Y - self.c[1]) * self.u[1]; V = (X - self.c[0]) * self.n[0] + (Y - self.c[1]) * self.n[1]
        s = 0.3 + 0.35 * self.mw * _ss(np.abs(U), 0.4 * self.mw, 0.85 * self.mw)
        wv = _ss(V - np.interp(U, self.seam_u, self.seam_v), -s, s); wf = 1 - _ss(V, self.cv * 0.75, self.cv * 1.35)
        wu = np.exp(-(np.abs(U) / (0.62 * self.mw)) ** 2.5)
        wm = np.exp(-(np.abs(U) / (1.1 * self.mw)) ** 2) * np.exp(-(V / (0.75 * self.mw)) ** 2)   # chehra-width (muh chauda/gol) ka zone
        return dict(M=wv * wf * wu, Mh=wf * wu, U=U, V=V, Wm=wm)

    def _disp(self, X, Y, d, g, lip=None):
        """Mouth displacement (dx, dy): jabda niche (d) + muh chauda/gol (g).
        lip=None: pixel field. lip='up'/'lo': inner-lip landmarks (upar wali sthir, neeche wali poori d)."""
        f = self._mfield(X, Y); sw = g * 0.16 * f["U"] * f["Wm"]
        m = f["M"] if lip is None else (0.0 * f["Mh"] if lip == "up" else f["Mh"])
        return d * m * self.n[0] + sw * self.u[0], d * m * self.n[1] + sw * self.u[1]

    def _prep_eyes(self):
        self.eyes = []; base = self.rgba
        for (A, B, up, lo) in EYE_SPECS:
            U, Lw = self.L[up].copy(), self.L[lo].copy(); ax = self.L[B] - self.L[A]; ew = float(np.linalg.norm(ax)); u = ax / ew
            n = np.array([-u[1], u[0]], np.float32)
            if n[1] < 0: n = -n
            eh = max(float(np.mean((Lw - U) @ n)), 3.0)
            pts = np.vstack([U, Lw]); roi, _, _ = self._roi(pts[:, 0].min() - 10, pts[:, 1].min() - 0.8 * eh - 10, pts[:, 0].max() + 10, pts[:, 1].max() + 10)
            x0, y0, x1, y1 = roi; off = np.array([x0, y0], np.float32); rgb = base[y0:y1, x0:x1, :3].copy()
            hole = np.zeros(rgb.shape[:2], np.uint8)
            poly = np.vstack([U - n * (0.45 * eh + 3), (Lw + n * (0.30 * eh + 2))[::-1]]) - off
            cv2.fillPoly(hole, [np.round(poly).astype(np.int32)], 255); hole = cv2.dilate(hole, np.ones((5, 5), np.uint8))
            col = cv2.inpaint(rgb, hole, 6, cv2.INPAINT_TELEA)            # aas-paas ki skin se band-palak wali skin
            self.eyes.append(dict(U=U, Lw=Lw, n=n, eh=eh, ew=ew, skin=col.astype(np.float32), roi=roi))

    def _prep_head(self):
        L = self.L; chin, top = L[152], L[10]; fh = float(np.linalg.norm(chin - top)); self.fh = fh
        self.pivot = np.array([L[1][0], chin[1] + 0.35 * fh], np.float32)
        ye = int(min(self.h, chin[1] + 0.55 * fh)); self.head_ye = ye
        Y, X = np.mgrid[0:ye, 0:self.w].astype(np.float32); self.HX, self.HY = X, Y
        self.wh = 1 - _ss(Y, chin[1] + 0.02 * fh, chin[1] + 0.42 * fh)                       # sir hilta hai, kandhe nahi
        fc = L[1]; ax_, ay_ = 0.52 * fh, 0.62 * fh
        self.wy = np.exp(-(((X - fc[0]) / ax_) ** 2 + ((Y - fc[1]) / ay_) ** 2) ** 1.2)       # chehra 'ghoomne' ka parallax zone
        bw = float(np.linalg.norm(L[107] - L[70]))
        self.wb = np.zeros_like(X)
        for br in BROWS:
            bc = L[br].mean(0); self.wb += np.exp(-(((X - bc[0]) / (0.8 * bw)) ** 2 + ((Y - bc[1]) / (0.30 * bw)) ** 2))
        self.wb = np.clip(self.wb, 0, 1) * self.wh

    # ---------------- motion (audio se) ----------------
    def prepare(self, wav):
        env, cen = features(wav); N = len(env); t = np.arange(N) / FPS; r = self.rng
        ph = lambda: r.uniform(0, 6.28)
        sn = lambda comps: sum(a * np.sin(2 * math.pi * f * t + ph()) for f, a in comps)
        slow = np.convolve(np.pad(env, (6, 0), mode="edge"), np.ones(7) / 7, "valid")[:N]
        beat = _gs(np.clip(env - slow, 0, 1), 1.6)                                           # emphasis peaks
        beat = beat / (beat.max() + 1e-6)
        fric = _ss(cen, 0.55, 0.85) * (env > 0.1)
        blink = np.zeros(N); x = r.uniform(0.8, 2.0)
        while x < N / FPS:
            for k in range(6):                                                                # 0.24s blink
                i = int((x + k / FPS) * FPS)
                if i < N: blink[i] = (0.35, 0.8, 1.0, 0.85, 0.5, 0.2)[k]
            x += r.uniform(2.2, 4.6)
        self.m = dict(
            N=N, env=env,
            open=np.clip(env * 0.92 * (1 - 0.5 * fric), 0, 1),
            width=np.clip(_gs((cen - 0.45) * 1.7, 1.2), -0.8, 0.9),
            roll=0.65 * sn([(0.21, 1), (0.53, 0.5)]) + 0.9 * beat * np.sin(np.arange(N) * 0.31),
            yaw=sn([(0.17, 1), (0.41, 0.5)]) + 0.8 * _gs(env - slow, 4),
            tx=1.8 * sn([(0.19, 1)]), ty=2.2 * sn([(0.23, 1), (0.6, 0.3)]) + 6.0 * beat,
            brow=4.5 * beat + 0.8 * np.clip(sn([(0.31, 1)]), 0, 1), blink=blink)

    # ---------------- per-frame ----------------
    def frame(self, i):
        m = self.m; i = int(min(max(i, 0), m["N"] - 1)); img = self.rgba.copy()
        self._blink(img, float(m["blink"][i])); self._mouth(img, float(m["open"][i]), float(m["width"][i]))
        return self._head(img, i)

    def _blink(self, img, b):
        if b < 0.05: return
        for e in self.eyes:
            x0, y0, x1, y1 = e["roi"]; sub = img[y0:y1, x0:x1, :3].astype(np.float32); off = np.array([x0, y0], np.float32)
            lid = e["U"] + b * (e["Lw"] - e["U"]); top = e["U"] - e["n"] * (0.22 * e["eh"] + 1.5)
            poly = np.vstack([top, lid[::-1]]) - off; m = np.zeros(sub.shape[:2], np.float32)
            cv2.fillPoly(m, [np.round(poly * 16).astype(np.int32)], 1.0, cv2.LINE_AA, 4); m = cv2.GaussianBlur(m, (0, 0), 0.9)
            sub = sub * (1 - m[..., None]) + e["skin"] * m[..., None]
            ln = np.zeros(sub.shape[:2], np.float32)
            cv2.polylines(ln, [np.round((lid - off) * 16).astype(np.int32)], False, 1.0, max(1, int(round(e["ew"] * 0.028))), cv2.LINE_AA, 4)
            ln = cv2.GaussianBlur(ln, (0, 0), 0.8) * 0.6
            sub = sub * (1 - ln[..., None]) + np.array([52, 34, 34], np.float32) * ln[..., None]
            img[y0:y1, x0:x1, :3] = np.clip(sub, 0, 255).astype(np.uint8)

    def _mouth(self, img, o, g):
        if o < 0.03 and abs(g) < 0.05: return
        x0, y0, x1, y1 = self.roi; d = o * self.dmax; src = img[y0:y1, x0:x1].copy()
        dx, dy = self._disp(self.X, self.Y, d, g)
        warped = cv2.remap(src, (self.X - dx - x0).astype(np.float32), (self.Y - dy - y0).astype(np.float32), cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        if o >= 0.03:
            up, lo = self.L[UP_IN].copy(), self.L[LO_IN].copy()
            udx, udy = self._disp(up[:, 0], up[:, 1], d, g, "up"); ldx, ldy = self._disp(lo[:, 0], lo[:, 1], d, g, "lo")
            up += np.stack([udx, udy], 1); lo += np.stack([ldx, ldy], 1)
            poly = np.vstack([up, lo[::-1][1:-1]]) - [x0, y0]
            m = np.zeros(warped.shape[:2], np.float32); cv2.fillPoly(m, [np.round(poly * 16).astype(np.int32)], 1.0, cv2.LINE_AA, 4)
            m = cv2.GaussianBlur(m, (0, 0), 0.9)
            U, V = self.Mf["U"], self.Mf["V"]
            uu, uv = (up - self.c) @ self.u, (up - self.c) @ self.n; lu, lv = (lo - self.c) @ self.u, (lo - self.c) @ self.n
            ou, ol = np.argsort(uu), np.argsort(lu)
            vup = np.interp(U, uu[ou], uv[ou]); vlo = np.interp(U, lu[ol], lv[ol]); gap = np.maximum(vlo - vup, 1.0)
            dep = np.clip((V - vup) / gap, 0, 1)                                    # 0 = upar wali lip, 1 = neeche wali lip
            half = max(float(uu.max() - uu.min()) / 2, 1.0); cu = np.abs(U - float(uu.mean())) / half
            base = np.array([132, 38, 50], np.float32) * (1 - 0.32 * np.sin(dep * math.pi))[..., None]    # andar gehra laal (kaala nahi)
            tongue = (_ss(dep, 0.40, 0.58) * np.exp(-(cu / 0.62) ** 2) * np.clip((gap - 5) / 10, 0, 1))[..., None]
            tcol = np.array([205, 98, 112], np.float32) * (1 - 0.25 * (1 - _ss(dep, 0.5, 0.9)))[..., None]
            inside = base * (1 - tongue * 0.9) + tcol * tongue * 0.9
            th = np.minimum(0.24, 0.055 * self.mw / gap)
            teeth = (1 - _ss(dep, th, th + 0.12)) * np.clip((gap - 2) / 5, 0, 1)
            shade = (0.97 - 0.22 * (1 - _ss(dep, 0.0, th + 0.05))) * (0.90 + 0.10 * np.cos(cu * 1.4))   # upar chhaya, beech ujla
            tc = np.array([232, 222, 208], np.float32) * shade[..., None]
            inside = inside * (1 - teeth[..., None] * 0.92) + tc * teeth[..., None] * 0.92
            inside *= (1 - 0.35 * (1 - _ss(dep, 0.0, 0.10)) * (1 - teeth))[..., None]                # upper-lip ke neeche halki chhaya
            out = warped[:, :, :3].astype(np.float32) * (1 - m[..., None]) + inside * m[..., None]
            warped[:, :, :3] = np.clip(out, 0, 255).astype(np.uint8)
        img[y0:y1, x0:x1] = warped

    def _head(self, img, i):
        m = self.m; th = math.radians(float(m["roll"][i])); c, s = math.cos(th), math.sin(th)
        px, py = self.HX - self.pivot[0], self.HY - self.pivot[1]
        dx = self.wh * ((c - 1) * px - s * py + float(m["tx"][i])) + float(m["yaw"][i]) * 3.2 * self.wy
        dy = self.wh * (s * px + (c - 1) * py + float(m["ty"][i])) - float(m["brow"][i]) * self.wb
        ye = self.head_ye
        img[:ye] = cv2.remap(img[:ye], self.HX - dx, self.HY - dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        return img

    def camera(self, img, t, out_w, speak=0.0):
        """Poore body ka halka saans/sway. Premultiplied RGBA out_w width par."""
        s = out_w / self.w; oh = int(round(self.h * s))
        ang = 0.25 * math.sin(2 * math.pi * 0.19 * t + 0.6)
        sc = 1 + 0.005 * math.sin(2 * math.pi * 0.27 * t) + 0.003 * speak
        Mx = cv2.getRotationMatrix2D((self.w * 0.5, self.h * 0.95), ang, sc); Mx[1, 2] += 1.5 * math.sin(2 * math.pi * 0.27 * t); Mx = Mx * s
        return cv2.warpAffine(img, Mx, (out_w, oh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    def render(self, t, out_w):
        i = int(round(t * FPS)); i = min(max(i, 0), self.m["N"] - 1)
        return self.camera(self.frame(i), t, out_w, float(self.m["env"][i]))

def with_shadow(cam, sa):
    """cam: premultiplied RGBA, sa: soft shadow alpha -> (straight RGB, alpha 0..1)."""
    a = cam[:, :, 3].astype(np.float32) / 255.0; a2 = a + sa * (1 - a)
    rgb = np.clip(cam[:, :, :3].astype(np.float32) / np.maximum(a2, 1e-3)[..., None], 0, 255).astype(np.uint8)
    return rgb, a2

def shadow_alpha(cam, strength=0.5):
    a = cam[:, :, 3].astype(np.float32) / 255.0; k = max(3, int(a.shape[1] * 0.04) | 1)
    sh = cv2.GaussianBlur(a, (k * 2 + 1, k * 2 + 1), k / 2.2)
    k2 = int(a.shape[1] * 0.018); out = np.zeros_like(sh); out[k2:] = sh[:-k2]
    return out * strength

def unpremultiply(rgba):
    a = rgba[:, :, 3:4].astype(np.float32) / 255.0
    return np.clip(rgba[:, :, :3].astype(np.float32) / np.maximum(a, 1e-3), 0, 255).astype(np.uint8), a[:, :, 0]
