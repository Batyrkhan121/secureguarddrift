# gitops/pr_bot.py
# Основная логика GitOps PR Bot

from gitops.config import GitOpsSettings
from gitops.github_client import GitHubClient
from gitops.gitlab_client import GitLabClient
from gitops.base_client import BaseGitOpsClient
from gitops.storage import GitOpsPRStore
from policy.renderer import to_yaml
from policy.generator import PolicySuggestion


class GitOpsPRBot:
    """GitOps PR Bot для автоматического создания Pull Requests."""

    def __init__(self, settings: GitOpsSettings, pr_store: GitOpsPRStore):
        self.settings = settings
        self.pr_store = pr_store
        self.client: BaseGitOpsClient = self._create_client()

    def _create_client(self) -> BaseGitOpsClient:
        """Создает клиент для GitHub или GitLab."""
        if self.settings.provider == "github":
            return GitHubClient(
                token=self.settings.token,
                api_url=self.settings.api_url,
                repo_owner=self.settings.repo_owner,
                repo_name=self.settings.repo_name,
            )
        elif self.settings.provider == "gitlab":
            return GitLabClient(
                token=self.settings.token,
                api_url=self.settings.api_url,
                repo_owner=self.settings.repo_owner,
                repo_name=self.settings.repo_name,
            )
        else:
            raise ValueError(f"Unsupported provider: {self.settings.provider}")

    def process_policy(self, policy: PolicySuggestion) -> dict:
        """Создает PR для одной policy.

        Returns:
            dict с информацией о созданном PR
        """
        if not self.settings.enabled:
            return {"status": "skipped", "reason": "GitOps not enabled"}

        # Проверяем, есть ли уже PR для этой policy
        existing_pr = self.pr_store.get_pr_by_policy(policy.policy_id)
        if existing_pr:
            return {
                "status": "exists",
                "pr_url": existing_pr["pr_url"],
                "pr_number": existing_pr["pr_number"],
            }

        # Генерируем имена
        branch_name = f"{self.settings.branch_prefix}{policy.policy_id}"
        file_path = f"{self.settings.policies_path}/{policy.policy_id}.yaml"

        # Создаем ветку
        self.client.create_branch(branch_name, self.settings.base_branch)

        # Генерируем YAML
        yaml_content = to_yaml(policy)

        # Коммитим файл
        commit_msg = f"Add NetworkPolicy: {policy.policy_id}"
        self.client.commit_file(branch_name, file_path, yaml_content, commit_msg)

        # Создаем PR
        pr_title = self.settings.pr_title_template.format(policy_id=policy.policy_id)
        pr_body = self.settings.pr_body_template.format(
            policy_id=policy.policy_id,
            severity=policy.severity,
            risk_score=policy.risk_score,
            reason=policy.reason,
            source=policy.source,
            destination=policy.destination,
        )

        pr_info = self.client.create_pull_request(
            branch_name, self.settings.base_branch, pr_title, pr_body
        )

        # Сохраняем в БД
        self.pr_store.save_pr(
            policy_id=policy.policy_id,
            branch_name=pr_info.branch_name,
            pr_number=pr_info.pr_number,
            pr_url=pr_info.pr_url,
            provider=self.settings.provider,
        )

        return {
            "status": "created",
            "pr_url": pr_info.pr_url,
            "pr_number": pr_info.pr_number,
            "branch_name": branch_name,
        }

    def sync_pr_statuses(self) -> list[dict]:
        """Синхронизирует статусы открытых PRs с GitHub/GitLab.

        Returns:
            список обновленных PRs
        """
        open_prs = self.pr_store.list_prs(status="open")
        updated = []

        for pr in open_prs:
            try:
                new_status = self.client.get_pr_status(pr["pr_number"])
                if new_status != pr["status"]:
                    self.pr_store.update_pr_status(pr["pr_id"], new_status)
                    updated.append({"pr_id": pr["pr_id"], "old_status": pr["status"], "new_status": new_status})
            except Exception as e:
                print(f"Failed to sync PR {pr['pr_number']}: {e}")

        return updated
