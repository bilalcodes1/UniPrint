import sys
import io

# لإصلاح مشكلة الـ NoneType attribute isatty عند التشغيل بدون Console
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()
from fastapi import FastAPI, Request, Form, File, UploadFile, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import os, shutil, json, socket, qrcode, asyncio, uuid, subprocess, platform, secrets, time
from datetime import datetime
from typing import List
from fastapi import FastAPI, Request, Form, File, UploadFile, WebSocket, WebSocketDisconnect, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI()

templates = Jinja2Templates(directory="templates")

security = HTTPBasic()
SETTINGS_FILE = "db/settings.json"

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        default_settings = {"username": "admin", "password": "12345"}
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_settings, f)
        return default_settings
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return {"username": "admin", "password": "12345"}

def save_settings(settings_data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings_data, f, indent=4)

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    settings = load_settings()
    correct_username = secrets.compare_digest(credentials.username, settings.get("username", "admin"))
    correct_password = secrets.compare_digest(credentials.password, settings.get("password", "12345"))
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

app_state = {"auto_print": False, "selected_printer": ""}
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".ppt", ".pptx", ".xls", ".xlsx", ".dwg", ".txt"}
MAX_FILE_SIZE = 1 * 1024 * 1024 * 1024 # 1 GB

# التأكد من وجود المجلدات الضرورية
for folder in ["orders", "db", "static"]:
    if not os.path.exists(folder):
        os.makedirs(folder)

app.mount("/static", StaticFiles(directory="static"), name="static")

DB_FILE = "db/orders_db.json"
db_lock = asyncio.Lock()

# وظيفة تجلب آيبي الماك وتولد باركود تلقائياً
def generate_qr():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 1))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = '127.0.0.1'
    
    url = f"http://{local_ip}:8000"
    qr_path = "static/qr_code.png"
    qr = qrcode.make(url)
    qr.save(qr_path)
    return url

SERVER_URL = generate_qr()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try: await connection.send_text(message)
            except: pass

manager = ConnectionManager()

def load_db():
    if not os.path.exists(DB_FILE): return []
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return []

