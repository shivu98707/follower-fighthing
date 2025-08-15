import streamlit as st
import numpy as np
import time, os, random, pathlib
from PIL import Image, ImageDraw

# ------------ Page & constants ------------
st.set_page_config(page_title="Follower Fighters", layout="wide")
W, H = 1080, 1920   # vertical canvas
RENDER_FPS = 30     # target render FPS
SIM_FPS = 60        # physics tick rate (fixed timestep)
MAX_RUN_SECONDS = 120

# ------------ App dir (robust) ------------
try:
    APP_DIR = pathlib.Path(__file__).parent
except NameError:
    APP_DIR = pathlib.Path(os.getcwd())

# ------------ Sidebar controls ------------
st.sidebar.header("Follower Fighters")
N = st.sidebar.slider("Fighters on screen", 8, 40, 14)
TITLE = st.sidebar.text_input("Title", "Every follower is a fighter")
SUB = st.sidebar.text_input("Sub", "Day 1: 14 followers")

# Stronger defaults for visible motion and hits
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
            # circular mask
            m = Image.new("L", im.size, 0)
            d = ImageDraw.Draw(m)
            d.ellipse((0, 0, im.size[0], im.size[1]), fill=255)
            im.putalpha(m)
            imgs.append(im)
        except Exception:
            pass
    return imgs

avatars = load_avatars(folder=str(APP_DIR / "images"))
if len(avatars) == 0:
    st.error("No images found in ./images. Add .png/.jpg avatars to the images/ folder (next to app.py) and rerun.")
    st.stop()

# ------------ Session state (robust init) ------------
if "fighters" not in st.session_state:
    st.session_state.fighters = []
if "running" not in st.session_state:
    st.session_state.running = False
if "impacts" not in st.session_state:
    st.session_state.impacts = []

def spawn(n: int):
    F = []
    n = int(min(n, len(avatars)))
    for i in range(n):
        x = random.randint(140, W - 140)
        y = random.randint(320, H - 220)
        ang = random.uniform(0, 2 * np.pi)
        spd = float(speed)
        v = spd + float(np.random.uniform(-0.25 * spd, 0.25 * spd))
        vx = float(np.cos(ang) * v)
        vy = float(np.sin(ang) * v)
        F.append({
            "x": float(x), "y": float(y),
            "vx": vx, "vy": vy,
            "hp": 100.0, "alive": True,
            "img": avatars[i % len(avatars)],
            "cool": 0.0
        })
    st.session_state.impacts = []
    return F

def reset():
    st.session_state.fighters = spawn(N)
    st.session_state.impacts = []

# ------------ Controls ------------
c1, c2, c3 = st.columns(3)
if c1.button("▶ Start / Resume", use_container_width=True):
    st.session_state.running = True
if c2.button("⏸ Pause", use_container_width=True):
    st.session_state.running = False
if c3.button("🔄 Reset", use_container_width=True):
    reset()

if len(st.session_state.fighters) == 0:
    reset()

# ------------ Placeholders ------------
viewport = st.empty()
winner_placeholder = st.empty()

# ------------ Simulation ------------
def sim_step(dt: float):
    F = st.session_state.fighters
    impacts = st.session_state.impacts

    alive_indices = [i for i, a in enumerate(F) if a["alive"]]
    if len(alive_indices) <= 1:
        return

    for i in alive_indices:
        a = F[i]

        # Wander jitter
        a["vx"] += np.random.uniform(-25, 25) * dt
        a["vy"] += np.random.uniform(-25, 25) * dt

        # Clamp speed
        try:
            s = float((a["vx"]**2 + a["vy"]**2) ** 0.5)
        except Exception:
            s = 0.0
        try:
            maxv = float(max(30.0, float(speed)))
        except Exception:
            maxv = 100.0
        if s > maxv and maxv > 0:
            a["vx"] *= maxv / s
            a["vy"] *= maxv / s

        # Move
        a["x"] += a["vx"] * dt
        a["y"] += a["vy"] * dt

        # Walls
        if a["x"] < 80 or a["x"] > W - 80:
            a["vx"] *= -1
            a["x"] = min(max(a["x"], 80), W - 80)
        if a["y"] < 260 or a["y"] > H - 140:
            a["vy"] *= -1
            a["y"] = min(max(a["y"], 260), H - 140)

        # Cooldown
        a["cool"] = max(0.0, a["cool"] - dt)

        # Attack
        if a["cool"] <= 0 and random.random() < (hit_rate / 100.0):
            j = -1
            best = 1e18
            for k in alive_indices:
                if k == i:
                    continue
                b = F[k]
                d2 = (b["x"] - a["x"])**2 + (b["y"] - a["y"])**2
                if d2 < best:
                    best = d2
                    j = k
            if j >= 0 and best < (220**2):
                dmg = random.uniform(float(damage_min), float(damage_max))
                F[j]["hp"] -= dmg
                a["cool"] = 0.35
                # small knockback for visibility
                dx = F[j]["x"] - a["x"]
                dy = F[j]["y"] - a["y"]
                dist = (dx*dx + dy*dy) ** 0.5 + 1e-6
                F[j]["x"] += (dx/dist) * 8
                F[j]["y"] += (dy/dist) * 8
                impacts.append({"x": F[j]["x"], "y": F[j]["y"], "age": 0.0})
                if F[j]["hp"] <= 0:
                    F[j]["alive"] = False

    # Age out impacts (250 ms)
    for imp in impacts:
        imp["age"] += dt
    st.session_state.impacts = [imp for imp in impacts if imp["age"] < 0.25]

