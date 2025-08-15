import streamlit as st
import numpy as np
import time, os, random, pathlib
from PIL import Image, ImageDraw

# ------------ Page & constants ------------
st.set_page_config(page_title="Follower Fighters", layout="wide")
W, H = 1080, 1920   # vertical canvas
FPS = 30

APP_DIR = pathlib.Path(__file__).parent

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

# ------------ State ------------
if "fighters" not in st.session_state:
    st.session_state.fighters = []
    st.session_state.running = False
    st.session_state.impacts = []  # list of transient hit effects (x,y,age)

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

# ------------ Controls ------------
c1, c2, c3, c4 = st.columns([1,1,1,1])
if c1.button("Start / Resume"):
    st.session_state.running = True
if c2.button("Pause"):
    st.session_state.running = False
if c3.button("Reset"):
    reset()
if c4.button("Run 20s"):
    # run a guaranteed 20s loop once
    st.session_state.running = True
    last = time.time()
    end_time = last + 20.0
    while time.time() < end_time and st.session_state.running:
        now = time.time()
        dt = min(1/20, now - last)
        last = now
        step(dt=True)  # we’ll define a wrapper below
    st.session_state.running = False

if len(st.session_state.fighters) == 0:
    reset()

viewport = st.empty()
winner_placeholder = st.empty()

# ------------ Simulation ------------
def sim_step(dt: float):
    F = st.session_state.fighters
    impacts = st.session_state.impacts

    alive_indices = [i for i,a in enumerate(F) if a["alive"]]
    if len(alive_indices) <= 1:
        return  # winner logic handled in render

    for i in alive_indices:
        a = F[i]

        # Wander jitter
        a["vx"] += np.random.uniform(-25, 25) * dt
        a["vy"] += np.random.uniform(-25, 25) * dt

        # Clamp speed
        try:
            s = float((a["vx"]*2 + a["vy"]*2) ** 0.5)
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
            # nearest target
            j = -1
            best = 1e18
            for k in alive_indices:
                if k == i:
                    continue
                b = F[k]
                d2 = (b["x"] - a["x"])*2 + (b["y"] - a["y"])*2
                if d2 < best:
                    best = d2
                    j = k
            if j >= 0 and best < (220**2):
                dmg = random.uniform(float(damage_min), float(damage_max))
                F[j]["hp"] -= dmg
                a["cool"] = 0.35
                # knock a bit for visibility
                dx = F[j]["x"] - a["x"]
                dy = F[j]["y"] - a["y"]
                dist = (dx*dx + dy*dy) ** 0.5 + 1e-6
                F[j]["x"] += (dx/dist) * 8
                F[j]["y"] += (dy/dist) * 8
                # impact flash
                impacts.append({"x": F[j]["x"], "y": F[j]["y"], "age": 0.0})
                if F[j]["hp"] <= 0:
                    F[j]["alive"] = False

    # age out impacts
    for imp in impacts:
        imp["age"] += dt
    st.session_state.impacts = [imp for imp in impacts if imp["age"] < 0.25]  # 250ms flash

def render(title: str, sub: str):
    F = st.session_state.fighters
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # Titles
    draw.text((W // 2, 120), title, fill=(255, 255, 255, 255), anchor="mm")
    draw.text((W // 2, H - 140), sub, fill=(255, 255, 255, 255), anchor="mm")

    alive_indices = [i for i,a in enumerate(F) if a["alive"]]

    # Fighters
    for i in alive_indices:
        f = F[i]
        x, y = int(f["x"]), int(f["y"])
        img.paste(f["img"], (x - 46, y - 46), f["img"])

        # HP bar (thicker and clearer)
        w, h = 48, 7
        draw.rounded_rectangle((x - w, y - 60, x + w, y - 60 + h),
                               radius=3, fill=(170, 35, 35, 255))
        pct = max(0.0, min(1.0, f["hp"] / 100.0))
        gw = int((2 * w) * pct)
        color = (40, 200, 90, 255) if pct >= 0.4 else (230, 90, 60, 255)
        draw.rounded_rectangle((x - w, y - 60, x - w + gw, y - 60 + h),
                               radius=3, fill=color)

    # Impact flashes (white ring)
    for imp in st.session_state.impacts:
        a = imp["age"] / 0.25  # 0..1
        r = int(26 + 20 * a)
        alpha = int(255 * (1 - a))
        x, y = int(imp["x"]), int(imp["y"])
        draw.ellipse((x - r, y - r, x + r, y + r), outline=(255,255,255,alpha), width=3)

    # Winner banner
    if len(alive_indices) == 1:
        idx = alive_indices[0]
        draw.text((W // 2, H // 2), "Winner!", fill=(255,255,255,255), anchor="mm")
        # also show small name-like placeholder under winner bar
        # (we don't have usernames; this is purely visual)
    return img

def step(dt=True):
    # Single iteration: step + render + display
    now = time.time()
    dt_val = 1/30 if dt is True else float(dt)
    sim_step(dt_val)
    frame = render(TITLE, SUB)
    viewport.image(frame, use_container_width=True)
    time.sleep(1 / FPS)

# ------------ Main loop ------------
if st.session_state.running:
    # Reliable while loop for smooth animation
    last = time.time()
    # Let it run until user pauses or ~120s
    end_time = last + 120
    while time.time() < end_time and st.session_state.running:
        now = time.time()
        dt = min(1/20, now - last)
        last = now
        sim_step(dt)
        frame = render(TITLE, SUB)
        viewport.image(frame, use_container_width=True)
        time.sleep(1 / FPS)
else:
    viewport.image(render(TITLE, SUB), use_container_width=True)

