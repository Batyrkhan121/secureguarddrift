# gitops/github_client.py
# GitHub API client для создания Pull Requests

import requests
from gitops.base_client import BaseGitOpsClient, PRInfo, CommitInfo


class GitHubClient(BaseGitOpsClient):
    """GitHub API client."""

    def _headers(self) -> dict:
        """Возвращает HTTP headers для API запросов."""
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def get_default_branch_sha(self, branch_name: str) -> str:
        """Получает SHA последнего коммита в ветке."""
        url = f"{self.api_url}/repos/{self.repo_owner}/{self.repo_name}/git/refs/heads/{branch_name}"
        response = requests.get(url, headers=self._headers(), timeout=30)
        response.raise_for_status()
        return response.json()["object"]["sha"]

    def create_branch(self, branch_name: str, base_branch: str = "main") -> bool:
        """Создает новую ветку от base_branch."""
        # Получаем SHA базовой ветки
        base_sha = self.get_default_branch_sha(base_branch)

        # Создаем новую ветку
        url = f"{self.api_url}/repos/{self.repo_owner}/{self.repo_name}/git/refs"
        data = {
            "ref": f"refs/heads/{branch_name}",
            "sha": base_sha,
        }
        response = requests.post(url, json=data, headers=self._headers(), timeout=30)

        if response.status_code == 201:
            return True
        elif response.status_code == 422:  # Branch already exists
            return True
        else:
            response.raise_for_status()
            return False

    def commit_file(
        self,
        branch_name: str,
        file_path: str,
        file_content: str,
        commit_message: str,
    ) -> CommitInfo:
        """Коммитит файл в указанную ветку."""
        import base64

        url = f"{self.api_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"

        # Проверяем существует ли файл
        response = requests.get(url, headers=self._headers(), params={"ref": branch_name}, timeout=30)

        sha = None
        if response.status_code == 200:
            sha = response.json()["sha"]

        # Создаем или обновляем файл
        content_b64 = base64.b64encode(file_content.encode()).decode()
        data = {
            "message": commit_message,
            "content": content_b64,
            "branch": branch_name,
        }
        if sha:
            data["sha"] = sha

        response = requests.put(url, json=data, headers=self._headers(), timeout=30)
        response.raise_for_status()

        result = response.json()
        return CommitInfo(sha=result["commit"]["sha"], message=commit_message)

    def create_pull_request(
        self,
        branch_name: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> PRInfo:
        """Создает Pull Request."""
        url = f"{self.api_url}/repos/{self.repo_owner}/{self.repo_name}/pulls"
        data = {
            "title": title,
            "body": body,
            "head": branch_name,
            "base": base_branch,
        }
        response = requests.post(url, json=data, headers=self._headers(), timeout=30)
        response.raise_for_status()

        result = response.json()
        return PRInfo(
            pr_number=result["number"],
            pr_url=result["html_url"],
            branch_name=branch_name,
            status="open",
        )

    def get_pr_status(self, pr_number: int) -> str:
        """Получает статус Pull Request."""
        url = f"{self.api_url}/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}"
        response = requests.get(url, headers=self._headers(), timeout=30)
        response.raise_for_status()

        result = response.json()
        state = result["state"]  # "open" или "closed"

        if state == "closed" and result.get("merged"):
            return "merged"
        return state
