import streamlit as st
import numpy as np
from PIL import Image, ImageDraw
import time
import os
import imageio

# ----- Config -----
FPS = 30
DT = 1.0 / FPS
FIGHTER_RADIUS = 15
FADE_OUT_FRAMES = 15  # ghost fade duration

# ----- Fighter class -----
class Fighter:
    def __init__(self, x, y, color, name):
        self.x = x
        self.y = y
        self.color = color
        self.name = name
        self.alive = True
        self.fade_frame = 0  # for ghost fade

    def move(self):
        if self.alive:
            self.x += np.random.randint(-3, 4)
            self.y += np.random.randint(-3, 4)

    def hit(self):
        self.alive = False
        self.fade_frame = FADE_OUT_FRAMES

# ----- Drawing -----
def draw_scene(fighters, width=500, height=500):
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    for f in fighters:
        if f.alive or f.fade_frame > 0:
            alpha = 255
            if not f.alive:
                alpha = int(255 * (f.fade_frame / FADE_OUT_FRAMES))
                f.fade_frame -= 1
            color = tuple(int(c * alpha / 255) for c in f.color)
            draw.ellipse(
                (f.x - FIGHTER_RADIUS, f.y - FIGHTER_RADIUS,
                 f.x + FIGHTER_RADIUS, f.y + FIGHTER_RADIUS),
                fill=color
            )
    return img

# ----- Simulation -----
def run_simulation():
    fighters = [
        Fighter(100, 250, (255, 0, 0), "Red"),
        Fighter(400, 250, (0, 0, 255), "Blue")
    ]

    frames = []
    for frame in range(200):
        # Movement
        for f in fighters:
            f.move()

        # Randomly defeat one
        if frame == 60:
            fighters[1].hit()

        # Draw
        img = draw_scene(fighters)
        frames.append(np.array(img))

        # Smooth Streamlit update
        st.image(img)
        time.sleep(DT)

    return frames

# ----- Main -----
st.title("⚔️ Follower Fighting Animation")

if st.button("▶️ Start Fight"):
    frames = run_simulation()

    # Save GIF
    gif_path = "fight_animation.gif"
    imageio.mimsave(gif_path, frames, fps=FPS)

    # If Streamlit Cloud → download button
    if "streamlit" in os.environ.get("SERVER_SOFTWARE", "").lower():
        with open(gif_path, "rb") as f:
            st.download_button(
                label="📥 Download Animation",
                data=f,
                file_name="fight_animation.gif",
                mime="image/gif"
            )
    else:
        st.success(f"✅ GIF saved locally as: {os.path.abspath(gif_path)}")
        st.info("Open the above path to view your GIF.")


