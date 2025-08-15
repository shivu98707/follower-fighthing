import streamlit as st
import numpy as np
import time, os, random, pathlib
from PIL import Image, ImageDraw, ImageEnhance
import imageio

# ------------ Page & constants ------------
st.set_page_config(page_title="Follower Fighters", layout="wide")
W, H = 1080, 1920
RENDER_FPS = 30
SIM_FPS = 60
MAX_RUN_SECONDS = 120
FADE_SPEED = 0.8  # opacity fade per second

# ------------ App dir ------------
try:
    APP_DIR = pathlib.Path(__file__).parent
except NameError:
    APP_DIR = pathlib.Path(os.getcwd())

# ------------ Sidebar controls ------------
st.sidebar.header("Follower Fighters")
N = st.sidebar.slider("Fighters on screen", 8, 40, 14)
TITLE = st.sidebar.text_input("Title", "Every follower is a fighter")
SUB = st.sidebar.text_input("Sub", "Day 1: 14 followers")
speed = st.sidebar.slider("Average speed", 40, 160, 110)
hit_rate = st.sidebar.slider("Hit chance per step (%)", 5, 35, 22)
damage_min, damage_max = st.sidebar.slider("Damage range", 5, 35, (10, 20))

# ------------ Load avatars ------------
@st.cache_resource
def load_avatars(folder: str):
    p = pathlib.Path(folder)
    if not p.exists():
        return []
    files = [f for f in p.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg")]
    imgs = []
    for f in files[:120]:
        try:
            im = Image.open(f).convert("RGBA").resize((92, 92))
            m = Image.new("L", im.size, 0)
            d = ImageDraw.Draw(m)
            d.ellipse((0, 0, im.size[0], im.size[1]), fill=255)
            im.putalpha(m)
            imgs.append(im)
        except Exception:
            pass
    return imgs

avatars = load_avatars(str(APP_DIR / "images"))
if not avatars:
    st.error("No images found in ./images.")
    st.stop()

# ------------ Session state ------------
for key, default in {
    "fighters": [],
    "running": False,
    "impacts": [],
    "frames": []  # store frames for export
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

def spawn(n):
    F = []
    n = int(min(n, len(avatars)))
    for i in range(n):
        x = random.randint(140, W - 140)
        y = random.randint(320, H - 220)
        ang = random.uniform(0, 2 * np.pi)
        v = float(speed) + np.random.uniform(-0.25 * speed, 0.25 * speed)
        vx, vy = np.cos(ang) * v, np.sin(ang) * v
        F.append({
            "x": float(x), "y": float(y),
            "vx": vx, "vy": vy,
            "hp": 100.0, "alive": True,
            "opacity": 1.0,
            "img": avatars[i % len(avatars)],
            "cool": 0.0
        })
    st.session_state.impacts.clear()
    return F

def reset():
    st.session_state.fighters = spawn(N)
    st.session_state.impacts.clear()
    st.session_state.frames.clear()

# ------------ Controls ------------
c1, c2, c3, c4 = st.columns(4)
if c1.button("▶ Start / Resume", use_container_width=True):
    st.session_state.running = True
if c2.button("⏸ Pause", use_container_width=True):
    st.session_state.running = False
if c3.button("🔄 Reset", use_container_width=True):
    reset()
if c4.button("💾 Save GIF", use_container_width=True):
    if st.session_state.frames:
        gif_path = APP_DIR / "battle.gif"
        imageio.mimsave(gif_path, st.session_state.frames, fps=RENDER_FPS)
        st.success(f"Saved GIF to {gif_path}")
    else:
        st.warning("No frames to save.")

if not st.session_state.fighters:
    reset()

viewport = st.empty()

# ------------ Simulation ------------
def sim_step(dt):
    F = st.session_state.fighters
    impacts = st.session_state.impacts
    alive_indices = [i for i, a in enumerate(F) if a["alive"]]
    if len(alive_indices) <= 1:
        return

    for i in range(len(F)):
        a = F[i]

        if a["alive"]:
            a["vx"] += np.random.uniform(-25, 25) * dt
            a["vy"] += np.random.uniform(-25, 25) * dt
            s = max(1e-6, (a["vx"]**2 + a["vy"]**2) ** 0.5)
            maxv = max(30.0, float(speed))
            if s > maxv:
                a["vx"] *= maxv / s
                a["vy"] *= maxv / s

            a["x"] += a["vx"] * dt
            a["y"] += a["vy"] * dt

            if a["x"] < 80 or a["x"] > W - 80:
                a["vx"] *= -1
                a["x"] = min(max(a["x"], 80), W - 80)
            if a["y"] < 260 or a["y"] > H - 140:
                a["vy"] *= -1
                a["y"] = min(max(a["y"], 260), H - 140)

            a["cool"] = max(0.0, a["cool"] - dt)

            if a["cool"] <= 0 and random.random() < (hit_rate / 100.0):
                j = min(alive_indices, key=lambda k: (F[k]["x"] - a["x"])**2 + (F[k]["y"] - a["y"])**2 if k != i else 1e18)
                if j != i:
                    d2 = (F[j]["x"] - a["x"])**2 + (F[j]["y"] - a["y"])**2
                    if d2 < (220**2):
                        dmg = random.uniform(damage_min, damage_max)
                        F[j]["hp"] -= dmg
                        a["cool"] = 0.35
                        dx, dy = F[j]["x"] - a["x"], F[j]["y"] - a["y"]
                        dist = (dx**2 + dy**2) ** 0.5 + 1e-6
                        F[j]["x"] += (dx/dist) * 8
                        F[j]["y"] += (dy/dist) * 8
                        impacts.append({"x": F[j]["x"], "y": F[j]["y"], "age": 0.0})
                        if F[j]["hp"] <= 0:
                            F[j]["alive"] = False
        else:
            a["opacity"] = max(0.0, a["opacity"] - FADE_SPEED * dt)

    for imp in impacts:
        imp["age"] += dt
    st.session_state.impacts = [imp for imp in impacts if imp["age"] < 0.25]

# ------------ Render ------------
def render(title, sub):
    F = st.session_state.fighters
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)
    draw.text((W//2, 120), title, fill=(255, 255, 255, 255), anchor="mm")
    draw.text((W//2, H-140), sub, fill=(255, 255, 255, 255), anchor="mm")

    for f in F:
        if f["opacity"] > 0:
            fighter_img = f["img"].copy()
            alpha_layer = fighter_img.getchannel("A").point(lambda p: int(p * f["opacity"]))
            fighter_img.putalpha(alpha_layer)
            img.paste(fighter_img, (int(f["x"]) - 46, int(f["y"]) - 46), fighter_img)
            if f["alive"]:
                w, h = 48, 7
                draw.rounded_rectangle((f["x"] - w, f["y"] - 60, f["x"] + w, f["y"] - 53),
                                       radius=3, fill=(170, 35, 35, 255))
                pct = max(0.0, min(1.0, f["hp"] / 100.0))
                gw = int((2 * w) * pct)
                color = (40, 200, 90, 255) if pct >= 0.4 else (230, 90, 60, 255)
                draw.rounded_rectangle((f["x"] - w, f["y"] - 60, f["x"] - w + gw, f["y"] - 53),
                                       radius=3, fill=color)

    for imp in st.session_state.impacts:
        a = imp["age"] / 0.25
        r = int(26 + 20 * a)
        alpha = int(255 * (1 - a))
        draw.ellipse((imp["x"] - r, imp["y"] - r, imp["x"] + r, imp["y"] + r),
                     outline=(255, 255, 255, alpha), width=3)

    return img

# ------------ Animation loop ------------
def run_loop():
    fixed_dt = 1.0 / SIM_FPS
    render_dt = 1.0 / RENDER_FPS
    next_render_time = 0.0
    start = time.perf_counter()
    prev = start
    acc = 0.0

    while st.session_state.running:
        now = time.perf_counter()
        frame_dt = now - prev
        prev = now
        if frame_dt > 0.25: frame_dt = 0.25
        acc += frame_dt

        while acc >= fixed_dt:
            sim_step(fixed_dt)
            acc -= fixed_dt

        if (now - start) >= next_render_time:
            frame = render(TITLE, SUB)
            viewport.image(frame, use_container_width=True)
            st.session_state.frames.append(frame.copy())
            next_render_time += render_dt

        alive = sum(1 for f in st.session_state.fighters if f["alive"])
        if alive <= 1 and all(f["opacity"] <= 0.01 for f in st.session_state.fighters):
            st.session_state.running = False
            break
        if (now - start) >= MAX_RUN_SECONDS:
            st.session_state.running = False
            break
        time.sleep(0.001)

# ------------ Run ------------
if st.session_state.running:
    run_loop()
else:
    viewport.image(render(TITLE, SUB), use_container_width=True)