@app.get("/")
async def show_form(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

def native_print(path: str, printer: str = None):
    try:
        if platform.system() == "Windows":
            abs_path = os.path.abspath(path)
            if printer:
                current_default_cmd = ['powershell', '-Command', '(Get-WmiObject -Class Win32_Printer -Filter "Default=True").Name']
                current_default = subprocess.run(current_default_cmd, capture_output=True, text=True).stdout.strip()
                set_printer_cmd = ['powershell', '-Command', f'(New-Object -ComObject WScript.Network).SetDefaultPrinter("{printer}")']
                subprocess.run(set_printer_cmd, check=True)
                os.startfile(abs_path, "print")
                if current_default and current_default != printer:
                    time.sleep(5)
                    restore_cmd = ['powershell', '-Command', f'(New-Object -ComObject WScript.Network).SetDefaultPrinter("{current_default}")']
                    subprocess.run(restore_cmd)
            else:
                os.startfile(abs_path, "print")
        else:
            cmd = ['lpr']
            if printer:
                cmd.extend(['-P', printer])
            cmd.append(path)
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True, ""
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        if "no default destination" in error_msg.lower():
            error_msg = "يرجى تحديد طابعة من القائمة أو تعيين طابعة افتراضية."
        return False, error_msg
    except Exception as e:
        return False, str(e)

@app.post("/upload")
async def handle_upload(request: Request, background_tasks: BackgroundTasks, student_name: str = Form(...), department: str = Form(...), notes: str = Form(None), file: UploadFile = File(...)):
    content_length = request.headers.get('content-length')
    if content_length and int(content_length) > MAX_FILE_SIZE:
        return JSONResponse(status_code=400, content={"message": "حجم الملف يتجاوز الحد المسموح (1 جيجا)."})
        
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        return JSONResponse(status_code=400, content={"message": f"النوع ({ext}) غير مدعوم للطباعة. استخدم PDF/DOCX/Images."})

    time_now = datetime.now()
    unique_id = uuid.uuid4().hex[:6]
    file_name = f"{time_now.strftime('%H-%M-%S')}_{unique_id}_{student_name}_{file.filename}"
    save_path = os.path.join("orders", file_name)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    order_data = {"time": time_now.strftime("%Y-%m-%d %H:%M:%S"), "name": student_name, "department": department, "notes": notes or "لا توجد", "file_path": f"/download/{file_name}", "file_system_name": file_name}
    
    async with db_lock:
        db = load_db()
        db.append(order_data)
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
    
    background_tasks.add_task(manager.broadcast, "new_order")
    
    if app_state["auto_print"]:
        background_tasks.add_task(native_print, save_path, app_state["selected_printer"])
        
    return templates.TemplateResponse("success.html", {"request": request, "name": student_name})

@app.get("/dashboard")
async def admin_dashboard(request: Request, username: str = Depends(verify_credentials)):
    return templates.TemplateResponse("dashboard.html", {"request": request, "server_url": SERVER_URL})

@app.post("/api/settings/autoprint")
async def update_autoprint(request: Request, username: str = Depends(verify_credentials)):
    data = await request.json()
    app_state["auto_print"] = data.get("auto_print", False)
    app_state["selected_printer"] = data.get("printer", "")
    return {"status": "success"}

@app.get("/api/settings/autoprint")
async def get_autoprint(username: str = Depends(verify_credentials)):
    return app_state

@app.post("/api/settings/credentials")
async def update_credentials(request: Request, username: str = Depends(verify_credentials)):
    data = await request.json()
    new_user = data.get("username")
    new_pass = data.get("password")
    if new_user and new_pass:
        settings = load_settings()
        settings["username"] = new_user
        settings["password"] = new_pass
        save_settings(settings)
        return {"status": "success"}
    return {"status": "error"}

@app.get("/api/orders")
async def get_orders_api(username: str = Depends(verify_credentials)):
    orders = load_db()
    return {"orders": sorted(orders, key=lambda x: x['time'], reverse=True)}

@app.get("/api/printers")
async def get_printers(username: str = Depends(verify_credentials)):
    try:
        if platform.system() == "Windows":
            result = subprocess.run(['powershell', '-Command', 'Get-Printer | Select-Object -ExpandProperty Name'], capture_output=True, text=True, check=True)
            printers = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        else:
            result = subprocess.run(['lpstat', '-a'], capture_output=True, text=True, check=True)
            printers = [line.split(' ')[0] for line in result.stdout.strip().split('\n') if line]
        return {"status": "success", "printers": printers}
    except Exception as e:
        return {"status": "error", "message": "لا توجد طابعات متاحة", "printers": []}

@app.delete("/api/delete_all")
async def delete_all_orders(username: str = Depends(verify_credentials)):
    async with db_lock:
        for f in os.listdir("orders"):
            os.remove(os.path.join("orders", f))
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    await manager.broadcast("refresh_silent")
    return {"status": "cleared"}

@app.get("/api/print/{filename}")
async def print_order(filename: str, printer: str = None, username: str = Depends(verify_credentials)):
    path = os.path.join("orders", filename)
    if not os.path.exists(path):
        return {"status": "error", "message": "الملف غير موجود"}
    success, err = native_print(path, printer)
    if success:
        return {"status": "success"}
    return {"status": "error", "message": err}

@app.get("/download/{filename}")
async def download_file(filename: str):
    return FileResponse(os.path.join("orders", filename))

@app.delete("/api/delete/{filename}")
async def delete_order(filename: str, username: str = Depends(verify_credentials)):
    path = os.path.join("orders", filename)
    async with db_lock:
        if os.path.exists(path): os.remove(path)
        db = [o for o in load_db() if o['file_system_name'] != filename]
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
    await manager.broadcast("refresh_silent")
    return {"status": "deleted"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect: manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn, webbrowser, threading
    def auto_open_browser():
        time.sleep(2)
        webbrowser.open("http://127.0.0.1:8000/dashboard")
    threading.Thread(target=auto_open_browser, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8000)
