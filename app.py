import os
import requests
import logging
import json
import re
import time
import threading
from flask import Flask, request, jsonify
from groq import Groq
from dotenv import load_dotenv

from state_manager import get_session, save_session, delete_session, is_session_expired, get_all_sessions

# ==========================================
#    CONFIGURACIÓN DE ENTORNO Y LOGGING
# ==========================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Memoria temporal para evitar que Render repita mensajes (Filtro de duplicados)
PROCESSED_IDS = []

@app.route("/", methods=["GET"])
def home():
    return "Studio Nova Engine Online", 200

@app.route("/health", methods=["GET"])
def health():
    return "healthy", 200

# ==========================================
#    CREDENCIALES DE INTEGRACIÓN META & GROQ
# ==========================================
ACCESS_TOKEN = "EAANfhSTgSFUBRBDcViZBb5lGr5j37eMHKjJdyx70YvxurFOe3y11BZAZC2734IeBaZA2oBo3fxBakUCFegHoYtTgDxZAbSkXJwivTusTvw2HSHwdtruqNfyQv0NjBiXGeRKUZBZBaEKRG3mYgGxhQYA9pL5tNTZCiSwKXdze4nWLqysZCYRWSKpWJLZAMiqncx".strip()
PHONE_NUMBER_ID = "1083068084882723"
VERIFY_TOKEN = "mi_token_seguro_nova"
API_VERSION = "v22.0"

GROQ_KEY = os.environ.get("GROQ_API_KEY")
ESTEBAN_CEL = os.getenv("ADMIN_PHONE_NUMBER")

try:
    if GROQ_KEY:
        client_groq = Groq(api_key=GROQ_KEY)
        logger.info("✅ API KEY de Groq cargada correctamente")
    else:
        logger.error("❌ GROQ_API_KEY NO encontrada")
        client_groq = None
except Exception as e:
    logger.error(f"❌ Error inicializando Groq: {e}")
    client_groq = None

# ==========================================
#    FUNCIONES DE APOYO (MENSAJERÍA Y LÓGICA)
# ==========================================
def send_whatsapp_message(to_number, text_message):
    url = f"https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": to_number, "type": "text", "text": {"body": text_message}}
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
             logger.error(f"Error Enviando a Meta: {response.text}")
        return True
    except Exception as e:
        logger.error(f"Error enviando mensaje: {e}")
        return False

def buscar_opcion_numero(texto, opciones_validas):
    numeros = re.findall(r'\b\d+\b', texto)
    for n in numeros:
        if n in opciones_validas: return n
    return None

