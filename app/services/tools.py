"""
Resolución de las "llamadas a herramienta" que emite el chatbot, del tipo
{{consultar_pedido:<dato>}}.

En el flujo Secure, <dato> es un marcador ([CORREO_1]). La tienda le pide
a la bóveda que lo descifre SOLO para consultar el sistema interno de
pedidos (propósito "consultar_pedido", queda en la bitácora de la
bóveda); el resultado que se inserta en la respuesta no contiene datos
personales. Así se cumple T05 sin que el chatbot vea el dato.

<dato> también puede ser "mi_cuenta": el pedido más reciente del usuario
autenticado. Así el cliente ni siquiera necesita escribir su correo.
La búsqueda está restringida a los pedidos de ese usuario.
"""
import re
from dataclasses import dataclass
from typing import Callable

from app.services.orders import describe_order, find_order
from common.tokens import TOKEN_RE

TOOL_RE = re.compile(r"\{\{\s*consultar_pedido\s*:\s*([^}]+?)\s*\}\}")


@dataclass
class ToolCall:
    tool: str
    argument: str              # lo que escribió el chatbot (marcador en Secure)
    resolved_internally: bool  # True si hubo que pedirle a la bóveda el dato real
    found: bool


def resolve_tool_calls(text: str, resolver: Callable[[str], str | None] | None, user: dict | None) -> tuple[str, list[ToolCall]]:
    calls: list[ToolCall] = []

    def _run(match: re.Match) -> str:
        argument = match.group(1)
        real_value, resolved = argument, False
        if resolver and TOKEN_RE.fullmatch(argument):
            real_value, resolved = resolver(argument), True
        order = find_order(real_value, user) if real_value else None
        calls.append(ToolCall("consultar_pedido", argument, resolved, order is not None))
        return describe_order(order)

    return TOOL_RE.sub(_run, text), calls
