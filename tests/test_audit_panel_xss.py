"""
Prueba de regresión del Lab. 05 (hallazgo F-08, CodeQL #3 "DOM text
reinterpreted as HTML"): el panel de auditoría no debe decidir si escapa un
texto mirando si empieza por "<div". El mensaje del usuario y la respuesta
del LLM se escapan siempre; solo el HTML marcado con trusted() se inserta tal
cual.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

APP_JS = Path(__file__).resolve().parent.parent / "static" / "app.js"
PAYLOAD = "<div><img src=x onerror=1>"


def _source() -> str:
    return APP_JS.read_text(encoding="utf-8")


def _extract(pattern: str, src: str) -> str:
    match = re.search(pattern, src, re.S | re.M)
    assert match, f"no se encontró {pattern!r} en static/app.js"
    return match.group(0)


def test_no_content_sniffing_to_skip_escaping():
    src = _source()
    assert 'startsWith("<div")' not in src
    assert "startsWith('<div')" not in src
    step = _extract(r"^\s*function step\(.*?^\s*\}$", src)
    assert "esc(title)" in step
    assert "asHtml(content)" in step


@pytest.mark.skipif(shutil.which("node") is None, reason="node no está instalado")
def test_step_escapes_user_and_llm_text():
    src = _source()
    helpers = "\n".join([
        _extract(r"^\s*const ESC = .*?;$", src),
        _extract(r"^\s*const esc = .*?;$", src),
        _extract(r"^\s*class TrustedHtml .*?$", src),
        _extract(r"^\s*const trusted = .*?;$", src),
        _extract(r"^\s*const asHtml = .*?;$", src),
        _extract(r"^\s*function step\(.*?^\s*\}$", src),
        _extract(r"^\s*const pills = .*?;$", src),
    ])
    script = helpers + """
const payload = %s;
process.stdout.write(JSON.stringify({
  userText: step("1. Lo que escribió el usuario", payload),
  llmOutput: step("4. Lo que respondió el chatbot", payload, "safe"),
  provider: step(`3. Lo que recibió el chatbot (${payload}, 0 turno(s) previos)`, "x"),
  fakeMarker: step("x", { html: payload }),
  pills: step("Servicios", pills(["Tienda", payload])),
}));
""" % json.dumps(PAYLOAD)
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30)
    res = json.loads(out.stdout)

    escaped = "&lt;div&gt;&lt;img src=x onerror=1&gt;"
    for key in ("userText", "llmOutput", "provider", "pills"):
        assert "<img" not in res[key], key
        assert escaped in res[key], key
    assert res["userText"] == f'<div class="audit-step "><h4>1. Lo que escribió el usuario</h4><pre>{escaped}</pre></div>'
    # Un objeto que imita el marcador (p. ej. llegado por JSON) no es HTML confiable.
    assert "<img" not in res["fakeMarker"]
    # El HTML propio de las pills se sigue insertando sin escapar.
    assert '<div class="pill-list"><span class="pill ">Tienda</span>' in res["pills"]
