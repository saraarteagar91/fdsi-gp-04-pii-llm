"""
Pruebas del chatbot entrenado (Andi) y del flujo completo de la página:
T03 (reflejo), T05 (utilidad con consulta de pedido) y la página web.
"""
import pytest

from app.services.tools import resolve_tool_calls
from chatbot.assistant import TrainedAssistant

PII_MESSAGE = "Hola, soy Juan Carlos Pérez Gómez, cédula 1.020.304.050, correo juan.perez@gmail.com, celular 300 123 4567"


@pytest.fixture(scope="module")
def assistant():
    return TrainedAssistant()


@pytest.mark.parametrize(
    "message, intent",
    [
        ("¿Dónde está mi pedido?", "estado_pedido"),
        ("¿Cuál es el estado de mi pedido asociado al correo [CORREO_1]?", "estado_pedido"),
        ("quiero devolver un producto", "devoluciones"),
        ("¿qué métodos de pago aceptan?", "metodos_pago"),
        ("resume lo que te dije", "resumen_conversacion"),
        ("mi nueva dirección es [DIRECCION_1]", "cambio_direccion"),
    ],
)
def test_trained_assistant_classifies_intents(assistant, message, intent):
    assert assistant.predict(message)[0] == intent


def test_assistant_emits_tool_call_with_the_marker(assistant):
    assert "{{consultar_pedido:[CORREO_1]}}" in assistant.reply("¿Cuál es el estado de mi pedido asociado al correo [CORREO_1]?")


def test_assistant_uses_logged_account_when_no_identifier(assistant):
    """Sin dato, el chatbot pide el pedido de la cuenta con sesión iniciada:
    el cliente no necesita escribir ningún dato personal."""
    assert "{{consultar_pedido:mi_cuenta}}" in assistant.reply("quiero saber dónde está mi pedido")


def _user(email):
    from app import db

    return db.one("SELECT id, rol FROM usuarios WHERE email = ?", (email,))


def test_tool_uses_resolver_only_for_markers(services):
    juan = _user("juan.perez@gmail.com")
    text, calls = resolve_tool_calls("Revisé: {{consultar_pedido:[CORREO_1]}}", lambda t: "juan.perez@gmail.com", juan)
    assert "AM-10231" in text and "En camino" in text and "juan.perez@gmail.com" not in text
    assert calls[0].resolved_internally and calls[0].found
    sara = _user("sara.arteaga@correo.edu.co")
    text, calls = resolve_tool_calls("{{consultar_pedido:AM-10458}}", lambda t: pytest.fail("no debe llamar a la bóveda"), sara)
    assert "Entregado" in text and not calls[0].resolved_internally


def test_customer_cannot_query_someone_elses_order_through_the_chat(customer, local_llm):
    """IDOR: Juan pregunta por el pedido de Sara (AM-10458) y por su correo."""
    for msg in ("¿Cómo va el pedido AM-10458?", "estado del pedido del correo sara.arteaga@correo.edu.co"):
        r = customer.post("/secure/chat", json={"message": msg}).json()
        assert "Licuadora" not in r["response"] and "Entregado" not in r["response"]
        assert "No encontré ese pedido en tu cuenta" in r["response"]


def test_my_order_without_typing_personal_data(customer, local_llm):
    r = customer.post("/secure/chat", json={"message": "¿Dónde está mi pedido?"}).json()
    assert r["audit"]["llm_input"] == "¿Dónde está mi pedido?"
    assert r["audit"]["tool_calls"][0]["argument"] == "mi_cuenta" and r["audit"]["tool_calls"][0]["found"]


def test_t05_secure_answers_order_status_without_sending_email_to_chatbot(customer, local_llm):
    r = customer.post("/secure/chat", json={"message": "¿Cuál es el estado de mi pedido asociado al correo juan.perez@gmail.com?"}).json()
    assert "AM-10231" in r["response"] and "En camino" in r["response"]
    assert "juan.perez@gmail.com" not in r["audit"]["llm_input"]
    assert "juan.perez@gmail.com" not in r["audit"]["logged_response"]
    assert r["audit"]["tool_calls"][0]["resolved_internally"] is True


def test_t03_reflection_secure_vs_unsecure(client, local_llm):
    results = {}
    for scenario in ("unsecure", "secure"):
        first = client.post(f"/{scenario}/chat", json={"message": PII_MESSAGE}).json()
        results[scenario] = client.post(
            f"/{scenario}/chat", json={"message": "Resume lo que te dije", "session_id": first["session_id"]}
        ).json()
    assert "juan.perez@gmail.com" in results["unsecure"]["audit"]["llm_output"]
    assert "juan.perez@gmail.com" not in results["secure"]["audit"]["llm_output"]
    assert "[CORREO_1]" in results["secure"]["audit"]["llm_output"]
    assert "juan.perez@gmail.com" not in results["secure"]["audit"]["logged_response"]
    assert "juan.perez@gmail.com" in results["secure"]["response"]


def test_session_ids_do_not_cross_scenarios(client, local_llm):
    secure = client.post("/secure/chat", json={"message": PII_MESSAGE}).json()
    leaked = client.post("/unsecure/chat", json={"message": "Resume lo que te dije", "session_id": secure["session_id"]}).json()
    assert "juan.perez@gmail.com" not in leaked["response"]


def test_web_page_and_admin_api(admin, anon):
    page = anon.get("/")
    assert page.status_code == 200 and "Andes Market" in page.text
    assert "simulad" not in page.text.lower()
    assert len(anon.get("/api/products").json()) == 12
    assert len(admin.get("/api/admin/demo-data").json()["clientes"]) == 5
    services = admin.get("/api/admin/services").json()
    assert services["guardian"]["puede_descifrar"] is False
    assert services["vault"]["tiene_llave_privada"] is True
    assert admin.get("/api/admin/logs/otro").status_code == 404
