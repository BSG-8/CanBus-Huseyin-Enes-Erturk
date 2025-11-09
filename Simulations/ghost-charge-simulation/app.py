import asyncio
import uvicorn
import can
import json
import logging
import websockets
import threading
from datetime import datetime
from typing import Union, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket
from fastapi.templating import Jinja2Templates
from websockets.exceptions import ConnectionClosed

from ocpp.routing import on
from ocpp.v16 import ChargePoint as cp
from ocpp.v16 import call, call_result
from ocpp.v16.enums import Action, RegistrationStatus, ChargePointStatus

logging.basicConfig(level=logging.INFO)

# Konfigürasyon
VIRTUAL_CAN_BUS = "vcano"
CSMS_PORT = 9000
CP_ID = "CP_123"

# CAN ID'leri
START_CHARGE_CAN_ID = 0x200
STOP_CHARGE_CAN_ID = 0x201
METER_VALUE_CAN_ID = 0x300

# Global değişkenler
can_bus: Optional[can.Bus] = None
meter_queue: Optional[asyncio.Queue] = None
cp_queue: Optional[asyncio.Queue] = None
ui_websocket: Optional[WebSocket] = None

SIM_STATE = {
    "is_running": False,
    "attack_mode": False,
    "energy_kwh": 0.0
}

# UI'a log gönderme fonksiyonu
async def send_ui_log(prefix: str, message: str):
    """UI'a log mesajı gönder"""
    if ui_websocket:
        try:
            payload = {
                "type": "log",
                "prefix": prefix,
                "message": message
            }
            await ui_websocket.send_text(json.dumps(payload))
        except:
            pass
    logging.info(f"{prefix}: {message}")

# UI'a veri gönderme fonksiyonu
async def send_ui_data(data_type: str, value: float):
    """UI'a veri gönder"""
    if ui_websocket:
        try:
            payload = {
                "type": "data",
                "data_type": data_type,
                "value": value
            }
            await ui_websocket.send_text(json.dumps(payload))
        except:
            pass

# CAN okuyucu thread
def can_reader_thread(bus: can.Bus, loop: asyncio.AbstractEventLoop):
    """Ayrı thread'de CAN mesajlarını oku"""
    logging.info("CAN Okuyucu: Başlatıldı")
    try:
        while True:
            msg = bus.recv()
            if msg is None:
                continue

            # Mesajı async olarak işle
            if msg.arbitration_id in [START_CHARGE_CAN_ID, STOP_CHARGE_CAN_ID]:
                asyncio.run_coroutine_threadsafe(
                    handle_meter_command(msg), loop
                )
            elif msg.arbitration_id == METER_VALUE_CAN_ID:
                asyncio.run_coroutine_threadsafe(
                    handle_meter_value(msg), loop
                )
    except Exception as e:
        logging.error(f"CAN Okuyucu hatası: {e}")

# Sayaç komutlarını işle
async def handle_meter_command(msg: can.Message):
    """START/STOP komutlarını işle"""
    global can_bus
    
    if msg.arbitration_id == START_CHARGE_CAN_ID and not SIM_STATE["is_running"]:
        SIM_STATE["is_running"] = True
        SIM_STATE["energy_kwh"] = 0.0
        await send_ui_log("SAYAÇ ⚡️", "Fiziksel şarj başlatıldı (0x200 alındı).")
        
        # Enerji üretim döngüsü
        while SIM_STATE["is_running"]:
            await asyncio.sleep(1.0)
            SIM_STATE["energy_kwh"] += 0.5
            
            await send_ui_log("SAYAÇ ⚡️", 
                f"Fiziksel Tüketim: {SIM_STATE['energy_kwh']:.2f} kWh. CAN'a (0x300) gönderiliyor.")
            await send_ui_data("fiziksel", SIM_STATE["energy_kwh"])
            
            # CAN'a gönder
            energy_as_int = int(SIM_STATE["energy_kwh"] * 100)
            can_data = energy_as_int.to_bytes(4, 'little', signed=False)
            
            try:
                if can_bus:
                    can_bus.send(can.Message(
                        arbitration_id=METER_VALUE_CAN_ID, 
                        data=can_data
                    ))
            except can.CanError as e:
                logging.error(f"CAN gönderme hatası: {e}")
    
    elif msg.arbitration_id == STOP_CHARGE_CAN_ID and SIM_STATE["is_running"]:
        SIM_STATE["is_running"] = False
        await send_ui_log("SAYAÇ 🛑", "Fiziksel şarj durduruldu (0x201 alındı).")

# Metre değerlerini işle
async def handle_meter_value(msg: can.Message):
    """CP'ye metre değerini ilet"""
    if cp_queue:
        await cp_queue.put(msg)

