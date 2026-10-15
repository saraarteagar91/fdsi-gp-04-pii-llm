"""
Generador de datos SINTÉTICOS para entrenar el modelo guardián.

El guardián aprende cómo LUCEN los datos personales colombianos (formatos
de cédula, celular, correo, nomenclatura de direcciones, nombres en
distintas grafías), nunca datos de personas reales: todos los valores se
arman al azar a partir de listas y patrones. Por eso el modelo puede
detectar sin "conocer" a nadie.

Las plantillas se escribieron aparte y NO copian los mensajes de los
conjuntos de evaluación (data/pii_test_cases.csv y
data/pii_holdout_cases.csv), para que la evaluación mida generalización.
"""
import random
import re
import string

LABELS = ["NOMBRE", "CEDULA", "TELEFONO", "CORREO", "DIRECCION"]

NOMBRES = [
    "Juan", "Carlos", "Andrés", "Luis", "Jorge", "Diego", "Santiago", "Sebastián", "Camilo", "Felipe", "Mateo",
    "Alejandro", "Daniel", "David", "Julián", "Óscar", "Ricardo", "Hernán", "Fabio", "Germán", "Iván", "Nicolás",
    "Esteban", "Mauricio", "Wilson", "Jhon", "Brayan", "Cristian", "Edwin", "Fredy", "Gustavo", "Hugo", "Javier",
    "María", "Ana", "Laura", "Paula", "Valentina", "Daniela", "Camila", "Natalia", "Carolina", "Diana", "Sandra",
    "Luz", "Gloria", "Martha", "Claudia", "Lina", "Juliana", "Mariana", "Sofía", "Isabella", "Paola", "Viviana",
    "Yolanda", "Ángela", "Beatriz", "Catalina", "Lorena", "Marcela", "Nubia", "Rocío", "Tatiana", "Ximena", "Yesenia",
]
SEGUNDOS = ["José", "Fernanda", "Alejandra", "Andrea", "Patricia", "Eugenia", "Inés", "Antonio", "Fernando", "Alberto",
            "Enrique", "Camilo", "Esteban", "Lucía", "Cristina", "Elena", "Manuel", "Ignacio", "Isabel", "Mercedes"]
APELLIDOS = [
    "Gómez", "Rodríguez", "Martínez", "García", "López", "Hernández", "González", "Pérez", "Sánchez", "Ramírez",
    "Torres", "Díaz", "Vargas", "Moreno", "Rojas", "Jiménez", "Castro", "Ortiz", "Rubio", "Morales", "Suárez",
    "Restrepo", "Ospina", "Cárdenas", "Henao", "Zapata", "Arango", "Mejía", "Valencia", "Quintero", "Montoya",
    "Salazar", "Cifuentes", "Londoño", "Echeverry", "Bermúdez", "Guerrero", "Acosta", "Mosquera", "Palacios",
    "Córdoba", "Rincón", "Becerra", "Pineda", "Duarte", "Villamil", "Cuervo", "Caicedo", "Benavides", "Buitrago",
    "Peña", "Muñoz", "Ibáñez", "Rivera", "Silva", "Cruz", "Navarro", "Fajardo", "Lozano", "Patiño",
]
DOMINIOS = ["gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "yahoo.es", "outlook.es", "live.com",
            "une.net.co", "correo.co", "empresa.com.co", "unal.edu.co", "udistrital.edu.co", "javeriana.edu.co",
            "uniandes.edu.co", "colegio.edu.co", "alcaldia.gov.co", "tienda.co", "mail.com", "icloud.com", "proton.me"]
CIUDADES = ["Bogotá", "Bogotá D.C.", "Medellín", "Cali", "Barranquilla", "Cartagena", "Bucaramanga", "Pereira",
            "Manizales", "Cúcuta", "Ibagué", "Santa Marta", "Villavicencio", "Pasto", "Tunja", "Neiva", "Armenia",
            "Montería", "Popayán", "Valledupar", "Soacha", "Chía", "Envigado", "Bello", "Itagüí"]
