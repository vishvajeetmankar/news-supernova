"""Fast 2D 'puppet' anchor: full-res cutout photo + audio-driven mouth, breathing, head sway.
MediaPipe FaceMesh se landmarks, OpenCV se warp. 12 sec ka clip seconds me banta hai (XTalker 36 min leta tha)."""
import math, random, subprocess
from pathlib import Path
import numpy as np, cv2

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "assets" / "anchor.png"
UP_IN = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308]    # inner upper lip
LO_IN = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308]    # inner lower lip
FPS = 25

def _ss(x, a, b):
    t = np.clip((x - a) / (b - a + 1e-9), 0, 1); return t * t * (3 - 2 * t)

def envelope(wav, fps=FPS):
    """Awaaz ka loudness har video-frame ke liye (0..1), silence = 0."""
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(wav), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0
    hop = 16000 // fps; n = len(a) // hop
    r = np.sqrt((a[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
    db = 20 * np.log10(r + 1e-4)                            # dB me relative: compressed voice me bhi shabdon ke beech gap dikhe
    lo, hi = np.percentile(db, 22), np.percentile(db, 96)
    t = np.clip((db - lo) / (hi - lo + 1e-6), 0, 1)
    t = np.where(t < 0.12, 0.0, t) ** 1.25 * 0.88           # gate + peaks pe zor
    out = np.zeros_like(t); o = 0.0
    for i, v in enumerate(t):                              # fast attack, slower release
        o = v if v > o else o * 0.5 + v * 0.5
        out[i] = o
    return out

class Puppet:
    def __init__(self, path=IMG, seed=7):
        im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if im.ndim == 2: im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
        if im.shape[2] == 3: im = np.dstack([im, np.full(im.shape[:2], 255, np.uint8)])
        straight = cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA)
        self.h, self.w = straight.shape[:2]; self.straight = straight
        a = straight[:, :, 3:4].astype(np.float32) / 255.0                  # premultiplied: halo/fringe nahi aata
        self.rgba = np.dstack([(straight[:, :, :3] * a).astype(np.uint8), straight[:, :, 3]])
        self.rng = random.Random(seed)
        self._landmarks(); self._prep_mouth()

    # ---------- geometry ----------
    def _landmarks(self):
        import mediapipe as mp
        fm = mp.solutions.face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True)
        res = fm.process(self.straight[:, :, :3]); fm.close()
        if not res.multi_face_landmarks: raise RuntimeError("anchor image me chehra detect nahi hua")
        self.L = np.array([(p.x * self.w, p.y * self.h) for p in res.multi_face_landmarks[0].landmark], np.float32)

    def _roi(self, x0, y0, x1, y1):
        x0, y0 = max(int(x0), 0), max(int(y0), 0); x1, y1 = min(int(x1), self.w), min(int(y1), self.h)
        Y, X = np.mgrid[y0:y1, x0:x1].astype(np.float32); return (x0, y0, x1, y1), X, Y

    def _mouth_field(self, X, Y):
        U = (X - self.c[0]) * self.u[0] + (Y - self.c[1]) * self.u[1]
        V = (X - self.c[0]) * self.n[0] + (Y - self.c[1]) * self.n[1]
        s = 0.6 + 0.35 * self.mw * _ss(np.abs(U), 0.4 * self.mw, 0.85 * self.mw)
        Vs = V - np.interp(U, self.seam_u, self.seam_v)           # lip-seam curve se doori (smile curve follow)
        wv = _ss(Vs, -s, s); wf = 1 - _ss(V, self.cv * 0.75, self.cv * 1.35)
        wu = np.exp(-(np.abs(U) / (0.62 * self.mw)) ** 2.5)
        return wv * wf * wu, U, V

    def _prep_mouth(self):
        L = self.L; cL, cR = L[61], L[291]; ax = cR - cL
        self.mw = float(np.linalg.norm(ax)); self.u = ax / self.mw; self.n = np.array([-self.u[1], self.u[0]], np.float32)
        self.c = (L[13] + L[14]) / 2; self.cv = float((L[152] - self.c) @ self.n)
        up, lo = L[UP_IN], L[LO_IN]
        uu, uv = (up - self.c) @ self.u, (up - self.c) @ self.n
        lu, lv = (lo - self.c) @ self.u, (lo - self.c) @ self.n; ol = np.argsort(lu)
        sv = (uv + np.interp(uu, lu[ol], lv[ol])) / 2; os_ = np.argsort(uu)
        self.seam_u, self.seam_v = uu[os_], sv[os_]
        self.roi, self.X, self.Y = self._roi(self.c[0] - 1.7 * self.mw, self.c[1] - 1.0 * self.mw,
                                             self.c[0] + 1.7 * self.mw, L[152][1] + 0.7 * self.mw)
        self.M, self.U, self.V = self._mouth_field(self.X, self.Y)
        P = L[UP_IN]; self.up_pts = P
        pu = (P - self.c) @ self.u; pv = (P - self.c) @ self.n; o = np.argsort(pu); self.up_u, self.up_v = pu[o], pv[o]
        self.dmax = 0.24 * self.mw

    # ---------- per-frame ----------
    def frame(self, t, open_, speak=0.0):
        """Source-res (premultiplied) RGBA frame: mouth open_ (0..1). Body motion camera() me."""
        img = self.rgba.copy()
        # mouth
        if open_ > 0.02:
            x0, y0, x1, y1 = self.roi; d = open_ * self.dmax; src = img[y0:y1, x0:x1].copy()
            mx = (self.X - d * self.M * self.n[0]).astype(np.float32) - x0
            my = (self.Y - d * self.M * self.n[1]).astype(np.float32) - y0
            warped = cv2.remap(src, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            # inside-of-mouth polygon
            lo = self.L[LO_IN].copy(); Mlo, _, _ = self._mouth_field(lo[:, 0], lo[:, 1])
            lo = lo + (d * Mlo)[:, None] * self.n[None, :]
            poly = np.vstack([self.up_pts, lo[::-1][1:-1]]) - [x0, y0]
            m = np.zeros(warped.shape[:2], np.float32); cv2.fillPoly(m, [np.round(poly * 16).astype(np.int32)], 1.0, cv2.LINE_AA, 4)
            m = cv2.GaussianBlur(m, (0, 0), 0.9)
            lou, lov = (lo - self.c) @ self.u, (lo - self.c) @ self.n; ol = np.argsort(lou)
            vup = np.interp(self.U, self.up_u, self.up_v); vlo = np.interp(self.U, lou[ol], lov[ol])
            gap = np.maximum(vlo - vup, 1e-3); depth = np.clip((self.V - vup) / gap, 0, 1)
            col = np.array([62, 22, 30], np.float32) * (1 - 0.35 * np.sin(depth * math.pi))[..., None] + 0   # darker centre
            teeth = ((self.V - vup) < np.minimum(0.30 * gap, 0.065 * self.mw)).astype(np.float32); teeth = cv2.GaussianBlur(teeth, (0, 0), 1.0)
            tcol = np.array([226, 214, 204], np.float32)
            inside = col * (1 - teeth[..., None] * 0.8) + tcol * teeth[..., None] * 0.8
            out = warped[:, :, :3].astype(np.float32) * (1 - m[..., None]) + inside * m[..., None]
            warped[:, :, :3] = np.clip(out, 0, 255).astype(np.uint8); img[y0:y1, x0:x1] = warped
        return img

    def camera(self, img, t, speak, out_w, out_h=None, pivot=None):
        """Halka saans/sway/nod: whole cutout ko scale+rotate. Returns RGBA at out size."""
        s = out_w / self.w; oh = int(round(self.h * s)) if out_h is None else out_h
        ang = 0.55 * math.sin(2 * math.pi * 0.19 * t + 0.6) + 0.35 * math.sin(2 * math.pi * 0.43 * t)
        sc = 1 + 0.004 * math.sin(2 * math.pi * 0.27 * t) + 0.004 * speak
        ty = 2.5 * speak + 1.5 * math.sin(2 * math.pi * 0.27 * t)
        px, py = (self.w * 0.5, self.h * 0.95) if pivot is None else pivot
        Mx = cv2.getRotationMatrix2D((px, py), ang, sc); Mx[1, 2] += ty
        Mx = Mx * s; Mx[:, 2] = (Mx[:, 2])  # scale to output
        return cv2.warpAffine(img, Mx, (out_w, oh), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

def unpremultiply(rgba):
    """premultiplied RGBA -> (straight RGB uint8, alpha float 0..1) moviepy ke liye."""
    a = rgba[:, :, 3:4].astype(np.float32) / 255.0
    rgb = np.clip(rgba[:, :, :3].astype(np.float32) / np.maximum(a, 1e-3), 0, 255).astype(np.uint8)
    return rgb, a[:, :, 0]

def with_shadow(cam, sa):
    """cam: premultiplied RGBA (camera() output), sa: soft shadow alpha -> (straight RGB, alpha 0..1)."""
    a = cam[:, :, 3].astype(np.float32) / 255.0
    a2 = a + sa * (1 - a)
    rgb = np.clip(cam[:, :, :3].astype(np.float32) / np.maximum(a2, 1e-3)[..., None], 0, 255).astype(np.uint8)
    return rgb, a2

def shadow_alpha(cam, strength=0.5):
    a = cam[:, :, 3].astype(np.float32) / 255.0
    k = max(3, int(a.shape[1] * 0.04) | 1)
    sh = cv2.GaussianBlur(a, (k * 2 + 1, k * 2 + 1), k / 2.2)
    k2 = int(a.shape[1] * 0.018); out = np.zeros_like(sh); out[k2:] = sh[:-k2]      # shift (wrap nahi)
    return out * strength
