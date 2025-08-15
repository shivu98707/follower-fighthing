import streamlit as st
import numpy as np
import time, os, random, pathlib
from PIL import Image, ImageDraw

# ------------ Page & constants ------------
st.set_page_config(page_title="Follower Fighters", layout="wide")
W, H = 1080, 1920   # vertical canvas
FPS = 30

# ------------ Sidebar controls ------------
st.sidebar.header("Follower Fighters")
N = st.sidebar.slider("Fighters on screen", 8, 60, 12)
TITLE = st.sidebar.text_input("Title", "Every follower is a fighter")
SUB = st.sidebar.text_input("Sub", "Day 1: 9 followers")

# Sliders return numbers; we still cast before use for safety
speed = st.sidebar.slider("Average speed", 20, 160, 60)
hit_rate = st.sidebar.slider("Hit chance per step (%)", 1, 25, 10)
damage_min, damage_max = st.sidebar.slider("Damage range", 5, 30, (8, 16))

# ------------ Load avatars from images/ next to app.py ------------
APP_DIR = pathlib.Path(_file_).parent

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

def spawn(n: int):
    F = []
    n = int(min(n, len(avatars)))
    for i in range(n):
        x = random.randint(140, W - 140)
        y = random.randint(320, H - 220)
        ang = random.uniform(0, 2 * np.pi)
        # numeric-safe velocity
        spd = float(speed)
        v = spd + float(np.random.uniform(-0.3 * spd, 0.3 * spd))
        vx = float(np.cos(ang) * v)
        vy = float(np.sin(ang) * v)
        F.append({
            "x": float(x), "y": float(y),
            "vx": vx, "vy": vy,
            "hp": 100.0, "alive": True,
            "img": avatars[i % len(avatars)],
            "cool": 0.0
        })
    return F

def reset():
    st.session_state.fighters = spawn(N)

# ------------ Controls ------------
c1, c2, c3 = st.columns([1, 1, 1])
if c1.button("Start / Resume"):
    st.session_state.running = True
if c2.button("Pause"):
    st.session_state.running = False
if c3.button("Reset"):
    reset()
if len(st.session_state.fighters) == 0:
    reset()

viewport = st.empty()

# ------------ Simulation ------------
def step(dt: float):
    F = st.session_state.fighters
    for i, a in enumerate(F):
        if not a["alive"]:
            continue

        # Wander jitter
        a["vx"] += np.random.uniform(-20, 20) * dt
        a["vy"] += np.random.uniform(-20, 20) * dt

        # Clamp speed (numeric-safe)
        try:
            s = float((a["vx"]*2 + a["vy"]*2) ** 0.5)
        except Exception:
            s = 0.0
        try:
            maxv = float(max(20.0, float(speed)))
        except Exception:
            maxv = 60.0

        if s > maxv and maxv > 0:
            a["vx"] *= maxv / s
            a["vy"] *= maxv / s

        # Integrate position
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

        # Try an attack
        if a["cool"] <= 0 and random.random() < (hit_rate / 100.0):
            j = -1
            best = 1e18
            for k, b in enumerate(F):
                if k == i or not b["alive"]:
                    continue
                d2 = (b["x"] - a["x"])*2 + (b["y"] - a["y"])*2
                if d2 < best:
                    best = d2
                    j = k
            if j >= 0 and best < (200**2):
                dmg = random.uniform(float(damage_min), float(damage_max))
                F[j]["hp"] -= dmg
                a["cool"] = 0.4
                if F[j]["hp"] <= 0:
                    F[j]["alive"] = False

# ------------ Render ------------
def render(title: str, sub: str):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # Titles (default font)
    draw.text((W // 2, 120), title, fill=(255, 255, 255, 255), anchor="mm")
    draw.text((W // 2, H - 140), sub, fill=(255, 255, 255, 255), anchor="mm")

    for f in st.session_state.fighters:
        if not f["alive"]:
            continue
        x, y = int(f["x"]), int(f["y"])
        img.paste(f["img"], (x - 46, y - 46), f["img"])

        # HP bar
        w, h = 40, 6
        draw.rounded_rectangle(
            (x - w, y - 58, x + w, y - 58 + h),
            radius=3, fill=(170, 35, 35, 255)
        )
        pct = max(0.0, min(1.0, f["hp"] / 100.0))
        gw = int((2 * w) * pct)
        color = (40, 200, 90, 255) if pct >= 0.4 else (230, 120, 60, 255)
        draw.rounded_rectangle(
            (x - w, y - 58, x - w + gw, y - 58 + h),
            radius=3, fill=color
        )
    return img

# ------------ Main loop ------------
if st.session_state.running:
    last = time.time()
    for _ in range(3000):  # ~100s on Cloud
        now = time.time()
        dt = min(1/20, now - last)  # stable stepping
        last = now
        step(dt)
        frame = render(TITLE, SUB)
        viewport.image(frame, use_container_width=True)
        time.sleep(1 / FPS)
else:
    viewport.image(render(TITLE, SUB), use_container_width=True)