VIAS = ["Calle", "Cl", "Cll", "Cl.", "Carrera", "Cra", "Cra.", "Kr", "Kra", "Avenida", "Av", "Av.", "Av Calle",
        "Avenida Calle", "Av Carrera", "Diagonal", "Dg", "Transversal", "Tv", "Autopista Norte"]
VIAS_NOMBRE = ["Boyacá", "Caracas", "Ciudad de Cali", "Suba", "Las Américas", "Primero de Mayo", "El Dorado", "Pasoancho"]
COMPLEMENTOS = ["Apto {n}", "Apartamento {n}", "Int {d}", "Interior {d}", "Torre {d}", "Casa {d}", "Oficina {n}",
                "Of. {n}", "Piso {d}", "Bloque {L}", "Local {n}", "Torre {d} Apto {n}"]

PRODUCTOS = ["audífonos inalámbricos", "la licuadora", "el portátil", "el smartwatch", "la cafetera", "el televisor",
             "la freidora de aire", "el celular", "la aspiradora", "el teclado", "la impresora", "el parlante"]
MARCAS = ["Samsung", "Xiaomi", "Lenovo", "Apple", "Motorola", "Oster", "Imusa", "Kalley", "Huawei", "LG", "Sony"]


def _rng_digits(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(string.digits) for _ in range(n))


def _group_thousands(digits: str, sep: str) -> str:
    parts = []
    while digits:
        parts.insert(0, digits[-3:])
        digits = digits[:-3]
    return sep.join(parts)


_SILABAS = ["ar", "te", "ga", "ba", "que", "ro", "vi", "llo", "san", "do", "val", "de", "rra", "ma", "ce", "li",
            "no", "ve", "la", "zu", "ña", "ga", "bo", "ter", "mon", "tal", "ri", "co", "bel", "trán", "ya", "pe"]


def _apellido(rng: random.Random) -> str:
    """Apellido de la lista o INVENTADO con sílabas: así el modelo aprende la
    forma y el contexto de un nombre, no una lista de personas."""
    if rng.random() < 0.35:
        return "".join(rng.choice(_SILABAS) for _ in range(rng.randint(2, 3))).capitalize()
    return rng.choice(APELLIDOS)


def nombre(rng: random.Random) -> str:
    style = rng.random()
    first = rng.choice(NOMBRES)
    parts = [first]
    if rng.random() < 0.45:
        parts.append(rng.choice(SEGUNDOS))
    parts.append(_apellido(rng))
    if rng.random() < 0.55:
        parts.append(_apellido(rng))
    if rng.random() < 0.05:
        parts.insert(-1, rng.choice(["de", "del", "de la"]))
    value = " ".join(parts)
    if style < 0.06:  # iniciales: "J. Beltrán G."
        value = f"{first[0]}. {rng.choice(APELLIDOS)}" + (f" {rng.choice(APELLIDOS)[0]}." if rng.random() < 0.6 else "")
    elif style < 0.20:
        value = value.upper()
    elif style < 0.30:
        value = value.lower()
    elif style < 0.36:  # solo nombre y apellido
        value = f"{first} {rng.choice(APELLIDOS)}"
    return value


def cedula(rng: random.Random) -> str:
    n = rng.choice([7, 8, 8, 10, 10, 10])
    digits = ("1" if n == 10 else rng.choice("1234567899")) + _rng_digits(rng, n - 1)
    fmt = rng.random()
    if fmt < 0.35:
        return digits
    if fmt < 0.65:
        return _group_thousands(digits, ".")
    if fmt < 0.75:
        return _group_thousands(digits, ",")
    if fmt < 0.87:
        return _group_thousands(digits, "-")
    return _group_thousands(digits, " ")


