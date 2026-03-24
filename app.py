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
threading.Thread(target=monitor_sesiones, daemon=True).start()

@app.route("/", methods=["GET"])
def home():
    return "OK", 200

@app.route("/health", methods=["GET"])
def health():
    return "healthy", 200
    
# ==========================================
#    CREDENCIALES DE INTEGRACIÓN META & GROQ
# ==========================================
# Inyectado directamente en el código según solicitud para Meta v22.0
ACCESS_TOKEN = "EAANfhSTgSFUBRBo5DrPb9ZAneodUv8zxxkN83VCXc9VF3OsyzX9JgfOW69D80kZCk1kZCD3qvQxfjpBQGpF4kmuoZBoIaxLJnfDQ6aKYvxKQloehx2HeZB4JhVSZAK5HeWiO3ZArjZCmQHApgyfy03DhpNQ6226W0ZBA6FAWBra8ZBzfIj9NZCu604LGIWfZAXTXM7TdYX1wfGxwLztQtpUZBnWhraFxg4E5iU5ZAfGwDP8uFl2DD7bnHSuJKaExL2y4vVAdw2MKzoK3JPuPwK63Had3gX1nDZC4gZDZD".strip()
PHONE_NUMBER_ID = "1083068084882723"
VERIFY_TOKEN = "mi_token_seguro_nova"
API_VERSION = "v22.0"

# Groq y número de administrador se cargan desde el .env
GROQ_KEY = os.getenv("GROQ_API_KEY")
ESTEBAN_CEL = os.getenv("ADMIN_PHONE_NUMBER")

# Inicialización segura de Groq
import os

GROQ_KEY = os.environ.get("GROQ_API_KEY")

print("GROQ_KEY:", GROQ_KEY)  # 👈 DEBUG CLAVE

# Inicialización segura de Groq
try:
    if GROQ_KEY:
        client_groq = Groq(api_key=GROQ_KEY)
        print("✅ API KEY cargada correctamente")
    else:
        print("❌ GROQ_API_KEY NO encontrada")
        client_groq = None
except Exception as e:
    print(f"❌ Error inicializando Groq: {e}")
    client_groq = None

# ==========================================
#    FUNCIÓN PARA ENVIAR MENSAJES (META API)
# ==========================================
def send_whatsapp_message(to_number, text_message):
    """
    Envía un mensaje de texto usando la API oficial de Meta WhatsApp Cloud.
    """
    url = f"https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {
            "body": text_message
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
             logger.error(f"Error Enviando a Meta: {response.text}")
        response.raise_for_status()
        logger.info(f"Mensaje enviado exitosamente a {to_number}")
        return True
    except requests.exceptions.HTTPError as err_http:
        logger.error(f"Error HTTP de Meta API: {err_http} - Detalles: {response.text}")
        return False
    except Exception as e:
        logger.error(f"Error general al intentar enviar el mensaje: {e}")
        return False


def alertar_esteban(datos):
    """Envía un resumen ejecutivo de la oportunidad a Esteban vía WhatsApp Cloud API."""
    if not ESTEBAN_CEL:
        return
        
    cuerpo = (
        f"🚨 *NUEVO LEAD ESTELAR - STUDIO NOVA* 🚨\n\n"
        f"🏢 *Compañía:* {datos.get('nombre_empresa', 'N/A').title()}\n"
        f"🎯 *Interés:* {datos.get('servicio', 'N/A')}\n"
        f"💼 *Sector/Producto:* {datos.get('descripcion', 'No especificado').capitalize()}\n"
        f"💰 *Presupuesto:* {datos.get('presupuesto', 'N/A')}\n"
        f"📱 *Teléfono:* wa.me/{datos.get('telefono', 'N/A')}\n\n"
        f"👉 *¡Esteban, es tu momento de cerrar!* 🔥"
    )
