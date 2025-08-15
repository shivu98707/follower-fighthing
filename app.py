import streamlit as st
import numpy as np, time, os, random
from PIL import Image, ImageDraw

# Canvas size: vertical video
W, H = 1080, 1920
FPS = 30

st.set_page_config(page_title="Follower Fighters", layout="wide")

# Sidebar controls
st.sidebar.header("Follower Fighters")
N = st.sidebar.slider("Fighters on screen", 8, 60, 12)
TITLE = st.sidebar.text_input("Title", "Every follower is a fighter")
SUB = st.sidebar.text_input("Sub", "Day 1: 9 followers")
speed = st.sidebar.slider("Average speed", 20, 120, 60)
hit_rate = st.sidebar.slider("Hit chance per step (%)", 1, 25, 10)
damage_min, damage_max = st.sidebar.slider("Damage range", 5, 30, (8, 16))

# Load avatars from images/ directory in repo
@st.cache_resource
def load_avatars(folder="images"):
    files = []
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                files.append(os.path.join(folder, f))
    imgs=[]
    for p in files[:100]:
        try:
            im = Image.open(p).convert("RGBA").resize((92,92))
            # circular mask
            m = Image.new("L", im.size, 0); d = ImageDraw.Draw(m)
            d.ellipse((0,0,im.size[0],im.size[1]), fill=255)
            im.putalpha(m)
            imgs.append(im)
        except:
            pass
    return imgs

avatars = load_avatars()
if len(avatars)==0:
    st.error("No images found in ./images. Add some .png/.jpg avatars to the repo and rerun.")
    st.stop()

# State init
if "fighters" not in st.session_state:
    st.session_state.fighters = []
    st.session_state.running = False

def spawn(n):
    F=[]
    for i in range(n):
        x = random.randint(140, W-140)
        y = random.randint(320, H-220)
        # random velocity
        ang = random.uniform(0, 2*np.pi)
        v = speed + np.random.uniform(-speed*0.3, speed*0.3)
        vx, vy = float(np.cos(ang)*v), float(np.sin(ang)*v)
        F.append({
            "x": float(x), "y": float(y),
            "vx": vx, "vy": vy,
            "hp": 100.0, "alive": True,
            "img": avatars[i % len(avatars)],
            "cool": 0.0 # attack cooldown
        })
    return F

def reset():
    st.session_state.fighters = spawn(min(N, len(avatars)))

# Buttons
c1, c2, c3 = st.columns([1,1,1])
if c1.button("Start / Resume"): st.session_state.running = True
if c2.button("Pause"): st.session_state.running = False
if c3.button("Reset"): reset()
if len(st.session_state.fighters)==0: reset()

viewport = st.empty()

# Simulation functions
def step(dt):
    F = st.session_state.fighters
    # movement and simple combat
    for i,a in enumerate(F):
        if not a["alive"]: continue
        # wander jitter
        a["vx"] += np.random.uniform(-20,20)*dt
        a["vy"] += np.random.uniform(-20,20)*dt
        # clamp speed
        s = (a["vx"]*2 + a["vy"]2)*0.5
        maxv = max(20.0, float(speed))
        if s>maxv:
            a["vx"] *= maxv/s; a["vy"] *= maxv/s
        a["x"] += a["vx"]*dt
        a["y"] += a["vy"]*dt
        # walls
        if a["x"]<80 or a["x"]>W-80: a["vx"]*=-1
        if a["y"]<260 or a["y"]>H-140: a["vy"]*=-1

        # cooldown
        a["cool"] = max(0.0, a["cool"]-dt)

        # attack sometimes
        if a["cool"]<=0 and random.random() < (hit_rate/100.0):
            # nearest alive other
            j = -1; best = 1e18
            for k,b in enumerate(F):
                if k==i or not b["alive"]: continue
                d2 = (b["x"]-a["x"])*2 + (b["y"]-a["y"])*2
                if d2<best: best=d2; j=k
            if j>=0 and best < (200**2):
                dmg = random.uniform(float(damage_min), float(damage_max))
                F[j]["hp"] -= dmg
                a["cool"] = 0.4
                if F[j]["hp"]<=0:
                    F[j]["alive"]=False

def render(title, sub):
    img = Image.new("RGBA", (W,H), (0,0,0,255))
    draw = ImageDraw.Draw(img)
    # Titles (use default font)
    draw.text((W//2, 120), title, fill=(255,255,255,255), anchor="mm")
    draw.text((W//2, H-140), sub, fill=(255,255,255,255), anchor="mm")

    for f in st.session_state.fighters:
        if not f["alive"]: continue
        x, y = int(f["x"]), int(f["y"])
        img.paste(f["img"], (x-46, y-46), f["img"])
        # HP bar
        w, h = 40, 6
        # red background
        draw.rounded_rectangle((x-w, y-58, x+w, y-58+h), radius=3, fill=(170,35,35,255))
        pct = max(0.0, min(1.0, f["hp"]/100.0))
        gw = int((2*w)*pct)
        # green foreground
        color = (40,200,90,255) if pct>=0.4 else (230,100,60,255)
        draw.rounded_rectangle((x-w, y-58, x-w+gw, y-58+h), radius=3, fill=color)
    return img

# Main loop
if st.session_state.running:
    last = time.time()
    # soft cap to prevent infinite loops on cloud
    for _ in range(3000):  # ~100s
        now = time.time()
        dt = min(1/20, now-last)
        last = now
        step(dt)
        frame = render(TITLE, SUB)
        viewport.image(frame, use_container_width=True)
        time.sleep(1/FPS)
else:
    viewport.image(render(TITLE, SUB), use_container_width=True)
