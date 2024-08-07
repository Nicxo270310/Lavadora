from tuya_iot import TuyaOpenAPI
from tuya_connector import TuyaOpenAPI
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from flask import Flask, request, jsonify
import os
import schedule
import threading

app = Flask(__name__)

ACCESS_ID = 'quhpne73atwjcptsd8dt'
ACCESS_KEY = 'a96d4023a806452d96c608fb10be0aea'
ENDPOINT = "https://openapi.tuyaus.com"
DEVICE_ID = '72286240600194c4d67a'

openapi = TuyaOpenAPI(ENDPOINT, ACCESS_ID, ACCESS_KEY)
connect = openapi.connect()

command_on = {"commands":[{"code":"switch_1","value":True}]}
command_off = {"commands":[{"code":"switch_1", "value":False}]}

class Tuya_methods:
    @staticmethod
    def send_off():
        openapi.post(f"/v1.0/iot-03/devices/{DEVICE_ID}/commands", command_off)

    @staticmethod
    def send_on():
        openapi.post(f"/v1.0/iot-03/devices/{DEVICE_ID}/commands", command_on)

scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

key_json = {
    "type": os.getenv("GOOGLE_SERVICE_ACCOUNT_TYPE"),
    "project_id": os.getenv("GOOGLE_PROJECT_ID"),
    "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("GOOGLE_PRIVATE_KEY").replace('\\n', '\n'),
    "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
    "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
    "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("GOOGLE_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.getenv("GOOGLE_CLIENT_X509_CERT_URL"),
    "universe_domain": os.getenv("GOOGLE_UNIVERSE_DOMAIN")
}

creds = ServiceAccountCredentials.from_json_keyfile_dict(key_json, scope)
client = gspread.authorize(creds)

# Abrir la hoja de cálculo
sheet = client.open("Lavadora").sheet1

# Abrir la hoja "Registro"
try:
    registro_sheet = client.open("Lavadora").worksheet("Registro")
except gspread.exceptions.WorksheetNotFound:
    sheet = client.open("Lavadora")
    registro_sheet = sheet.add_worksheet(title="Registro", rows="1000", cols="2")

def extract_time(time_str):
    try:
        datetime_obj = datetime.strptime(time_str, '%m/%d/%Y %H:%M')
        return datetime_obj.strftime('%H:%M:%S')
    except ValueError as e:
        print(f"Error al procesar el tiempo: {e} - Valor recibido: {time_str}")
        return None

def get_times(sheet):
    encendido_times = []
    apagado_times = []
    row = 2
    while True:
        on_time_raw = sheet.cell(row, 4).value
        off_time_raw = sheet.cell(row, 6).value
        
        on_time = extract_time(on_time_raw)
        off_time = extract_time(off_time_raw)
        
        if on_time and off_time:
            encendido_times.append(on_time)
            apagado_times.append(off_time)
        else:
            break
        
        row += 1
    
    return encendido_times, apagado_times

def log_event(action):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Registrando {action} a las {now}")
    registro_sheet.append_row([action, now])

def update_schedule():
    encendido_times, apagado_times = get_times(sheet)
    
    # Limpia las programaciones anteriores
    schedule.clear()

    for i in range(len(encendido_times)):
        if encendido_times[i] and apagado_times[i]:
            schedule.every().day.at(encendido_times[i]).do(lambda: [Tuya_methods.send_on(), log_event('Encendido')])
            schedule.every().day.at(apagado_times[i]).do(lambda: [Tuya_methods.send_off(), log_event('Apagado')])

    # Ejecuta las tareas programadas en un thread separado
    def run_scheduled_tasks():
        while True:
            schedule.run_pending()
            time.sleep(1)
    
    threading.Thread(target=run_scheduled_tasks).start()

@app.route('/api/run-schedule', methods=['POST'])
def run_schedule():
    update_schedule()
    return jsonify({"status": "success"}), 200

@app.route('/api/update-schedule', methods=['POST'])
def update_schedule_endpoint():
    update_schedule()
    return jsonify({"status": "success"}), 200

# Handler para Vercel
def handler(request, *args):
    return app(*args, **request)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)