def telefono(rng: random.Random) -> str:
    if rng.random() < 0.18:  # fijo con indicativo 60X
        a, b, c = f"60{rng.randint(1, 8)}", _rng_digits(rng, 3), _rng_digits(rng, 4)
    else:
        a, b, c = f"3{rng.choice('012345')}{rng.randint(0, 9)}", _rng_digits(rng, 3), _rng_digits(rng, 4)
    fmt = rng.random()
    if fmt < 0.30:
        num = f"{a}{b}{c}"
    elif fmt < 0.55:
        num = f"{a} {b} {c}"
    elif fmt < 0.68:
        num = f"{a}-{b}-{c}"
    elif fmt < 0.76:
        num = f"{a}.{b}.{c}"
    elif fmt < 0.86:
        num = f"({a}) {b} {c}"
    elif fmt < 0.92:
        num = f"{a} {b}-{c}"
    else:
        num = f"{a[0]}-{a[1:]}-{b}-{c}"
    pref = rng.random()
    if pref < 0.12:
        num = f"+57 {num}"
    elif pref < 0.18:
        num = f"+57{a}{b}{c}"
    elif pref < 0.21:
        num = f"57 {num}"
    return num


def correo(rng: random.Random) -> str:
    first, last = rng.choice(NOMBRES), rng.choice(APELLIDOS)
    norm = lambda s: re.sub(r"[^a-z]", "", s.lower().translate(str.maketrans("áéíóúñü", "aeiounu")))
    user = rng.choice([
        f"{norm(first)}.{norm(last)}", f"{norm(first)}{norm(last)}", f"{norm(first)[0]}{norm(last)}",
        f"{norm(first)}_{norm(last)}{rng.randint(1, 99)}", f"{norm(last)}{rng.randint(70, 2009)}",
        f"{norm(first)}.{norm(last)}+{rng.choice(['compras', 'facturas', 'tienda'])}", f"{norm(first)}{rng.randint(1, 999)}",
    ])
    dom = rng.choice(DOMINIOS)
    style = rng.random()
    if style < 0.08:
        dom_name, *tld = dom.split(".")
        return f"{user.replace('.', ' punto ')} arroba {dom_name} punto {' punto '.join(tld)}"
    if style < 0.14:
        dom_name, *tld = dom.split(".")
        return f"{user}(arroba){dom_name}" + "".join(f"(punto){t}" for t in tld)
    value = f"{user}@{dom}"
    return value.upper() if style < 0.22 else value


def direccion(rng: random.Random) -> str:
    via = rng.choice(VIAS)
    if via.startswith(("Av", "Avenida")) and rng.random() < 0.3 and " " not in via:
        num_via = rng.choice(VIAS_NOMBRE)
    else:
        num_via = str(rng.randint(1, 200)) + (rng.choice(string.ascii_uppercase[:6]) if rng.random() < 0.25 else "")
        if rng.random() < 0.08:
            num_via += " Bis"
    cardinal = rng.choice(["", "", "", " Sur", " Norte", " Este"])
    sep = rng.choice([" # ", " #", " No. ", " N° ", " Nro. ", " ", " # "])
    placa = f"{rng.randint(1, 120)}{rng.choice(['', '', '', 'A', 'B', 'C'])}-{rng.randint(1, 99):02d}"
    value = f"{via} {num_via}{cardinal}{sep}{placa}"
    if rng.random() < 0.15:
        value += rng.choice([" Sur", " Este"])
    if rng.random() < 0.4:
        comp = rng.choice(COMPLEMENTOS).format(n=rng.randint(101, 1504), d=rng.randint(1, 9), L=rng.choice("ABCDE"))
        value += rng.choice([" ", ", "]) + comp
    if rng.random() < 0.35:
        value += f", {rng.choice(CIUDADES)}"
    if rng.random() < 0.15:
        value = value.lower()
    return value


GENERATORS = {"NOMBRE": nombre, "CEDULA": cedula, "TELEFONO": telefono, "CORREO": correo, "DIRECCION": direccion}

