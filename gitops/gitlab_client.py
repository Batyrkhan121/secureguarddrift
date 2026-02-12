# gitops/gitlab_client.py
# GitLab API client для создания Merge Requests

import requests
from gitops.base_client import BaseGitOpsClient, PRInfo, CommitInfo


class GitLabClient(BaseGitOpsClient):
    """GitLab API client."""

    def _headers(self) -> dict:
        """Возвращает HTTP headers для API запросов."""
        return {
            "PRIVATE-TOKEN": self.token,
            "Content-Type": "application/json",
        }

    def _project_id(self) -> str:
        """Возвращает project ID в формате namespace/repo."""
        return f"{self.repo_owner}/{self.repo_name}"

    def get_default_branch_sha(self, branch_name: str) -> str:
        """Получает SHA последнего коммита в ветке."""
        project_id = requests.utils.quote(self._project_id(), safe="")
        url = f"{self.api_url}/projects/{project_id}/repository/branches/{branch_name}"
        response = requests.get(url, headers=self._headers(), timeout=30)
        response.raise_for_status()
        return response.json()["commit"]["id"]

    def create_branch(self, branch_name: str, base_branch: str = "main") -> bool:
        """Создает новую ветку от base_branch."""
        project_id = requests.utils.quote(self._project_id(), safe="")
        url = f"{self.api_url}/projects/{project_id}/repository/branches"
        data = {
            "branch": branch_name,
            "ref": base_branch,
        }
        response = requests.post(url, json=data, headers=self._headers(), timeout=30)

        if response.status_code in (201, 200):
            return True
        elif response.status_code == 400:  # Branch already exists
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
        project_id = requests.utils.quote(self._project_id(), safe="")
        url = f"{self.api_url}/projects/{project_id}/repository/commits"

        data = {
            "branch": branch_name,
            "commit_message": commit_message,
            "actions": [
                {
                    "action": "create",
                    "file_path": file_path,
                    "content": file_content,
                }
            ],
        }
        response = requests.post(url, json=data, headers=self._headers(), timeout=30)

        # Если файл уже существует, обновляем
        if response.status_code == 400:
            data["actions"][0]["action"] = "update"
            response = requests.post(url, json=data, headers=self._headers(), timeout=30)

        response.raise_for_status()
        result = response.json()
        return CommitInfo(sha=result["id"], message=commit_message)

    def create_pull_request(
        self,
        branch_name: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> PRInfo:
        """Создает Merge Request."""
        project_id = requests.utils.quote(self._project_id(), safe="")
        url = f"{self.api_url}/projects/{project_id}/merge_requests"
        data = {
            "source_branch": branch_name,
            "target_branch": base_branch,
            "title": title,
            "description": body,
        }
        response = requests.post(url, json=data, headers=self._headers(), timeout=30)
        response.raise_for_status()

        result = response.json()
        return PRInfo(
            pr_number=result["iid"],
            pr_url=result["web_url"],
            branch_name=branch_name,
            status="open",
        )

    def get_pr_status(self, pr_number: int) -> str:
        """Получает статус Merge Request."""
        project_id = requests.utils.quote(self._project_id(), safe="")
        url = f"{self.api_url}/projects/{project_id}/merge_requests/{pr_number}"
        response = requests.get(url, headers=self._headers(), timeout=30)
        response.raise_for_status()

        result = response.json()
        state = result["state"]  # "opened", "closed", "merged"

        if state == "opened":
            return "open"
        elif state == "merged":
            return "merged"
        return "closed"