def buscar_opcion_numero(texto, opciones_validas):
    """
    Busca el primer número en el texto que coincida con las opciones válidas (ej: [1, 2, 3, 4]).
    Retorna el número como string o None if no se encuentra.
    """
    numeros = re.findall(r'\b\d+\b', texto)
    for n in numeros:
        if n in opciones_validas:
            return n
    return None


# ==========================================
#    LÓGICA CORE: STUDIO NOVA ENGINE
# ==========================================
def procesar_mensaje_bot(numero_usuario, usuario_dice):
    """Motor principal de ChatNova con estado persistente y generación de IA Groq."""
    msg_low = usuario_dice.lower().strip()

    # Cargar estado desde el disco (JSON seguro a reinicios)
    estado_usuario = get_session(numero_usuario)
    paso_actual = estado_usuario.get("paso")
    
    respuesta = ""
    cerrar_sesion = False

    # --- FLUJO 2. BIENVENIDA O OPCIONES ---
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

    # --- FLUJO 2. DESCRIPCIÓN DEL NEGOCIO ---
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
                "No es un bot de botones. Es un asistente que entiende frases naturales, razona con contexto y ejecuta tareas complejas como reservar citas, enviar recordatorios o clasificar solicitudes. 💼\n\n"
                "✅ Maneja consultas, quejas y ventas sin intervención humana.\n"
                "✅ Se adapta al tono y la identidad de tu marca.\n"
                "✅ Aprende con cada interacción de tus clientes.\n\n"
                "👉 **¿Cuál es el nombre de tu empresa o proyecto?** 🏢"
            )
        elif opcion == '4':
            alertar_esteban({"nombre_empresa": "Consulta Directa (Lead Caliente)", "servicio": "Asesoría CEO", "presupuesto": "Por Validar", "telefono": numero_usuario})
            respuesta = "👨‍💻 *Esteban Casas ha sido notificado.* \nEn este momento está revisando tu número y se pondrá en contacto contigo a la brevedad. ¡Hablamos pronto! 🙌"
            cerrar_sesion = True
        else:
            # Respuesta por defecto limpia si escribe algo que no es 1,2,3,4
            estado_usuario = {"paso": "esperando_nombre", "servicio": "Idea Personalizada", "telefono": numero_usuario}
            respuesta = "💡 *¡Me encanta la visión!* \nPara empezar a estructurar una propuesta tecnológica... **¿Me compartes el nombre de tu empresa?** 🏢"

    # --- FLUJO 3. NOMBRE EMPRESA ---
    elif paso_actual == "esperando_nombre":
        # Solo guardamos el nombre y pedimos el sector
        estado_usuario["nombre_empresa"] = usuario_dice
        estado_usuario["paso"] = "esperando_sector"
        respuesta = (
            f"🏢 *¡Perfecto!* Anotamos: *{usuario_dice}*\n\n"
            "👉 **Ahora cuéntanos: ¿a qué sector o producto pertenece tu negocio?** 💼\n"
            "_Ej: Venta de ropa, Taller mecánico, Servicios jurídicos, Panadería, etc._"
        )

    # --- FLUJO 4. SECTOR/PRODUCTO + GROQ ---
    elif paso_actual == "esperando_sector":
        estado_usuario["descripcion"] = usuario_dice  # Guardamos sector como descripcion para la alerta
        nombre_empresa = estado_usuario.get("nombre_empresa", "tu empresa")
        servicio_elegido = estado_usuario.get("servicio", "solución digital")
        funciones_generadas = "✅ Automatización de procesos clave\n✅ Atención de Clientes 24/7\n✅ Generación automática de ventas"
        
        if client_groq:
            try:
                # PROMPT CON NOMBRE + SECTOR: genera plan a medida
                system_prompt = (
                    f"Actúa como consultor de ventas de Studio Nova. "
                    f"Empresa: '{nombre_empresa}', Sector/Producto: '{usuario_dice}', Servicio contratado: '{servicio_elegido}'.\n"
                    f"Crea 3 funciones CONCRETAS y ESPECÍFICAS de '{servicio_elegido}' para este negocio. Cada función debe:\n"
                    "- Mencionar algo puntual del sector o producto del negocio\n"
                    "- Explicar en 1 oración (máx 13 palabras) el impacto o beneficio\n"
                    "- Ser diferente a las otras dos\n"
                    "Formato obligatorio (sin texto extra ni introducciones):\n"
                    "🚀 *Titulo Función 1*: descripción del impacto específico\n"
                    "📊 *Titulo Función 2*: descripción del impacto específico\n"
                    "💰 *Titulo Función 3*: descripción del impacto específico\n"
                    "IMPORTANTE: Usa SOLO Español correcto. NO inventes palabras ni mezcles idiomas. Sin errores ortográficos."
                )
                proc = client_groq.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": system_prompt}],
                    temperature=0.5,
                    max_tokens=400
                )
                res_groq = proc.choices[0].message.content.strip()
                if len(res_groq) > 15:
                    funciones_generadas = res_groq
            except Exception as e:
                logger.error(f"Error de conexión con Groq API (Flujo Sector): {e}")

        estado_usuario["paso"] = "esperando_presupuesto"
        respuesta = (
            f"✨ *PLAN ESTRATÉGICO PARA {nombre_empresa.upper()}* 🚀\n\n"
            f"{funciones_generadas}\n\n"
            f"------------------------------------------\n"
            f"💰 **¿Cuál es el presupuesto que tienes destinado para invertir en esta transformación digital?**\n\n"
            f"1️⃣ *Plan Básico:* $200 USD 💵\n"
            f"2️⃣ *Plan Profesional:* $400 - $600 USD 💸\n"
            f"3️⃣ *Plan Corporativo:* Más de $600 USD 💎\n\n"
            f"_Escribe el número de la opción o el rango esperado._"
        )


    # --- FLUJO 5. CIERRE Y RESUMEN ---
    elif paso_actual == "esperando_presupuesto":
        opcion_pres = buscar_opcion_numero(msg_low, ['1', '2', '3'])
        if opcion_pres == '1':
            estado_usuario["presupuesto"] = "Plan Básico ($200 USD)"
        elif opcion_pres == '2':
            estado_usuario["presupuesto"] = "Plan Profesional ($400 - $600 USD)"
        elif opcion_pres == '3':
            estado_usuario["presupuesto"] = "Plan Corporativo (> $600 USD)"
        else:
            estado_usuario["presupuesto"] = usuario_dice # Si no es número, guardamos el texto literal
            
        if "telefono" not in estado_usuario: 
            estado_usuario["telefono"] = numero_usuario
            
        alertar_esteban(estado_usuario)
        respuesta = (
            "🎯 *¡TODO LISTO Y GUARDADO!* ✅\n\n"
            "Tu informe ejecutivo ya fue transferido a la mesa directiva. El fundador **Esteban Casas**, revisará tu caso personalmente y te escribirá pronto para agilizar el proceso.\n\n"
            "¡Estamos a un paso de revolucionar tu negocio! 🔥"
        )
        cerrar_sesion = True

    # --- FLUJO DESCONOCIDO ---
    else:
        respuesta = "Escribe *'Hola'* para interactuar con nuestras soluciones tecnológicas. 📈"

    # ==========================
    # EJECUCIÓN DEL ENVÍO Y GUARDADO
    # ==========================
    send_whatsapp_message(numero_usuario, respuesta)
    
    # Manejo robusto del estado (Persistencia JSON)
    if cerrar_sesion:
        delete_session(numero_usuario)
        logger.info(f"Ciclo de ventas cerrado exitosamente para {numero_usuario}")
    elif "paso" in estado_usuario:
        save_session(numero_usuario, estado_usuario)
        logger.info(f"Progreso guardado: Cliente {numero_usuario} avanza a paso '{estado_usuario['paso']}'")