# Plantillas con entidades ({NOMBRE}, {CEDULA}...) y relleno sin PII
# ({PRODUCTO}, {MARCA}, {CIUDAD}, {PRECIO}, {PEDIDO}, {FECHA}, {HORA}...).
TEMPLATES_PII = [
    "Buenos días, les escribe {NOMBRE}",
    "buenas tardes, me llamo {NOMBRE} y compré {PRODUCTO}",
    "Mi nombre es {NOMBRE}, necesito ayuda con una compra",
    "Con quién hablo? Soy {NOMBRE}",
    "Te saluda {NOMBRE} desde {CIUDAD}",
    "a nombre de {NOMBRE} quedó el pedido {PEDIDO}",
    "El titular de la cuenta es {NOMBRE}",
    "la factura debe salir a nombre de {NOMBRE}",
    "Cordialmente, {NOMBRE}",
    "Gracias, {NOMBRE}",
    "Quien recibe el paquete es {NOMBRE}",
    "Hola, habla {NOMBRE}, tengo un problema con {PRODUCTO}",
    "Nombre completo: {NOMBRE}",
    "Señora {NOMBRE}, cliente desde 2019",
    "mi mamá {NOMBRE} va a recibir el pedido",
    "{NOMBRE} aquí, ¿ya despacharon?",
    "Autorizo a {NOMBRE} para recoger la compra",
    "Mi cédula es {CEDULA}",
    "cc {CEDULA}",
    "C.C. {CEDULA} de {CIUDAD}",
    "con cédula de ciudadanía {CEDULA}",
    "Número de documento {CEDULA}",
    "documento: {CEDULA}",
    "identificación {CEDULA}, por favor verifiquen",
    "mi número de identificación es {CEDULA}",
    "la cédula del titular es {CEDULA}",
    "Te paso mi documento {CEDULA} para validar",
    "soy {NOMBRE} identificado con c.c. {CEDULA}",
    "Mi celular es {TELEFONO}",
    "llámenme al {TELEFONO}",
    "mi número es {TELEFONO}",
    "Tel. {TELEFONO}",
    "teléfono de contacto: {TELEFONO}",
    "me pueden escribir al whatsapp {TELEFONO}",
    "cel {TELEFONO} en la tarde",
    "Pueden marcar al {TELEFONO} ext 204",
    "{TELEFONO} es mi número",
    "el número de mi esposa es {TELEFONO}",
    "Mi correo es {CORREO}",
    "escríbanme a {CORREO}",
    "email: {CORREO}",
    "envíen la factura al correo {CORREO}",
    "mi correo personal es {CORREO} y el del trabajo {CORREO}",
    "Me registré con {CORREO}",
    "cambien el correo de la cuenta a {CORREO}",
    "{CORREO} es el correo asociado",
    "Vivo en la {DIRECCION}",
    "mi dirección es {DIRECCION}",
    "Dirección de entrega: {DIRECCION}",
    "envíen el paquete a la {DIRECCION}",
    "pueden entregarlo en {DIRECCION}",
    "La casa queda en la {DIRECCION}",
    "Cambien la dirección a {DIRECCION}",
    "Recogida en {DIRECCION} después de las {HORA}",
    "Hola, soy {NOMBRE}, mi cédula es {CEDULA} y mi celular {TELEFONO}",
    "{NOMBRE}, CC {CEDULA}, tel {TELEFONO}, correo {CORREO}",
    "Datos: {NOMBRE} / {CEDULA} / {CORREO}",
    "me llamo {NOMBRE}, vivo en la {DIRECCION} y mi número es {TELEFONO}",
    "Por favor actualicen mi correo a {CORREO} y mi teléfono a {TELEFONO}",
    "El pedido {PEDIDO} es de {NOMBRE}, documento {CEDULA}",
    "Necesito cambiar la dirección {DIRECCION} por otra; mi correo es {CORREO}",
    "{NOMBRE}\n{CEDULA}\n{TELEFONO}\n{DIRECCION}",
    "Hola! soy {NOMBRE} y quiero saber de mi pedido {PEDIDO}, mi cel es {TELEFONO}",
    "compré {PRODUCTO} por {PRECIO}; mi correo es {CORREO}",
    "Mi documento es {CEDULA} y pagué {PRECIO} el {FECHA}",
    "Llamen a {NOMBRE} al {TELEFONO} antes de entregar en la {DIRECCION}",
    "{NOMBRE} {TELEFONO}",
    "Atentamente {NOMBRE}, {CORREO}",
]

