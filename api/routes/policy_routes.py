# api/routes/policy_routes.py
# API эндпоинты для NetworkPolicy предложений

from fastapi import APIRouter, HTTPException, Response
from policy.storage import PolicyStore
from policy.renderer import to_yaml, to_yaml_bundle

router = APIRouter(prefix="/api/policies", tags=["policies"])

# Глобальное хранилище (будет инициализировано в server.py)
_store: PolicyStore = None


def init_store(store: PolicyStore):
    """Инициализирует хранилище для роутера."""
    global _store
    _store = store


def get_store() -> PolicyStore:
    """Возвращает хранилище."""
    if _store is None:
        raise HTTPException(status_code=500, detail="Policy store not initialized")
    return _store


@router.get("/")
async def list_policies(status: str = None):
    """Возвращает список предложенных NetworkPolicy.

    Query params:
        status: фильтр по статусу ('pending', 'approved', 'rejected')
    """
    store = get_store()
    policies = store.list_policies(status=status)

    # Убираем yaml_spec для списка (слишком большой)
    for p in policies:
        p["has_yaml"] = bool(p.get("yaml_spec"))
        del p["yaml_spec"]

    return {
        "policies": policies,
        "count": len(policies),
    }


@router.get("/{policy_id}")
async def get_policy(policy_id: str):
    """Возвращает детали одной policy."""
    store = get_store()
    policy = store.get_policy(policy_id)

    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    return policy


@router.get("/{policy_id}/yaml")
async def download_policy_yaml(policy_id: str):
    """Скачивает YAML одной policy для kubectl apply."""
    store = get_store()
    policy = store.get_policy(policy_id)

    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    # Генерируем YAML из yaml_spec
    from policy.generator import PolicySuggestion
    suggestion = PolicySuggestion(
        policy_id=policy["policy_id"],
        yaml_dict=policy["yaml_spec"],
        reason=policy["reason"],
        risk_score=policy["risk_score"],
        severity=policy["severity"],
        auto_apply_safe=policy["auto_apply_safe"],
        source=policy["source"],
        destination=policy["destination"],
    )

    yaml_content = to_yaml(suggestion)

    return Response(
        content=yaml_content,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{policy_id}.yaml"'},
    )


@router.get("/bundle/download")
async def download_policies_bundle(status: str = "pending"):
    """Скачивает все policies как один YAML файл с разделителями."""
    store = get_store()
    policies = store.list_policies(status=status)

    if not policies:
        raise HTTPException(status_code=404, detail="No policies found")

    # Конвертируем в PolicySuggestion для рендеринга
    from policy.generator import PolicySuggestion
    suggestions = []
    for p in policies:
        suggestions.append(PolicySuggestion(
            policy_id=p["policy_id"],
            yaml_dict=p["yaml_spec"],
            reason=p["reason"],
            risk_score=p["risk_score"],
            severity=p["severity"],
            auto_apply_safe=p["auto_apply_safe"],
            source=p["source"],
            destination=p["destination"],
        ))

    bundle_yaml = to_yaml_bundle(suggestions)

    return Response(
        content=bundle_yaml,
        media_type="application/x-yaml",
        headers={"Content-Disposition": 'attachment; filename="policies-bundle.yaml"'},
    )


@router.post("/{policy_id}/approve")
async def approve_policy(policy_id: str):
    """Помечает policy как одобренную."""
    store = get_store()
    success = store.update_status(policy_id, "approved")

    if not success:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    return {"status": "approved", "policy_id": policy_id}


@router.post("/{policy_id}/reject")
async def reject_policy(policy_id: str):
    """Помечает policy как отклоненную."""
    store = get_store()
    success = store.update_status(policy_id, "rejected")

    if not success:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    return {"status": "rejected", "policy_id": policy_id}
