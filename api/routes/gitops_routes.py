# api/routes/gitops_routes.py
# API endpoints для GitOps PR Bot

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from gitops.config import settings
from gitops.storage import GitOpsPRStore
from gitops.pr_bot import GitOpsPRBot
from policy.storage import PolicyStore
from db.base import get_db
from db.repository import PolicyRepository

router = APIRouter(prefix="/api/gitops", tags=["gitops"])

# Global stores
_policy_store: PolicyStore = None
_pr_store: GitOpsPRStore = None


def init_stores(policy_store: PolicyStore, pr_store: GitOpsPRStore):
    """Инициализирует хранилища для роутера."""
    global _policy_store, _pr_store
    _policy_store = policy_store
    _pr_store = pr_store


@router.get("/config")
async def get_config():
    """Возвращает текущую конфигурацию GitOps (без секретов)."""
    return {
        "enabled": settings.enabled,
        "provider": settings.provider,
        "repo": f"{settings.repo_owner}/{settings.repo_name}",
        "base_branch": settings.base_branch,
        "policies_path": settings.policies_path,
    }


@router.post("/sync")
async def sync_policies():
    """Синхронизирует все approved policies в GitOps репозиторий."""
    if not settings.enabled:
        raise HTTPException(status_code=400, detail="GitOps is not enabled")

    if not _policy_store or not _pr_store:
        raise HTTPException(status_code=500, detail="Stores not initialized")

    # Получаем все approved policies
    approved_policies = _policy_store.list_policies(status="approved")

    if not approved_policies:
        return {"status": "no_policies", "message": "No approved policies to sync"}

    bot = GitOpsPRBot(settings, _pr_store)
    results = []

    for policy_dict in approved_policies:
        # Конвертируем в PolicySuggestion
        from policy.generator import PolicySuggestion

        policy = PolicySuggestion(
            policy_id=policy_dict["policy_id"],
            yaml_dict=policy_dict["yaml_spec"],
            reason=policy_dict["reason"],
            risk_score=policy_dict["risk_score"],
            severity=policy_dict["severity"],
            auto_apply_safe=policy_dict["auto_apply_safe"],
            source=policy_dict["source"],
            destination=policy_dict["destination"],
        )

        try:
            result = bot.process_policy(policy)
            results.append({"policy_id": policy.policy_id, **result})
        except Exception as e:
            results.append({"policy_id": policy.policy_id, "status": "error", "error": str(e)})

    return {"status": "completed", "results": results}


@router.get("/prs")
async def list_prs(status: str = None):
    """Возвращает список созданных Pull Requests.

    Query params:
        status: фильтр по статусу ('open', 'merged', 'closed')
    """
    if not _pr_store:
        raise HTTPException(status_code=500, detail="PR store not initialized")

    prs = _pr_store.list_prs(status=status)
    return {"prs": prs, "count": len(prs)}


@router.get("/prs/{pr_id}/status")
async def get_pr_status(pr_id: int):
    """Получает текущий статус Pull Request."""
    if not _pr_store:
        raise HTTPException(status_code=500, detail="PR store not initialized")

    prs = _pr_store.list_prs()
    pr = next((p for p in prs if p["pr_id"] == pr_id), None)

    if not pr:
        raise HTTPException(status_code=404, detail=f"PR {pr_id} not found")

    return pr


@router.post("/sync-statuses")
async def sync_pr_statuses():
    """Синхронизирует статусы открытых PRs с GitHub/GitLab."""
    if not settings.enabled:
        raise HTTPException(status_code=400, detail="GitOps is not enabled")

    if not _pr_store:
        raise HTTPException(status_code=500, detail="PR store not initialized")

    bot = GitOpsPRBot(settings, _pr_store)
    updated = bot.sync_pr_statuses()

    return {"status": "completed", "updated": updated, "count": len(updated)}


@router.get("/policies/async")
async def list_approved_policies_async(
    db: AsyncSession = Depends(get_db),
):
    """Async endpoint — list approved policies ready for GitOps sync."""
    repo = PolicyRepository(db)
    policies = await repo.list_all("default", status="approved")
    return {"policies": policies, "count": len(policies)}