# CSMS Server
class SimulatedCSMS(cp):
    @on(Action.boot_notification)
    async def on_boot_notification(self, charge_point_vendor, charge_point_model, **kwargs):
        await send_ui_log("CSMS 🖥️", 
            f"CP ({self.id}) bağlandı: {charge_point_vendor} {charge_point_model}.")
        
        return call_result.BootNotification(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=RegistrationStatus.accepted
        )

    @on(Action.heartbeat)
    async def on_heartbeat(self, **kwargs):
        return call_result.Heartbeat(current_time=datetime.utcnow().isoformat())

    @on(Action.meter_values)
    async def on_meter_values(self, connector_id, meter_value, **kwargs):
        # OCPP mesajından değeri çıkar - hem object hem dict desteği
        try:
            # Object erişimi
            if hasattr(meter_value[0], 'sampled_value'):
                val = meter_value[0].sampled_value[0]
                enerji_wh = float(val.value)
            # Dictionary erişimi (snake_case)
            elif 'sampled_value' in meter_value[0]:
                val = meter_value[0]['sampled_value'][0]
                enerji_wh = float(val['value'])
            # Dictionary erişimi (camelCase)
            else:
                val = meter_value[0]['sampledValue'][0]
                enerji_wh = float(val['value'])
        except (KeyError, AttributeError, IndexError) as e:
            logging.error(f"CSMS: Metre değeri parse hatası: {e}, meter_value: {meter_value}")
            return call_result.MeterValues()
        
        enerji_kwh = enerji_wh / 1000.0
        
        await send_ui_log("CSMS 🖥️", 
            f"RAPOR ALINDI: CP'den {enerji_kwh:.2f} kWh tüketim raporlandı.")
        await send_ui_data("raporlanan", enerji_kwh)
        
        return call_result.MeterValues()

async def handle_csms_connection(websocket):
    """CSMS bağlantısını işle"""
    try:
        path = websocket.request.path
        charge_point_id = path.strip('/')
        
        if charge_point_id != CP_ID:
            logging.warning(f"Bilinmeyen CP: {charge_point_id}")
            return
        
        await send_ui_log("CSMS 🖥️", f"CP ({charge_point_id}) bağlantı isteği gönderdi...")
        csms = SimulatedCSMS(charge_point_id, websocket)
        await csms.start()
    except Exception as e:
        logging.error(f"CSMS bağlantı hatası: {e}")

async def run_csms_server():
    """CSMS WebSocket sunucusunu başlat"""
    await send_ui_log("CSMS 🖥️", f"WebSocket sunucusu 0.0.0.0:{CSMS_PORT} portunda başlatılıyor...")
    
    server = await websockets.serve(
        handle_csms_connection,
        "0.0.0.0",
        CSMS_PORT,
        subprotocols=["ocpp1.6"]
    )
    
    try:
        await server.wait_closed()
    except asyncio.CancelledError:
        logging.info("CSMS sunucusu kapatıldı")

# Charge Point Client
class SimulatedCP(cp):
    def __init__(self, id, connection, message_queue: asyncio.Queue):
        super().__init__(id, connection)
        self.message_queue = message_queue
        self.status = ChargePointStatus.available
        self.transaction_id = 1

    async def send_boot_notification(self):
        await send_ui_log("CP 🔌", "CSMS'e BootNotification gönderiliyor...")
        
        request = call.BootNotification(
            charge_point_model="SanalCP-2000",
            charge_point_vendor="Gorsel-Sim"
        )
        response = await self.call(request)
        
        if response.status == RegistrationStatus.accepted:
            await send_ui_log("CP 🔌", "CSMS tarafından kabul edildi (Accepted).")
        else:
            await send_ui_log("CP 🔌", "CSMS tarafından reddedildi (Rejected).")
        
        self.status = ChargePointStatus.available

    async def send_meter_value(self, energy_kwh: float):
        """CSMS'e metre değeri gönder"""
        raporlanan_kwh = energy_kwh
        
        if SIM_STATE["attack_mode"]:
            raporlanan_kwh = 0.01
            await send_ui_log("CP 💻", 
                f"SALDIRI! Gerçek ({energy_kwh:.2f} kWh) yerine Sahte ({raporlanan_kwh} kWh) raporlanıyor.")
        else:
            await send_ui_log("CP 🔌", 
                f"Gerçek tüketim ({energy_kwh:.2f} kWh) CSMS'e raporlanıyor.")
        
        enerji_wh_str = str(int(raporlanan_kwh * 1000))
        
        request = call.MeterValues(
            connector_id=1,
            transaction_id=self.transaction_id,
            meter_value=[{
                "timestamp": datetime.utcnow().isoformat(),
                "sampled_value": [{
                    "value": enerji_wh_str,
                    "unit": "Wh",
                    "measurand": "Energy.Active.Import.Register"
                }]
            }]
        )
        await self.call(request)

    async def listen_can_messages(self):
        """CAN mesajlarını dinle"""
        await send_ui_log("CP 🔌", "CAN-bus (vcano) mesaj kuyruğu dinleniyor...")
        
        try:
            while True:
                msg = await self.message_queue.get()
                
                if msg.arbitration_id == METER_VALUE_CAN_ID:
                    energy_as_int = int.from_bytes(msg.data[:4], 'little', signed=False)
                    energy_kwh = float(energy_as_int / 100.0)
                    
                    await send_ui_log("CP 🔌", 
                        f"CAN'dan (0x300) {energy_kwh:.2f} kWh fiziksel veri okundu.")
                    
                    if SIM_STATE["is_running"]:
                        await self.send_meter_value(energy_kwh)
        except asyncio.CancelledError:
            logging.info("CP CAN dinleyici kapatıldı")
        except Exception as e:
            logging.error(f"CP CAN dinleyici hatası: {e}")