TEMPLATES_NEG = [
    "¿Tienen {PRODUCTO} de {MARCA} disponible?",
    "Quiero comprar {PRODUCTO}, ¿cuánto cuesta?",
    "¿El envío a {CIUDAD} demora mucho?",
    "Pagué {PRECIO} y no me ha llegado la confirmación",
    "El pedido {PEDIDO} llegó incompleto",
    "Compré el {FECHA} y todavía nada",
    "¿Atienden hasta las {HORA}?",
    "La referencia {SKU} no aparece en la página",
    "¿Puedo pagar con {MEDIO}?",
    "Tengo un cupón {CUPON} que no funciona",
    "El radicado es {RADICADO}",
    "¿Qué garantía tiene {PRODUCTO} de {MARCA}?",
    "MUCHAS GRACIAS POR SU AYUDA",
    "NO ME HA LLEGADO NADA",
    "Quiero hablar con Servicio Al Cliente",
    "¿La tienda de {CIUDAD} abre los domingos?",
    "Pedí {N} unidades y llegaron {N}",
    "La calle principal de mi barrio está en obra",
    "¿Entregan en la Avenida principal?",
    "¿Tienen sede cerca a la Carrera Séptima?",
    "Mi horario es de 8-12 y de 2-6",
    "El descuento era del {N} % y no se aplicó",
    "Necesito factura electrónica a nombre de la empresa",
    "Hola, buenas noches",
    "¿Cómo hago para devolver {PRODUCTO}?",
    "El producto {MARCA} vino con la caja rota",
    "¿El portátil {MARCA} trae Windows 11?",
    "Gracias por la atención, muy amables",
    "El código de verificación {CODIGO} no me llegó",
    "¿Cuál es el valor del domicilio a {CIUDAD}?",
    "Tengo la versión 2.3.1 de la app",
    "Mi pedido pesa 12,5 kg",
    "Llegó el {FECHA} a las {HORA}",
    "¿Venden repuestos para {PRODUCTO}?",
    "Es para un regalo de cumpleaños",
    "El precio en la página dice {PRECIO} pero me cobraron {PRECIO}",
    "Quiero cancelar el pedido {PEDIDO}",
    "¿Puedo cambiar la talla?",
    "¿Hay promociones en {MARCA} esta semana?",
    "Me interesa el plan de {N} cuotas sin intereses",
    "Según la Ley 1480 de 2011 tengo derecho a la garantía",
    "La Ley 1581 de 2012 protege mis datos, ¿cierto?",
    "Atienden de lunes a sábado de 7:00 a. m. a 8:00 p. m.",
    "Los domingos y festivos abren de 9:00 a. m. a 5:00 p. m.",
    "Un técnico responde en 48 horas hábiles",
    "Tengo 30 días calendario para devolverlo",
    "El reembolso tarda de 5 a 8 días hábiles",
    "En «Mis pedidos» > «Garantía» no aparece nada",
    "Ve a «Mis pedidos» y luego a «Devolver»",
    "Hay hasta 30 % de descuento en audífonos",
    "El envío cuesta $9.900 y es gratis desde $150.000",
    "Llega en 1 a 2 días hábiles a Bogotá, Medellín y Cali",
    "El número de pedido empieza por AM- y tiene cinco dígitos",
    "Mínimo 1 año de garantía en tecnología (Ley 1480 de 2011)",
    "Chat 24/7 y asesores humanos en horario hábil",
    "Te enviamos una guía de recogida gratis",
    "Tenemos tiendas físicas en Bogotá, Medellín y Cali",
    "Me perdí cerca de la Calle de la Moneda",
    "Busco la Carrera de Ingeniería en la universidad",
    "Pasé por la Avenida Boyacá y vi la tienda",
]

