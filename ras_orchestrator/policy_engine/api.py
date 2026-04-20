"""
REST API для управления политиками.
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from pathlib import Path

from .core import PolicyEngineCore, get_global_engine
from .schemas import PolicyValidator
from .integration import get_integration

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/policies", tags=["policies"])

# Глобальные экземпляры
engine = get_global_engine(watch=False)
validator = PolicyValidator()


# Модели запросов/ответов
class PolicyCreate(BaseModel):
    name: str
    version: str = "1.0"
    description: str = ""
    enabled: bool = True
    priority: int = 0
    tags: List[str] = []
    conditions: Dict[str, Any] = Field(..., description="Условия в формате DSL")
    actions: Dict[str, Any] = Field(..., description="Действия политики")
    metadata: Dict[str, Any] = {}


class PolicyUpdate(BaseModel):
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    conditions: Optional[Dict[str, Any]] = None
    actions: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class PolicyResponse(BaseModel):
    name: str
    version: str
    description: str
    enabled: bool
    priority: int
    tags: List[str]
    conditions: Dict[str, Any]
    actions: Dict[str, Any]
    metadata: Dict[str, Any]


class EvaluateRequest(BaseModel):
    policy_type: str = Field(..., description="Тип политики (interrupt, mode, etc.)")
    context: Dict[str, Any] = Field(..., description="Контекст для оценки")


class EvaluateResponse(BaseModel):
    matched: bool
    policies: List[Dict[str, Any]]
    actions: Optional[Dict[str, Any]] = None


@router.get("/types")
async def list_policy_types():
    """Возвращает список поддерживаемых типов политик."""
    return {
        "types": [
            "interrupt",
            "mode",
            "action",
            "tool_access",
            "human_escalation",
            "routing",
            "salience_weights",
            "salience_anomaly",
            "mode_hysteresis",
            "checkpoint",
            "task_priority",
        ]
    }


@router.get("/files")
async def list_policy_files():
    """Возвращает список файлов политик."""
    policy_dir = Path(__file__).parent / "policies"
    files = []
    for yaml_file in policy_dir.glob("*.yaml"):
        files.append(yaml_file.name)
    for yaml_file in policy_dir.glob("*.yml"):
        files.append(yaml_file.name)
    return {"files": files}


@router.get("/file/{filename}")
async def get_policy_file(filename: str):
    """Возвращает содержимое файла политик."""
    policy_dir = Path(__file__).parent / "policies"
    file_path = policy_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    import yaml
    with open(file_path, "r", encoding="utf-8") as f:
        content = yaml.safe_load(f)
    return content


@router.post("/file/{filename}/validate")
async def validate_policy_file(filename: str, policy_type: str = Query(None)):
    """Валидирует файл политик."""
    policy_dir = Path(__file__).parent / "policies"
    file_path = policy_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    errors = validator.validate_file(file_path, policy_type)
    return {"valid": len(errors) == 0, "errors": errors}


@router.post("/evaluate")
async def evaluate_policy(request: EvaluateRequest):
    """Оценивает политики для заданного контекста."""
    matched = engine.evaluate(request.policy_type, request.context)
    return EvaluateResponse(
        matched=len(matched) > 0,
        policies=matched,
        actions=matched[0].get("actions") if matched else None,
    )


@router.get("/{policy_type}/list")
async def list_policies(policy_type: str):
    """Возвращает список политик определённого типа."""
    # Загружаем политики из engine
    policies = engine.policies.get(policy_type, [])
    # Преобразуем в ответ
    result = []
    for policy in policies:
        result.append({
            "name": policy.name,
            "version": policy.version,
            "enabled": policy.enabled,
            "priority": policy.priority,
            "tags": policy.tags,
            "conditions": policy.conditions,
            "actions": policy.actions,
            "metadata": policy.metadata,
        })
    return {"policies": result}


@router.post("/{policy_type}/create")
async def create_policy(policy_type: str, policy: PolicyCreate):
    """Создаёт новую политику (пока только в памяти)."""
    # В реальности нужно сохранять в YAML файл
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.put("/{policy_type}/{policy_name}")
async def update_policy(policy_type: str, policy_name: str, update: PolicyUpdate):
    """Обновляет существующую политику."""
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.delete("/{policy_type}/{policy_name}")
async def delete_policy(policy_type: str, policy_name: str):
    """Удаляет политику."""
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/reload")
async def reload_policies():
    """Перезагружает политики из файлов (hot-reload)."""
    engine.reload_policies()
    return {"status": "reloaded", "message": "Policies reloaded from disk"}


@router.get("/integration/{component}/test")
async def test_integration(component: str, context: Dict[str, Any] = {}):
    """Тестирует интеграцию с компонентом."""
    integration = get_integration(component)
    if not integration:
        raise HTTPException(status_code=404, detail=f"Integration for {component} not found")
    # Простой тест: оцениваем политики типа component
    matched = integration.evaluate(component, context)
    return {
        "component": component,
        "matched_policies": len(matched),
        "policies": matched,
    }