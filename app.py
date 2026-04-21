from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

from db import get_conn, init_db

# ---------------- APP ----------------
app = FastAPI()

# ✅ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- INIT DB ----------------
init_db()

# ---------------- ROOT ----------------
@app.get("/")
def root():
    return {"message": "Backend is running 🚀"}



import math

VREF = 3.3
RL = 10.0  # kOhm

# ⚠️ TODO: calibrate later (these are placeholder values)
R0_MQ2 = 10.0
R0_MQ4 = 1.1
R0_MQ135 = 10.0

def calculate_ppm(adc, R0, a, b):
    if adc <= 0:
        return 0

    Vout = (adc / 4095.0) * VREF
    if Vout <= 0.01:
        return 0

    Rs = RL * ((VREF - Vout) / Vout)
    ratio = Rs / R0

    # 🚨 CRITICAL FIXES
    if ratio <= 0:
        return 0

    # Prevent mathematical explosion
    ratio = max(ratio, 0.2)   # 👈 THIS SAVES YOUR LIFE

    ppm = a * math.pow(ratio, b)

    # 🚨 clamp insane values
    ppm = min(ppm, 1000000)

    return round(ppm, 2)
# ---------------- ALERT LOGIC ----------------
def get_status(mq135, mq2, mq4, temp, hum, prev=None):

    alerts = []

    curr = {"temp": temp, "hum": hum}

    # 🔥 Heat
    if prev and detect_heat_source(prev, curr):
        alerts.append("🔥 Heat Source Detected")

    # ---------------- LPG ----------------
    if mq2 > 5000:
        alerts.append("💣 LPG Explosion Risk")
    elif mq2 > 2000:
        alerts.append("🚨 High LPG Leak")
    elif mq2 > 800:
        alerts.append("⚠️ LPG Leak")

    # ---------------- Methane ----------------
    if mq4 > 1000:
        alerts.append("💣 Critical Methane")
    elif mq4 > 200:
        alerts.append("🚨 High Methane")
    elif mq4 > 100:
        alerts.append("⚠️ Methane Rising, food spoiling")

    # ---------------- Ammonia ----------------
    if mq135 > 300:
        alerts.append("☠️ Lethal Ammonia")
    elif mq135 > 100:
        alerts.append("🚨 High Ammonia")
    elif mq135 > 50:
        alerts.append("⚠️ Ammonia Detected")

    # ---------------- FINAL OUTPUT ----------------
    if not alerts:
        return "✅ Air Quality Normal"

    return " | ".join(alerts)

def detect_heat_source(prev, curr):
    if not prev:
        return False

    temp_rise = curr["temp"] - prev["temp"]
    hum_drop  = prev["hum"] - curr["hum"]

    # 🔥 threshold (tune if needed)
    if temp_rise > 2 and hum_drop > 3:
        return True

    return False

# ---------------- POST SENSOR DATA ----------------
@app.post("/sensor")
async def receive_data(req: Request):
    try:
        data = await req.json()

        mq135 = data.get("mq135", 0)
        mq2   = data.get("mq2", 0)
        mq4   = data.get("mq4", 0)
        temp  = data.get("temp", 0)
        hum   = data.get("hum", 0)

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO sensor_data (mq135, mq2, mq4, temp, hum)
        VALUES (%s, %s, %s, %s, %s)
        """, (mq135, mq2, mq4, temp, hum))

        conn.commit()
        conn.close()

        print("STORED:", mq135, mq2, mq4)

        return {"status": "stored"}

    except Exception as e:
        return {"error": str(e)}

# ---------------- GET HISTORY ----------------
@app.get("/history")
def get_history():
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
        SELECT timestamp, mq135, mq2, mq4, temp, hum
        FROM sensor_data
        ORDER BY id DESC LIMIT 50
        """)

        rows = cur.fetchall()
        conn.close()

        return [
             (lambda r: {
                          "time": str(r[0]),

                         "mq135": (mq135_ppm := calculate_ppm(r[1], R0_MQ135, 116.60, -2.769)),
                         "mq2":   (mq2_ppm   := calculate_ppm(r[2], R0_MQ2,   651.39, -2.047)),
                         "mq4":   (mq4_ppm   := calculate_ppm(r[3], R0_MQ4,  1012.7,  -2.786)),

                         "temp": r[4],
                          "hum": r[5],

                          "status": get_status(mq135_ppm, mq2_ppm, mq4_ppm, r[4], r[5])
                         })(r)
         for r in rows[::-1]
            ]

    except Exception as e:
        return {"error": str(e)}

# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)