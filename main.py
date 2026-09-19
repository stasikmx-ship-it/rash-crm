import asyncio
import sqlite3
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

BOT_TOKEN = "8823607240:AAHTcvZq15faIsBbYxvF88JaiV5WUFbSjKE
"
MY_TELEGRAM_ID = 387900317

app = FastAPI()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def init_db():
    conn = sqlite3.connect("crm.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            address TEXT,
            last_visit_date TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shipments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            date TEXT,
            bottles INT DEFAULT 0,
            cartons INT DEFAULT 0,
            total_amount REAL,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/clients")
async def get_clients():
    conn = sqlite3.connect("crm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, phone, address, last_visit_date FROM clients")
    rows = cursor.fetchall()
    
    clients = []
    today = datetime.now()

    for r in rows:
        client_id, name, phone, address, last_visit = r
        cursor.execute("SELECT SUM(bottles), SUM(cartons) FROM shipments WHERE client_id = ?", (client_id,))
        sums = cursor.fetchone()
        total_bottles = sums[0] if sums[0] else 0
        total_cartons = sums[1] if sums[1] else 0

        days_passed = None
        if last_visit:
            visit_date = datetime.strptime(last_visit, "%Y-%m-%d")
            days_passed = (today - visit_date).days

        clients.append({
            "id": client_id,
            "name": name,
            "phone": phone,
            "address": address,
            "last_visit_date": last_visit,
            "days_passed": days_passed,
            "total_bottles": total_bottles,
            "total_cartons": total_cartons
        })
    
    conn.close()
    return clients

@app.post("/api/clients")
async def add_client(req: Request):
    data = await req.json()
    conn = sqlite3.connect("crm.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO clients (name, phone, address) VALUES (?, ?, ?)", 
                   (data['name'], data.get('phone', ''), data.get('address', '')))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.post("/api/shipment")
async def add_shipment(req: Request):
    data = await req.json()
    client_id = data['client_id']
    bottles = data['bottles']
    cartons = data['cartons']
    total_amount = (bottles * 210) + (cartons * 145)
    today_str = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect("crm.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO shipments (client_id, date, bottles, cartons, total_amount) VALUES (?, ?, ?, ?, ?)",
                   (client_id, today_str, bottles, cartons, total_amount))
    cursor.execute("UPDATE clients SET last_visit_date = ? WHERE id = ?", (today_str, client_id))
    conn.commit()
    conn.close()
    return {"status": "ok"}

async def check_reminders():
    while True:
        try:
            conn = sqlite3.connect("crm.db")
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, last_visit_date FROM clients")
            clients = cursor.fetchall()
            today = datetime.now()
            alerts = []

            for client_id, name, last_visit in clients:
                if last_visit:
                    visit_date = datetime.strptime(last_visit, "%Y-%m-%d")
                    days = (today - visit_date).days
                    if days >= 30:
                        alerts.append(f"🔴 **{name}** — прошло {days} дней с поставки!")
            conn.close()

            if alerts:
                text = "⏰ **Напоминание о заезде к клиентам:**\n\n" + "\n".join(alerts)
                await bot.send_message(chat_id=MY_TELEGRAM_ID, text=text, parse_mode="Markdown")
        except Exception as e:
            print(f"Ошибка проверки: {e}")

        await asyncio.sleep(86400)

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("CRM готова к работе! Нажми на кнопку в левом нижнем углу меню.")

async def start_all():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    
    asyncio.create_task(check_reminders())
    asyncio.create_task(dp.start_polling(bot))
    await server.serve()

if __name__ == "__main__":
    asyncio.run(start_all())
