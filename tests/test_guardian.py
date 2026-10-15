"""
Pruebas del servicio guardián (T04): formatos colombianos, mensajes de
control, y que su respuesta nunca contenga el dato en claro.
"""
import json

import pytest


def _protect(services, text):
    resp = services["guardian"].post("/protect", json={"text": text})
    assert resp.status_code == 200
    return resp.json()["entities"]


@pytest.mark.parametrize(
    "text, value, label",
    [
        ("Vivo en la Calle 123 # 45-67, Bogotá, y necesito el paquete", "Calle 123 # 45-67, Bogotá", "DIRECCION"),
        ("Dirección: Cra 7 #10-20 Apto 301, Medellín", "Cra 7 #10-20 Apto 301, Medellín", "DIRECCION"),
        ("me llamo laura martínez y quiero cambiar mi clave", "laura martínez", "NOMBRE"),
        ("Soy ANDRES CAMILO VIVAS BAQUERO, necesito ayuda", "ANDRES CAMILO VIVAS BAQUERO", "NOMBRE"),
        ("Mi correo es juan.perez(arroba)gmail(punto)com", "juan.perez(arroba)gmail(punto)com", "CORREO"),
        ("+573214567890 es mi whatsapp", "+573214567890", "TELEFONO"),
        ("Documento de identidad No. 52-345-678", "52-345-678", "CEDULA"),
        ("Mi número de cédula es 1.020.304.050", "1.020.304.050", "CEDULA"),
    ],
)
def test_detects_colombian_formats(services, text, value, label):
    entities = _protect(services, text)
    match = [e for e in entities if text[e["start"]:e["end"]] == value]
    assert match and match[0]["label"] == label


@pytest.mark.parametrize(
    "text",
    [
        "El pedido AM-10231 llegó con la caja dañada.",
        "GRACIAS POR LA ATENCIÓN",
        "¿Tienen envío gratis para compras mayores a 150.000 pesos?",
        "La referencia del producto es SKU 4455-221-889.",
        "¿Aceptan pagos con PSE y tarjeta de crédito?",
    ],
)
def test_control_messages_are_not_flagged(services, text):
    assert _protect(services, text) == []


def test_guardian_response_never_contains_plaintext(services):
    text = "Soy Sara Arteaga, cédula 1015987654, correo sara.arteaga@correo.edu.co"
    raw = json.dumps(_protect(services, text), ensure_ascii=False)
    for value in ("Sara Arteaga", "1015987654", "sara.arteaga@correo.edu.co"):
        assert value not in raw


def test_same_value_gets_same_blind_index(services):
    a = _protect(services, "mi celular es 300 123 4567")[0]
    b = _protect(services, "Llámame al 3001234567")[0]
    assert a["blind_index"] == b["blind_index"]
    assert a["ciphertext"] != b["ciphertext"]  # el cifrado es aleatorio cada vez


def test_output_guard_redacts_pii_generated_by_the_chatbot(services):
    out = services["guardian"].post("/redact", json={"text": "El cliente Carlos Andrés Restrepo tiene el correo carlos.r@gmail.com"}).json()
    assert "carlos.r@gmail.com" not in out["text"]
    assert "Carlos Andrés Restrepo" not in out["text"]
    assert set(out["redactions"]) == {"NOMBRE", "CORREO"}


def test_output_guard_keeps_markers_and_normal_text(services):
    text = "Listo, [NOMBRE_1]. Registré tu correo [CORREO_1]."
    assert services["guardian"].post("/redact", json={"text": text}).json()["text"] == text
