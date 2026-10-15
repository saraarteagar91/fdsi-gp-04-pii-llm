"""
Centro de seguridad (SOLO rol admin): últimas entradas de cada log,
estado de los servicios, resultados de la evaluación, clientes de prueba
e información de los modelos entrenados.

Nota: exponer el log crudo por HTTP es en sí mismo sensible; por eso todo
este router exige el rol de administrador.
"""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app import clients
from app.config import settings
from app.logging_config import read_recent_logs
from app.security import require_admin
from app.services.orders import demo_customers

router = APIRouter(prefix="/api/admin", tags=["seguridad"], dependencies=[Depends(require_admin)])


@router.get("/logs/{scenario}")
def recent_logs(scenario: str, limit: int = 15) -> list[dict]:
    if scenario not in ("secure", "unsecure"):
        raise HTTPException(status_code=404, detail="Escenario desconocido")
    return read_recent_logs(scenario, limit=min(limit, 100))


@router.get("/demo-data")
def demo_data() -> dict:
    return {"aviso": "Datos 100 % ficticios para el ambiente de pruebas.", "clientes": demo_customers()}


@router.get("/evaluation")
def evaluation() -> dict:
    path = Path(settings.data_dir) / "evaluation_summary.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Ejecuta python -m scripts.evaluate primero")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/evaluation.png")
def evaluation_chart() -> FileResponse:
    path = Path(settings.data_dir) / "evaluation_metrics.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sin gráfica todavía")
    return FileResponse(path, media_type="image/png")


@router.get("/services")
def services() -> dict:
    """Estado de los tres servicios externos (lo que cada uno declara
    tener: el guardián NO puede descifrar, la bóveda SÍ tiene la llave)."""
    return {s: clients.health(s) for s in ("guardian", "vault", "chatbot")}


@router.get("/bot-info")
def bot_info() -> dict:
    info = clients.get("chatbot", "/info")
    guardian_report = Path(settings.model_dir) / "guardian_training_report.json"
    if guardian_report.exists():
        g = json.loads(guardian_report.read_text(encoding="utf-8"))
        g.pop("historial", None)
        info["guardian"] = g
    return info