async def run_cp_client():
    """CP istemcisini çalıştır"""
    global cp_queue
    
    await asyncio.sleep(2)
    await send_ui_log("CP 🔌", f"CSMS'e (localhost:{CSMS_PORT}) bağlanılıyor...")
    
    try:
        async with websockets.connect(
            f"ws://localhost:{CSMS_PORT}/{CP_ID}",
            subprotocols=["ocpp1.6"]
        ) as ws:
            cp_instance = SimulatedCP(CP_ID, ws, cp_queue)
            
            await asyncio.gather(
                cp_instance.start(),
                cp_instance.listen_can_messages(),
                cp_instance.send_boot_notification()
            )
    except Exception as e:
        logging.error(f"CP istemci hatası: {e}")
        await send_ui_log("CP 🔌", f"HATA: CSMS'e bağlanılamadı. {e}")

# FastAPI Lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    global can_bus, meter_queue, cp_queue
    
    logging.info("Uygulama başlatılıyor...")
    
    # CAN bus aç (loopback ile - kendi mesajlarını da okuyabilmek için)
    try:
        can_bus = can.interface.Bus(
            VIRTUAL_CAN_BUS, 
            bustype='socketcan',
            receive_own_messages=True  # KRITIK: Kendi gönderdiği mesajları da oku
        )
        logging.info(f"CAN arayüzü '{VIRTUAL_CAN_BUS}' açıldı (loopback aktif)")
    except Exception as e:
        logging.error(f"CAN açılamadı: {e}")
        yield
        return
    
    # Kuyrukları oluştur
    meter_queue = asyncio.Queue()
    cp_queue = asyncio.Queue()
    
    # CAN okuyucu thread'i başlat
    loop = asyncio.get_running_loop()
    can_thread = threading.Thread(
        target=can_reader_thread,
        args=(can_bus, loop),
        daemon=True
    )
    can_thread.start()
    
    # Görevleri başlat
    asyncio.create_task(run_csms_server())
    asyncio.create_task(run_cp_client())
    
    yield
    
    # Temizlik
    logging.info("Uygulama kapatılıyor...")
    if can_bus:
        can_bus.shutdown()

# FastAPI uygulaması
app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory=".")

@app.get("/")
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global ui_websocket
    
    await websocket.accept()
    ui_websocket = websocket
    logging.info("UI bağlandı")
    
    # Başlangıç logları gönder
    await send_ui_log("SİSTEM ⚙️", "Backend sunucusuna bağlandı.")
    await send_ui_log("CSMS 🖥️", f"WebSocket sunucusu 0.0.0.0:{CSMS_PORT} portunda çalışıyor.")
    await send_ui_log("SAYAÇ ⚙️", "Simülatör hazır, komut bekleniyor...")
    
    try:
        while True:
            data = await websocket.receive_text()
            
            if data == "TOGGLE_ATTACK":
                SIM_STATE["attack_mode"] = not SIM_STATE["attack_mode"]
                status = "AKTİF 💻" if SIM_STATE["attack_mode"] else "KAPALI ✅"
                await send_ui_log("SİSTEM ⚙️", f"SALDIRI MODU DEĞİŞTİ: {status}")
            
            elif data == "START_SIM":
                if not SIM_STATE["is_running"] and can_bus:
                    await send_ui_log("SİSTEM ⚙️", "ARAYÜZDEN BAŞLATMA TETİKLENDİ.")
                    await send_ui_log("CP 🔌", "Fiziksel sayaca 'Başlat' (0x200) komutu gönderiliyor...")
                    can_bus.send(can.Message(arbitration_id=START_CHARGE_CAN_ID))
            
            elif data == "STOP_SIM":
                if SIM_STATE["is_running"] and can_bus:
                    await send_ui_log("SİSTEM ⚙️", "ARAYÜZDEN DURDURMA TETİKLENDİ.")
                    await send_ui_log("CP 🔌", "Fiziksel sayaca 'Durdur' (0x201) komutu gönderiliyor...")
                    can_bus.send(can.Message(arbitration_id=STOP_CHARGE_CAN_ID))
    
    except Exception as e:
        logging.warning(f"UI bağlantı hatası: {e}")
    finally:
        ui_websocket = None
        logging.info("UI bağlantısı kesildi")

if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    
    logging.info("FastAPI sunucusu başlatılıyor... (http://127.0.0.1:8000)")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
