import json
import os

SESSION_FILE = "sesiones_whatsapp.json"

def _load_data():
    if not os.path.exists(SESSION_FILE):
        return {}
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def _save_data(data):
    try:
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error guardando sesión: {e}")

def get_session(phone_number):
    """Obtiene el estado actual de un número de teléfono."""
    data = _load_data()
    return data.get(str(phone_number), {})

def save_session(phone_number, session_data):
    """Guarda o actualiza el estado de un número de teléfono."""
    data = _load_data()
    data[str(phone_number)] = session_data
    _save_data(data)

def delete_session(phone_number):
    """Elimina la sesión de un número de teléfono (cierre de ciclo)."""
    data = _load_data()
    if str(phone_number) in data:
        del data[str(phone_number)]
        _save_data(data)