# ==========================================
#    LÓGICA CORE: STUDIO NOVA ENGINE
# ==========================================
def procesar_mensaje_bot(numero_usuario, usuario_dice):
    """Motor principal con las descripciones comerciales restauradas."""
    msg_low = usuario_dice.lower().strip()
    estado_usuario = get_session(numero_usuario)
    paso_actual = estado_usuario.get("paso")
    
    respuesta = ""
    cerrar_sesion = False

    # --- FLUJO 1. BIENVENIDA O OPCIONES ---
    if msg_low in ['hola', 'inicio', 'menu', 'menú', 'buenos dias', 'buenas tardes'] or not paso_actual:
        estado_usuario = {"paso": "inicio"}
        respuesta = (
            "👋 ¡Hola! Bienvenido a *Studio Nova*.\n\n"
            "Diseñamos ecosistemas digitales que facturan en automático. 🚀 ¿Cómo llevaremos hoy tu negocio al siguiente nivel?\n\n"
            "🤖 *1.* Chatbots IA (Agentes de Ventas 24/7)\n"
            "🌐 *2.* Páginas Web Premium\n"
            "🧠 *3.* Asistentes Virtuales _(Beta)_\n"
            "👨‍💻 *4.* Hablar con Esteban Casas (CEO)\n\n"
            "👉 *Escribe el número de la opción que más te resuene:* ✨"
        )

    # --- FLUJO 2. DESCRIPCIÓN DETALLADA DEL SERVICIO ---
    elif paso_actual == "inicio":
        opcion = buscar_opcion_numero(msg_low, ['1', '2', '3', '4'])
        
        if opcion == '1':
            estado_usuario = {"paso": "esperando_nombre", "servicio": "Chatbots IA", "telefono": numero_usuario}
            respuesta = (
                "🤖 *CHATBOTS IA — Agentes de Ventas 24/7*\n\n"
                "Imagina que tu negocio responde clientes a las 3am, envía precios automáticos y agenda citas — sin que tú levantes un dedo. ☏\ufe0f\n\n"
                "✅ Tu asistente conoce tus productos mejor que cualquier empleado.\n"
                "✅ Nunca se cansa. Nunca pide día libre.\n"
                "✅ Cierra tratos a cualquier hora del día.\n\n"
                "👉 **¿Cuál es el nombre de tu empresa o proyecto?** 🏢"
            )
        elif opcion == '2':
            estado_usuario = {"paso": "esperando_nombre", "servicio": "Páginas Web", "telefono": numero_usuario}
            respuesta = (
                "🌐 *PÁGINAS WEB PREMIUM — Tu Imagen Vale Oro*\n\n"
                "Tu web es lo primero que ven tus clientes antes de escribirte. Una página profesional convierte visitantes en compradores desde el primer segundo. 👀\n\n"
                "✅ Diseño moderno adaptado a tu marca y sector.\n"
                "✅ Posicionamiento en Google para que te encuentren solos.\n"
                "✅ Integrada con tus redes y WhatsApp.\n\n"
                "👉 **¿Cuál es el nombre de tu empresa?** 🏢"
            )
        elif opcion == '3':
            estado_usuario = {"paso": "esperando_nombre", "servicio": "Asistentes Virtuales", "telefono": numero_usuario}
            respuesta = (
                "🧠 *ASISTENTES VIRTUALES — Tu Empleado Digital* _(Beta)_\n\n"
                "No es un bot de botones. Es un asistente que entiende frases naturales, razona con contexto y ejecuta tareas complejas como reservar citas o clasificar solicitudes. 💼\n\n"
                "✅ Maneja consultas, quejas y ventas sin intervención humana.\n"
                "✅ Se adapta al tono y la identidad de tu marca.\n"
                "✅ Aprende con cada interacción de tus clientes.\n\n"
                "👉 **¿Cuál es el nombre de tu empresa o proyecto?** 🏢"
            )
        elif opcion == '4':
            respuesta = "👨‍💻 *Esteban Casas ha sido notificado.* \nEn este momento está revisando tu caso y se pondrá en contacto contigo a la brevedad. ¡Hablamos pronto! 🙌"
            cerrar_sesion = True
        else:
            respuesta = "Por favor, elige una opción del *1 al 4* para mostrarte cómo podemos escalar tu negocio. 📈"

    # --- FLUJO 3. NOMBRE EMPRESA ---
    elif paso_actual == "esperando_nombre":
        estado_usuario["nombre_empresa"] = usuario_dice
        estado_usuario["paso"] = "esperando_sector"
        respuesta = (
            f"🏢 *¡Perfecto!* Anotamos: *{usuario_dice}*\n\n"
            "👉 **Ahora cuéntanos: ¿a qué sector o producto pertenece tu negocio?** 💼\n"
            "_Ej: Taller mecánico, Servicios jurídicos, Inmobiliaria, etc._"
        )

    # --- FLUJO 4. SECTOR + ESTRATEGIA IA (GROQ) ---
    elif paso_actual == "esperando_sector":
        estado_usuario["descripcion"] = usuario_dice
        nombre_empresa = estado_usuario.get("nombre_empresa", "tu empresa")
        servicio_elegido = estado_usuario.get("servicio", "solución digital")
        
        funciones_generadas = "✅ Automatización de procesos clave\n✅ Atención de Clientes 24/7\n✅ Generación automática de ventas"
        
        if client_groq:
            try:
                system_prompt = (
                    f"Actúa como consultor de Studio Nova. Empresa: '{nombre_empresa}', Sector: '{usuario_dice}', Servicio: '{servicio_elegido}'.\n"
                    f"Crea 3 funciones CONCRETAS (máx 15 palabras c/u) con formato:\n"
                    f"🚀 *Titulo*: beneficio.\n📊 *Titulo*: beneficio.\n💰 *Titulo*: beneficio."
                )
                proc = client_groq.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": system_prompt}],
                    temperature=0.6
                )
                res_groq = proc.choices[0].message.content.strip()
                if len(res_groq) > 20: funciones_generadas = res_groq
            except: pass

        estado_usuario["paso"] = "esperando_presupuesto"
        respuesta = (
            f"✨ *ESTRATEGIA PARA {nombre_empresa.upper()}* 🚀\n\n"
            f"{funciones_generadas}\n\n"
            f"------------------------------------------\n"
            f"💰 **¿Qué presupuesto tienes destinado para esta inversión?**\n\n"
            f"1️⃣ *Plan Básico:* $200 USD\n"
            f"2️⃣ *Plan Pro:* $400 - $600 USD\n"
            f"3️⃣ *Plan Elite:* Más de $600 USD\n\n"
            f"_Escribe el número de tu opción._"
        )

    # --- FLUJO 5. CIERRE ---
    elif paso_actual == "esperando_presupuesto":
        respuesta = (
            "🎯 *¡PROCESO COMPLETADO!* ✅\n\n"
            "Tu informe ha sido enviado. **Esteban Casas** revisará los detalles de tu proyecto para contactarte con una propuesta técnica a medida.\n\n"
            "¡Es hora de llevar tu facturación al siguiente nivel! 🔥"
        )
        cerrar_sesion = True

    # --- ENVÍO Y PERSISTENCIA ---
    send_whatsapp_message(numero_usuario, respuesta)
    
    if cerrar_sesion:
        delete_session(numero_usuario)
    else:
        save_session(numero_usuario, estado_usuario)