FILLERS = {
    "PRODUCTO": lambda r: r.choice(PRODUCTOS),
    "MARCA": lambda r: r.choice(MARCAS),
    "CIUDAD": lambda r: r.choice(CIUDADES),
    "PRECIO": lambda r: r.choice([f"${r.randint(10, 999)}.{r.randint(0, 9)}00", f"{r.randint(20, 900)}.000 pesos",
                                  f"$ {r.randint(1, 3)}.{r.randint(100, 999)}.000"]),
    "PEDIDO": lambda r: f"AM-{r.randint(10000, 99999)}",
    "FECHA": lambda r: r.choice([f"{r.randint(1, 28)}/{r.randint(1, 12)}/2026", f"{r.randint(1, 28)} de octubre", "ayer"]),
    "HORA": lambda r: r.choice([f"{r.randint(1, 12)}:{r.choice(['00', '30', '15'])} pm", f"{r.randint(6, 11)} am"]),
    "SKU": lambda r: f"SKU {r.randint(1000, 9999)}-{r.randint(100, 999)}-{r.randint(100, 999)}",
    "MEDIO": lambda r: r.choice(["PSE", "Nequi", "Daviplata", "tarjeta Visa", "Mastercard", "efectivo"]),
    "CUPON": lambda r: r.choice(["ANDES30", "BLACKFRIDAY", "ENVIOGRATIS", "PRIMERA10"]),
    "RADICADO": lambda r: f"RAD-2026-{r.randint(1000, 999999):06d}",
    "N": lambda r: str(r.randint(1, 24)),
    "CODIGO": lambda r: _rng_digits(r, 6),
}

_SLOT_RE = re.compile(r"\{([A-Z]+)\}")


def render(template: str, rng: random.Random) -> tuple[str, list[tuple[int, int, str]]]:
    """Rellena una plantilla y devuelve (texto, [(inicio, fin, etiqueta)])."""
    text = ""
    ents = []
    pos = 0
    for m in _SLOT_RE.finditer(template):
        text += template[pos:m.start()]
        slot = m.group(1)
        if slot in GENERATORS:
            value = GENERATORS[slot](rng)
            ents.append((len(text), len(text) + len(value), slot))
        else:
            value = FILLERS[slot](rng)
        text += value
        pos = m.end()
    text += template[pos:]
    return text, ents


def _one(rng: random.Random, negative_ratio: float) -> tuple[str, list[tuple[int, int, str]]]:
    template = rng.choice(TEMPLATES_NEG if rng.random() < negative_ratio else TEMPLATES_PII)
    return render(template, rng)


def generate(n: int, seed: int = 13, negative_ratio: float = 0.35) -> list[tuple[str, list[tuple[int, int, str]]]]:
    rng = random.Random(seed)
    data = []
    for _ in range(n):
        text, ents = _one(rng, negative_ratio)
        # textos largos (2-3 oraciones), como las respuestas del chatbot
        if rng.random() < 0.35:
            for _ in range(rng.randint(1, 2)):
                extra, extra_ents = _one(rng, negative_ratio)
                sep = rng.choice([". ", " ", ", ", ". "])
                offset = len(text) + len(sep)
                text += sep + extra
                ents += [(s + offset, e + offset, label) for s, e, label in extra_ents]
        if rng.random() < 0.1:  # algo de ruido: minúsculas, como escribe la gente
            text = text.lower()
        data.append((text, ents))
    return data
