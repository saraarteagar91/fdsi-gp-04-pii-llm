"""
Prueba de regresión del Lab. 05 (hallazgo F-01): la página y la API deben
responder con los encabezados de seguridad que OWASP ZAP reportó ausentes
(CSP, anti-clickjacking, nosniff, Referrer-Policy y Permissions-Policy).
"""
import pytest

EXPECTED = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
}


@pytest.mark.parametrize("path", ["/", "/index.html", "/app.js", "/health", "/ruta-que-no-existe"])
def test_security_headers_present(anon, path):
    resp = anon.get(path)
    for name, value in EXPECTED.items():
        assert resp.headers.get(name) == value, f"{name} ausente en {path}"
    assert "camera=()" in resp.headers.get("permissions-policy", "")
    csp = resp.headers.get("content-security-policy", "")
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp


def test_csp_does_not_allow_inline_scripts(anon):
    csp = anon.get("/").headers["content-security-policy"]
    script_src = next(d for d in csp.split(";") if d.strip().startswith("script-src"))
    assert "unsafe-inline" not in script_src
    assert "unsafe-eval" not in script_src


def test_swagger_docs_still_work(anon):
    resp = anon.get("/docs")
    assert resp.status_code == 200
    assert "content-security-policy" not in resp.headers
    assert resp.headers.get("x-content-type-options") == "nosniff"
