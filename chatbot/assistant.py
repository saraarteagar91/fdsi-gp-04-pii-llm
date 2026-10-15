"""
Andi: asistente virtual de Andes Market (tienda ficticia), entrenado
localmente. Hace el papel del "LLM externo" de la propuesta: recibe SOLO
el texto que la aplicación decide enviarle (crudo en Unsecure,
anonimizado en Secure) más el historial de la conversación.

Funciona como un LLM pequeño orientado a tareas:
1. Clasifica la intención con el modelo entrenado (training.py).
2. Extrae los datos que el usuario mencionó (su propio NLU, igual que un
   LLM "lee" el mensaje): correo, cédula, teléfono... o sus marcadores.
3. Redacta la respuesta, repitiendo esos datos cuando es natural
   ("Listo Laura, registré tu correo ...") — por eso en Unsecure se
   produce la fuga por reflejo (T03) y en Secure solo se reflejan
   marcadores.
4. Para consultar pedidos emite una llamada a herramienta
   {{consultar_pedido:<dato>}} que resuelve el backend de la tienda
   (dentro del límite de confianza), no el modelo. Si el usuario no dio
   ningún dato, usa {{consultar_pedido:mi_cuenta}}: el pedido más reciente
   de la cuenta con la que inició sesión.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

import joblib

from chatbot.training import MODEL_FILENAME, train
from chatbot.config import settings

CONFIDENCE_THRESHOLD = 0.30

_TOKEN = r"\[(?:NOMBRE|CEDULA|TELEFONO|CORREO|DIRECCION)_\d+\]"
SLOT_PATTERNS = {
    "pedido": [r"\bAM-\d{4,6}\b"],
    "correo": [r"\[CORREO_\d+\]", r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"],
    "cedula": [
        r"\[CEDULA_\d+\]",
        r"(?i)(?:c\.?c\.?|c[eé]dula|documento(?:\s+de\s+identidad)?)\s*(?:es\s+)?(?:no\.?|:)?\s*(\d[\d.,\-]{5,14}\d)",
    ],
    "telefono": [
        r"\[TELEFONO_\d+\]",
        r"(?<!\d)(?:\+?57[\s\-.]?)?\(?3\d{2}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b",
        r"(?<!\d)\(?60[1-8]\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b",
    ],
    "direccion": [
        r"\[DIRECCION_\d+\]",
        r"(?i)\b(?:calle|cl|cll|carrera|cra|kr|diagonal|dg|transversal|tv|avenida|av)\.?\s+[\wáéíóúñ]+(?:\s+sur|\s+norte)?\s*(?:#|no\.?)?\s*\d+\s?[a-z]?\s?-\s?\d+[^.;\n]*",
    ],
    "nombre": [
        r"\[NOMBRE_\d+\]",
        r"(?:(?i:me llamo|mi nombre es|nombre:)|[Ss]oy|[Hh]abla)\s+((?:[A-ZÁÉÍÓÚÑ][\wáéíóúñÁÉÍÓÚÑ.]*\s?){1,5})",
    ],
}

STATIC_RESPONSES = {
    "devoluciones": (
        "Tienes 30 días calendario desde la entrega para devolver un producto sin uso y con su empaque. "
        "Inicia la devolución en «Mis pedidos» > «Devolver» y te enviamos una guía de recogida gratis. "
        "El reembolso se hace al mismo medio de pago en 5 a 8 días hábiles."
    ),
    "garantia": (
        "Todos los productos tienen garantía legal (Ley 1480 de 2011): mínimo 1 año en tecnología y "
        "electrodomésticos. Para hacerla válida, ve a «Mis pedidos» > «Garantía», describe la falla y "
        "adjunta una foto; un técnico te responde en 48 horas."
    ),
    "envios": (
        "Enviamos a todo Colombia. En Bogotá, Medellín y Cali llega en 1 a 2 días hábiles; en el resto del "
        "país, de 3 a 5. El envío es gratis en compras desde $150.000; si no, cuesta $9.900."
    ),
    "metodos_pago": (
        "Aceptamos tarjeta de crédito y débito, PSE, Nequi, Daviplata y pago contra entrega en ciudades "
        "principales. Tu factura electrónica llega al correo registrado y también puedes descargarla en «Mis pedidos»."
    ),
    "horario_atencion": (
        "Nuestro chat atiende 24/7. Los asesores humanos están de lunes a sábado de 7:00 a. m. a 8:00 p. m. "
        "y domingos y festivos de 9:00 a. m. a 5:00 p. m. Tenemos tiendas físicas en Bogotá, Medellín y Cali."
    ),
    "productos": (
        "En Andes Market tenemos tecnología, hogar, electrodomésticos y accesorios. Esta semana hay hasta 30 % "
        "de descuento en audífonos y licuadoras. Puedes ver el catálogo completo en la sección «Productos»."
    ),
    "agradecimiento": "¡Con mucho gusto! ¿Hay algo más en lo que te pueda ayudar?",
    "despedida": "¡Gracias por escribirle a Andes Market! Que tengas un excelente día.",
    "fuera_de_alcance": (
        "Solo puedo ayudarte con temas de Andes Market: pedidos, envíos, devoluciones, garantías, pagos y "
        "actualización de tus datos. Por seguridad, nunca comparto información de otros clientes."
    ),
}

@dataclass
class Slots:
    values: dict[str, str] = field(default_factory=dict)

    def get(self, key: str) -> str | None:
        return self.values.get(key)


def extract_slots(text: str) -> Slots:
    slots = Slots()
    for slot, patterns in SLOT_PATTERNS.items():
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                value = (m.group(1) if m.groups() else m.group(0)).strip(" ,.")
                slots.values[slot] = value
                break
    return slots


class TrainedAssistant:
    def __init__(self, model_dir: str | None = None) -> None:
        model_path = Path(model_dir or settings.model_dir) / MODEL_FILENAME
        if not model_path.exists():
            train(model_dir=model_path.parent, verbose=False)
        self.model = joblib.load(model_path)

    def predict(self, text: str) -> tuple[str, float]:
        probs = self.model.predict_proba([text])[0]
        best = probs.argmax()
        return self.model.classes_[best], float(probs[best])

    def reply(self, message: str, history: list[dict] | None = None) -> str:
        history = history or []
        intent, confidence = self.predict(message)
        slots = extract_slots(message)
        memory = self._memory(history)

        last_bot = next((h["content"] for h in reversed(history) if h["role"] == "assistant"), "")
        only_identifier = any(slots.get(k) for k in ("correo", "cedula", "pedido")) and len(message.split()) <= 3
        if only_identifier and "pedido" in last_bot.lower():
            # el usuario responde con un dato a una conversación sobre pedidos
            intent = "estado_pedido"
        elif confidence < CONFIDENCE_THRESHOLD:
            return (
                "No estoy seguro de haber entendido. Puedo ayudarte con el estado de tu pedido, envíos, "
                "devoluciones, garantías, pagos o actualización de datos. ¿Me lo explicas de otra forma?"
            )

        nombre = slots.get("nombre") or memory.get("nombre")
        trato = f", {nombre}" if nombre else ""

        if intent == "saludo":
            return (
                f"¡Hola{trato}! Soy Andi, el asistente virtual de Andes Market. Puedo ayudarte con tus pedidos, "
                "envíos, devoluciones, garantías, pagos o con la actualización de tus datos. ¿Qué necesitas?"
            )

        if intent == "estado_pedido":
            ident = slots.get("pedido") or slots.get("correo") or slots.get("cedula")
            ident = ident or memory.get("pedido") or memory.get("correo") or memory.get("cedula")
            # sin dato: se consulta el último pedido de la cuenta con la que el
            # usuario inició sesión (la tienda sabe quién es; el chatbot no)
            ident = ident or "mi_cuenta"
            if ident == "mi_cuenta":
                return f"Claro{trato}, revisé tu pedido más reciente. {{{{consultar_pedido:mi_cuenta}}}}"
            return f"Claro{trato}, busqué el pedido asociado a {ident}. {{{{consultar_pedido:{ident}}}}}"

        if intent == "actualizar_datos":
            datos = [
                f"{label} {slots.get(key)}"
                for key, label in (("nombre", "nombre"), ("cedula", "cédula"), ("correo", "correo"),
                                   ("telefono", "teléfono"), ("direccion", "dirección"))
                if slots.get(key)
            ]
            if not datos:
                return "Claro. ¿Qué dato quieres actualizar: nombre, cédula, correo, teléfono o dirección?"
            return (
                f"Listo{trato}. Registré estos datos para actualizar tu cuenta: {', '.join(datos)}. "
                "Quedarán actualizados en máximo 24 horas y te enviaremos una confirmación."
            )

        if intent == "cambio_direccion":
            direccion = slots.get("direccion")
            if not direccion:
                return "Claro. ¿Cuál es la nueva dirección de entrega (calle, número y ciudad)?"
            return (
                f"Perfecto{trato}. Tus próximos pedidos se enviarán a {direccion}. "
                "Si tienes un pedido en camino, la transportadora te confirmará el cambio."
            )

        if intent == "hablar_asesor":
            contacto = slots.get("telefono") or slots.get("correo") or memory.get("telefono") or memory.get("correo")
            if contacto:
                return f"Listo{trato}. Un asesor humano te contactará al {contacto} en las próximas 2 horas hábiles."
            return "Con gusto te comunico con un asesor. ¿A qué teléfono o correo te podemos contactar?"

        if intent == "resumen_conversacion":
            previos = [h["content"] for h in history if h["role"] == "user"]
            if not previos:
                return "Aún no me has contado nada en esta conversación."
            puntos = " ".join(f"({i}) «{m}»" for i, m in enumerate(previos[-5:], 1))
            return f"Este es el resumen de lo que me has escrito{trato}: {puntos}"

        return STATIC_RESPONSES.get(intent, STATIC_RESPONSES["fuera_de_alcance"])

    @staticmethod
    def _memory(history: list[dict]) -> dict[str, str]:
        """Datos mencionados en mensajes anteriores del usuario (el más
        reciente gana)."""
        memory: dict[str, str] = {}
        for h in history:
            if h["role"] == "user":
                memory.update(extract_slots(h["content"]).values)
        return memory


_assistant: TrainedAssistant | None = None


def get_assistant() -> TrainedAssistant:
    global _assistant
    if _assistant is None:
        _assistant = TrainedAssistant()
    return _assistant
