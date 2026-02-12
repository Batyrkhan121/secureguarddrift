# gitops/base_client.py
# Абстрактный базовый класс для GitOps клиентов

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PRInfo:
    """Информация о созданном Pull Request."""
    pr_number: int
    pr_url: str
    branch_name: str
    status: str = "open"


@dataclass
class CommitInfo:
    """Информация о коммите."""
    sha: str
    message: str


class BaseGitOpsClient(ABC):
    """Абстрактный базовый класс для работы с Git hosting providers."""

    def __init__(self, token: str, api_url: str, repo_owner: str, repo_name: str):
        """
        Args:
            token: API token для аутентификации
            api_url: Base URL для API (GitHub/GitLab)
            repo_owner: Владелец репозитория (GitHub) или namespace (GitLab)
            repo_name: Имя репозитория
        """
        self.token = token
        self.api_url = api_url
        self.repo_owner = repo_owner
        self.repo_name = repo_name

    @abstractmethod
    def create_branch(self, branch_name: str, base_branch: str = "main") -> bool:
        """Создает новую ветку от base_branch.

        Returns:
            True если ветка создана успешно
        """
        pass

    @abstractmethod
    def commit_file(
        self,
        branch_name: str,
        file_path: str,
        file_content: str,
        commit_message: str,
    ) -> CommitInfo:
        """Коммитит файл в указанную ветку.

        Returns:
            CommitInfo с информацией о коммите
        """
        pass

    @abstractmethod
    def create_pull_request(
        self,
        branch_name: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> PRInfo:
        """Создает Pull Request.

        Returns:
            PRInfo с информацией о PR
        """
        pass

    @abstractmethod
    def get_pr_status(self, pr_number: int) -> str:
        """Получает статус Pull Request.

        Returns:
            Статус: "open", "closed", "merged"
        """
        pass

    @abstractmethod
    def get_default_branch_sha(self, branch_name: str) -> str:
        """Получает SHA последнего коммита в ветке.

        Returns:
            SHA коммита
        """
        pass