# ==========================================
#    RUTAS DEL WEBHOOK
# ==========================================
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        return challenge, 200
    return "Studio Nova Engine Online", 200

@app.route('/webhook', methods=['POST'])
def handle_incoming_messages():
    try:
        body = request.get_json()
        if not body or body.get('object') != 'whatsapp_business_account':
            return jsonify({'error': 'Not Found'}), 404

        value = body['entry'][0]['changes'][0]['value']

        # 1. FILTRO DE ESTADOS: Ignorar avisos de "entregado" o "leído"
        if 'statuses' in value:
            return 'STATUS_RECEIVED', 200

        # 2. PROCESAR MENSAJES REALES
        if 'messages' in value:
            mensaje = value['messages'][0]
            msg_id = mensaje.get('id')
            numero_remitente = mensaje['from']
            
            # FILTRO DE DUPLICADOS: Si el ID ya se procesó, ignorar
            if msg_id in PROCESSED_IDS:
                return 'DUPLICATE_IGNORED', 200
            
            # Guardar ID en memoria (últimos 100)
            PROCESSED_IDS.append(msg_id)
            if len(PROCESSED_IDS) > 100: PROCESSED_IDS.pop(0)

            if mensaje.get('type') == 'text':
                texto_mensaje = mensaje['text']['body'].strip()
                
                # REVISAR EXPIRACIÓN ANTES DE PROCESAR
                estado_actual = get_session(numero_remitente)
                if estado_actual and is_session_expired(estado_actual, 180):
                    delete_session(numero_remitente)
                
                procesar_mensaje_bot(numero_remitente, texto_mensaje)
                            
        return 'EVENT_RECEIVED', 200
    except Exception as e:
        logger.error(f"Error Webhook: {e}")
        return 'ERROR_HANDLED', 200

# ==========================================
#    MONITOR DE SESIONES
# ==========================================
def monitor_sesiones():
    while True:
        try:
            sesiones = get_all_sessions()
            for numero, datos in list(sesiones.items()):
                if is_session_expired(datos, 180):
                    logger.info(f"Monitor: Cerrando sesión de {numero}")
                    mensaje = "⏳ *SESIÓN FINALIZADA*\nTu tiempo de consulta ha terminado. Escribe *'Hola'* cuando gustes retomar. 🚀"
                    send_whatsapp_message(numero, mensaje)
                    delete_session(numero)
        except Exception as e:
            logger.error(f"Error monitor: {e}")
        time.sleep(30)

if __name__ == '__main__':
    # El monitor se inicia solo una vez aquí
    threading.Thread(target=monitor_sesiones, daemon=True).start()
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)