# ------------ Render ------------
def render(title: str, sub: str):
    F = st.session_state.fighters
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # Titles
    draw.text((W // 2, 120), title, fill=(255, 255, 255, 255), anchor="mm")
    draw.text((W // 2, H - 140), sub, fill=(255, 255, 255, 255), anchor="mm")

    alive_indices = [i for i, a in enumerate(F) if a["alive"]]

    # Fighters
    for i in alive_indices:
        f = F[i]
        x, y = int(f["x"]), int(f["y"])
        img.paste(f["img"], (x - 46, y - 46), f["img"])
        # HP bar
        w, h = 48, 7
        draw.rounded_rectangle((x - w, y - 60, x + w, y - 60 + h),
                               radius=3, fill=(170, 35, 35, 255))
        pct = max(0.0, min(1.0, f["hp"] / 100.0))
        gw = int((2 * w) * pct)
        color = (40, 200, 90, 255) if pct >= 0.4 else (230, 90, 60, 255)
        draw.rounded_rectangle((x - w, y - 60, x - w + gw, y - 60 + h),
                               radius=3, fill=color)

    # Impact flashes
    for imp in st.session_state.impacts:
        a = imp["age"] / 0.25
        r = int(26 + 20 * a)
        alpha = int(255 * (1 - a))
        x, y = int(imp["x"]), int(imp["y"])
        draw.ellipse((x - r, y - r, x + r, y + r), outline=(255, 255, 255, alpha), width=3)

    # Winner
    if len(alive_indices) == 1:
        draw.text((W // 2, H // 2), "Winner!", fill=(255, 255, 255, 255), anchor="mm")

    return img

# ------------ Smooth animation loop ------------
def run_loop():
    """Run a smooth fixed-timestep simulation with a capped render FPS."""
    fixed_dt = 1.0 / SIM_FPS
    render_dt = 1.0 / RENDER_FPS
    next_render_time = 0.0

    start = time.perf_counter()
    prev = start
    accumulator = 0.0

    while st.session_state.running:
        now = time.perf_counter()
        frame_dt = now - prev
        prev = now

        # avoid spiral of death: clamp long pauses
        if frame_dt > 0.25:
            frame_dt = 0.25

        accumulator += frame_dt

        # fixed-timestep physics
        while accumulator >= fixed_dt:
            sim_step(fixed_dt)
            accumulator -= fixed_dt

        # render at most RENDER_FPS
        if (now - start) >= next_render_time:
            frame = render(TITLE, SUB)
            viewport.image(frame, use_container_width=True)
            next_render_time += render_dt

        # end conditions
        alive = sum(1 for f in st.session_state.fighters if f["alive"])
        if alive <= 1:
            # show final frame then stop
            frame = render(TITLE, SUB)
            viewport.image(frame, use_container_width=True)
            st.session_state.running = False
            break

        # stop after MAX_RUN_SECONDS to avoid runaway CPU on cloud
        if (now - start) >= MAX_RUN_SECONDS:
            st.session_state.running = False
            break

        # tiny sleep to yield CPU (keeps things smooth on Streamlit Cloud)
        time.sleep(0.001)

# ------------ Run once per page load ------------
if st.session_state.running:
    run_loop()
else:
    # static preview when paused
    viewport.image(render(TITLE, SUB), use_container_width=True)