# ==========================================
#    RUTAS DEL WEBHOOK (/webhook)
# ==========================================

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Valida hub.mode, hub.verify_token y hub.challenge para enlazado en Meta."""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode and token:
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            logger.info("Verificación de Webhook exitosa aprobada por Meta.")
            return challenge, 200
        else:
            logger.warning("Fallo verificando Webhook: el token no coincide.")
            return jsonify({'error': 'Forbidden'}), 403
            
    return "Studio Nova Engine Online", 200


@app.route('/webhook', methods=['POST'])
def handle_incoming_messages():
    """Procesa el JSON entrante de WhatsApp Cloud y delega al Motor."""
    try:
        body = request.get_json()
        # Puedes mantener el logger gigante temporalmente para auditorías si quieres
        logger.info(f"Evento POST analizado desde Meta.")
        
        if body.get('object'):
            if body.get('entry') and 'changes' in body['entry'][0]:
                cambios = body['entry'][0]['changes'][0]
                
                # Ignorar status indicators de Meta (sent, delivered, read)
                if 'value' in cambios and 'messages' in cambios['value']:
                    mensaje = cambios['value']['messages'][0]
                    numero_remitente = mensaje['from']
                    
                    if mensaje.get('type') == 'text':
                        texto_mensaje = mensaje['text']['body'].strip()
                        # REVISAR SI LA SESIÓN EXPIRÓ (3 minutos = 180 seg)
                        estado_actual = get_session(numero_remitente)
                        if estado_actual and is_session_expired(estado_actual, 180):
                            logger.info(f"Sesión expirada para {numero_remitente}. Reiniciando...")
                            delete_session(numero_remitente)
                        
                        # PASAR AL MOTOR DE VENTAS (Studio Nova Engine)
                        procesar_mensaje_bot(numero_remitente, texto_mensaje)
                            
            # Cumplir con la documentación de Meta para apagar retries
            return 'EVENT_RECEIVED', 200
        else:
            return jsonify({'error': 'Not Found'}), 404

    except Exception as e:
        logger.error(f"Fallo grave procesando el Webhook POST corporativo: {e}")
        return jsonify({'error': 'Internal Server Error', 'details': str(e)}), 500


# ==========================================
#    MONITOR DE SESIONES (BACKGROUND THREAD)
# ==========================================
def monitor_sesiones():
    """
    Revisa periódicamente todas las sesiones y las cierra si han expirado,
    notificando al usuario con el estilo de Studio Nova.
    """
    logger.info("Monitor de sesiones iniciado.")
    while True:
        try:
            sesiones = get_all_sessions()
            ahora = time.time()
            
            for numero, datos in list(sesiones.items()):
                # Solo monitorear si no están en el paso inicial o si queremos cerrar todo
                # Usamos el mismo timeout de 3 minutos (180s)
                if is_session_expired(datos, 180):
                    logger.info(f"Monitor: Sesión expirada para {numero}. Enviando notificación...")
                    
                    mensaje_despedida = (
                        "⏳ *SESIÓN FINALIZADA POR INACTIVIDAD* ⏳\n\n"
                        "Tu tiempo de consulta ha expirado para optimizar nuestros procesos digitales. 🚀\n\n"
                        "No te preocupes, cuando estés listo para llevar tu negocio al siguiente nivel, simplemente escribe *'Hola'* y estaremos listos para asistirte de inmediato. 🔥"
                    )
                    send_whatsapp_message(numero, mensaje_despedida)
                    delete_session(numero)
                    
        except Exception as e:
            logger.error(f"Error en monitor de sesiones: {e}")
            
        time.sleep(30) # Revisar cada 30 segundos


if __name__ == '__main__':
    # Iniciar monitor de sesiones en segundo plano
    threading.Thread(target=monitor_sesiones, daemon=True).start()
    
    puerto = int(os.environ.get("PORT", 5000))
    logger.info(f"🚀 Iniciando Studio Nova Engine (Meta V22.0) en puerto {puerto}")
    app.run(host='0.0.0.0', port=puerto, debug=True)
