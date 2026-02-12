# tests/test_week7_gitops.py
# Тесты для GitOps PR Bot (Неделя 7)

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from gitops.config import GitOpsSettings
from gitops.github_client import GitHubClient
from gitops.gitlab_client import GitLabClient
from gitops.storage import GitOpsPRStore
from gitops.pr_bot import GitOpsPRBot
from policy.generator import PolicySuggestion


class TestGitOpsConfig(unittest.TestCase):
    """Тесты конфигурации GitOps."""

    def test_config_defaults(self):
        """Конфигурация имеет правильные defaults."""
        settings = GitOpsSettings()
        self.assertEqual(settings.provider, "github")
        self.assertEqual(settings.base_branch, "main")
        self.assertFalse(settings.enabled)


class TestGitHubClient(unittest.TestCase):
    """Тесты GitHub API client."""

    def setUp(self):
        self.client = GitHubClient(
            token="test_token",
            api_url="https://api.github.com",
            repo_owner="test_org",
            repo_name="test_repo",
        )

    @patch("gitops.github_client.requests.get")
    def test_get_default_branch_sha(self, mock_get):
        """Получение SHA ветки работает."""
        mock_get.return_value.json.return_value = {"object": {"sha": "abc123"}}
        mock_get.return_value.raise_for_status = Mock()

        sha = self.client.get_default_branch_sha("main")

        self.assertEqual(sha, "abc123")
        mock_get.assert_called_once()

    @patch("gitops.github_client.requests.post")
    @patch("gitops.github_client.requests.get")
    def test_create_branch(self, mock_get, mock_post):
        """Создание ветки работает."""
        mock_get.return_value.json.return_value = {"object": {"sha": "abc123"}}
        mock_get.return_value.raise_for_status = Mock()
        mock_post.return_value.status_code = 201
        mock_post.return_value.raise_for_status = Mock()

        result = self.client.create_branch("test-branch", "main")

        self.assertTrue(result)
        mock_post.assert_called_once()

    @patch("gitops.github_client.requests.put")
    @patch("gitops.github_client.requests.get")
    def test_commit_file(self, mock_get, mock_put):
        """Коммит файла работает."""
        mock_get.return_value.status_code = 404  # File doesn't exist
        mock_put.return_value.json.return_value = {
            "commit": {"sha": "def456"},
        }
        mock_put.return_value.raise_for_status = Mock()

        commit_info = self.client.commit_file(
            "test-branch",
            "test.yaml",
            "content",
            "test commit",
        )

        self.assertEqual(commit_info.sha, "def456")
        mock_put.assert_called_once()

    @patch("gitops.github_client.requests.post")
    def test_create_pull_request(self, mock_post):
        """Создание PR работает."""
        mock_post.return_value.json.return_value = {
            "number": 42,
            "html_url": "https://github.com/test/test/pull/42",
        }
        mock_post.return_value.raise_for_status = Mock()

        pr_info = self.client.create_pull_request(
            "test-branch",
            "main",
            "Test PR",
            "Test body",
        )

        self.assertEqual(pr_info.pr_number, 42)
        self.assertIn("github.com", pr_info.pr_url)

    @patch("gitops.github_client.requests.get")
    def test_get_pr_status(self, mock_get):
        """Получение статуса PR работает."""
        mock_get.return_value.json.return_value = {
            "state": "open",
            "merged": False,
        }
        mock_get.return_value.raise_for_status = Mock()

        status = self.client.get_pr_status(42)

        self.assertEqual(status, "open")


class TestGitLabClient(unittest.TestCase):
    """Тесты GitLab API client."""

    def setUp(self):
        self.client = GitLabClient(
            token="test_token",
            api_url="https://gitlab.com/api/v4",
            repo_owner="test_org",
            repo_name="test_repo",
        )

    @patch("gitops.gitlab_client.requests.get")
    def test_get_default_branch_sha(self, mock_get):
        """Получение SHA ветки работает."""
        mock_get.return_value.json.return_value = {
            "commit": {"id": "xyz789"}
        }
        mock_get.return_value.raise_for_status = Mock()

        sha = self.client.get_default_branch_sha("main")

        self.assertEqual(sha, "xyz789")


class TestGitOpsPRStore(unittest.TestCase):
    """Тесты хранилища PRs."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.store = GitOpsPRStore(self.temp_db.name)

    def tearDown(self):
        os.unlink(self.temp_db.name)

    def test_save_and_get_pr(self):
        """Сохранение и получение PR работает."""
        pr_id = self.store.save_pr(
            policy_id="test-policy-1",
            branch_name="test-branch",
            pr_number=42,
            pr_url="https://github.com/test/test/pull/42",
            provider="github",
        )

        self.assertIsNotNone(pr_id)

        pr = self.store.get_pr_by_policy("test-policy-1")
        self.assertEqual(pr["pr_number"], 42)
        self.assertEqual(pr["policy_id"], "test-policy-1")

    def test_list_prs(self):
        """Получение списка PRs работает."""
        self.store.save_pr("policy-1", "branch-1", 1, "url1")
        self.store.save_pr("policy-2", "branch-2", 2, "url2")

        prs = self.store.list_prs()
        self.assertEqual(len(prs), 2)

    def test_update_pr_status(self):
        """Обновление статуса PR работает."""
        pr_id = self.store.save_pr("policy-1", "branch-1", 1, "url1")

        success = self.store.update_pr_status(pr_id, "merged")
        self.assertTrue(success)

        pr = self.store.get_pr_by_policy("policy-1")
        self.assertEqual(pr["status"], "merged")


class TestGitOpsPRBot(unittest.TestCase):
    """Тесты GitOps PR Bot."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.pr_store = GitOpsPRStore(self.temp_db.name)

        self.settings = GitOpsSettings(
            enabled=True,
            provider="github",
            token="test_token",
            repo_owner="test_org",
            repo_name="test_repo",
        )

    def tearDown(self):
        os.unlink(self.temp_db.name)

    @patch("gitops.pr_bot.GitHubClient")
    def test_process_policy_creates_pr(self, mock_client_class):
        """process_policy создает PR."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_client.create_branch.return_value = True
        mock_client.commit_file.return_value = Mock(sha="abc123", message="test")
        mock_client.create_pull_request.return_value = Mock(
            pr_number=42,
            pr_url="https://github.com/test/test/pull/42",
            branch_name="test-branch",
            status="open",
        )

        bot = GitOpsPRBot(self.settings, self.pr_store)
        bot.client = mock_client

        policy = PolicySuggestion(
            policy_id="test-policy",
            yaml_dict={"kind": "NetworkPolicy"},
            reason="Test",
            risk_score=85,
            severity="critical",
            source="svc1",
            destination="svc2",
        )

        result = bot.process_policy(policy)

        self.assertEqual(result["status"], "created")
        self.assertEqual(result["pr_number"], 42)


if __name__ == "__main__":
    unittest.main()
