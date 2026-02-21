"""
CI/CD pipeline validation tests.

Pure file-parsing tests that read the GitHub Actions workflow YAML files
as plain text and verify triggers, job structure, security practices,
and deployment configuration. No YAML parsing library required.
No Docker daemon or application imports needed.
"""

import pathlib
import re

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
CI_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
DEPLOY_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "deploy.yml"


@pytest.fixture(scope="module")
def ci_content():
    """Read the CI workflow file once for all tests in this module."""
    assert CI_WORKFLOW.exists(), f"CI workflow not found at {CI_WORKFLOW}"
    return CI_WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def deploy_content():
    """Read the deploy workflow file once for all tests in this module."""
    assert DEPLOY_WORKFLOW.exists(), f"Deploy workflow not found at {DEPLOY_WORKFLOW}"
    return DEPLOY_WORKFLOW.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# CI Workflow tests (7)
# ---------------------------------------------------------------------------


class TestCIWorkflow:
    """Verify the structure and configuration of the CI workflow."""

    def test_ci_triggers_on_push_to_master(self, ci_content):
        """The CI workflow must run on push events to the master branch
        so every merge is validated automatically."""
        assert "push:" in ci_content, "CI must trigger on push"
        assert re.search(r"branches:\s*\[.*master.*\]", ci_content), (
            "CI push trigger must include the master branch"
        )

    def test_ci_triggers_on_pull_request_to_master(self, ci_content):
        """The CI workflow must run on pull_request events targeting
        master so PRs are validated before merge."""
        assert "pull_request:" in ci_content, "CI must trigger on pull_request"
        # Verify master is in the branches list after pull_request
        pr_section = ci_content[ci_content.index("pull_request:"):]
        assert re.search(r"branches:\s*\[.*master.*\]", pr_section), (
            "CI pull_request trigger must include the master branch"
        )

    def test_all_required_jobs_exist(self, ci_content):
        """The CI workflow must define all five required jobs:
        backend-lint, backend-test, sast, frontend-test, quality-gate."""
        required_jobs = [
            "backend-lint",
            "backend-test",
            "sast",
            "frontend-test",
            "quality-gate",
        ]
        for job in required_jobs:
            assert re.search(rf"^\s+{re.escape(job)}:", ci_content, re.MULTILINE), (
                f"Required job '{job}' not found in CI workflow"
            )

    def test_quality_gate_depends_on_all_jobs(self, ci_content):
        """The quality-gate job must depend on all other CI jobs so it
        only passes when every check succeeds."""
        # Find the needs line for quality-gate
        qg_section_match = re.search(
            r"quality-gate:.*?needs:\s*\[([^\]]+)\]",
            ci_content,
            re.DOTALL,
        )
        assert qg_section_match, "quality-gate must have a 'needs' field"
        needs_value = qg_section_match.group(1)
        expected_deps = ["backend-lint", "backend-test", "sast", "frontend-test"]
        for dep in expected_deps:
            assert dep in needs_value, (
                f"quality-gate must depend on '{dep}'; found needs: [{needs_value}]"
            )

    def test_python_311_used(self, ci_content):
        """The CI workflow must use Python 3.11 for backend jobs."""
        assert re.search(r"python-version:\s*[\"']?3\.11[\"']?", ci_content), (
            "CI workflow must specify python-version: 3.11"
        )

    def test_node_20_used(self, ci_content):
        """The CI workflow must use Node.js 20 for frontend jobs."""
        assert re.search(r"node-version:\s*[\"']?20[\"']?", ci_content), (
            "CI workflow must specify node-version: 20"
        )

    def test_uses_checkout_v4(self, ci_content):
        """The CI workflow must use actions/checkout@v4 for reliable
        and up-to-date repository checkout."""
        assert "actions/checkout@v4" in ci_content, (
            "CI workflow must use actions/checkout@v4"
        )


# ---------------------------------------------------------------------------
# Deploy Workflow tests (7)
# ---------------------------------------------------------------------------


class TestDeployWorkflow:
    """Verify the structure and configuration of the deploy workflow."""

    def test_deploy_triggers_on_push_to_master(self, deploy_content):
        """The deploy workflow must trigger on push to master so
        successful merges are automatically deployed."""
        assert "push:" in deploy_content, "Deploy must trigger on push"
        assert re.search(r"branches:\s*\[.*master.*\]", deploy_content), (
            "Deploy push trigger must include the master branch"
        )

    def test_deploy_triggers_on_workflow_dispatch(self, deploy_content):
        """The deploy workflow must support manual triggering via
        workflow_dispatch for ad-hoc deployments."""
        assert "workflow_dispatch" in deploy_content, (
            "Deploy workflow must trigger on workflow_dispatch"
        )

    def test_has_both_deploy_jobs(self, deploy_content):
        """The deploy workflow must define deploy-infrastructure and
        build-and-deploy jobs."""
        assert re.search(r"^\s+deploy-infrastructure:", deploy_content, re.MULTILINE), (
            "deploy-infrastructure job not found"
        )
        assert re.search(r"^\s+build-and-deploy:", deploy_content, re.MULTILINE), (
            "build-and-deploy job not found"
        )

    def test_build_depends_on_infrastructure(self, deploy_content):
        """build-and-deploy must depend on deploy-infrastructure so
        infrastructure is provisioned before the app is deployed."""
        bd_section_match = re.search(
            r"build-and-deploy:.*?needs:\s*(\S+)",
            deploy_content,
            re.DOTALL,
        )
        assert bd_section_match, "build-and-deploy must have a 'needs' field"
        needs_value = bd_section_match.group(1)
        assert "deploy-infrastructure" in needs_value, (
            f"build-and-deploy must depend on deploy-infrastructure; "
            f"found needs: {needs_value}"
        )

    def test_references_azure_credentials_secret(self, deploy_content):
        """The deploy workflow must reference the AZURE_CREDENTIALS
        secret for authenticating with Azure."""
        assert "secrets.AZURE_CREDENTIALS" in deploy_content, (
            "Deploy workflow must reference secrets.AZURE_CREDENTIALS"
        )

    def test_includes_smoke_test_step(self, deploy_content):
        """The deploy workflow must include a smoke test step to verify
        the deployment is healthy before promoting traffic."""
        content_lower = deploy_content.lower()
        has_smoke = "smoke" in content_lower
        has_health = "health" in content_lower
        assert has_smoke or has_health, (
            "Deploy workflow must include a smoke test or health check step"
        )

    def test_includes_traffic_promotion_step(self, deploy_content):
        """The deploy workflow must include a traffic promotion step
        to shift production traffic to the new revision."""
        assert "ingress traffic" in deploy_content, (
            "Deploy workflow must include a traffic promotion step "
            "using 'ingress traffic' command"
        )


# ---------------------------------------------------------------------------
# Security tests (3)
# ---------------------------------------------------------------------------


class TestCICDSecurity:
    """Verify security best practices across CI/CD workflows."""

    def test_deployment_uses_incremental_mode(self, deploy_content):
        """Infrastructure deployment must use Incremental mode (not
        Complete) to avoid accidentally deleting existing resources."""
        assert "--mode Incremental" in deploy_content, (
            "Deployment must use '--mode Incremental' (not Complete)"
        )
        assert "--mode Complete" not in deploy_content, (
            "Deployment must NOT use '--mode Complete'; use Incremental instead"
        )

    def test_images_tagged_with_sha(self, deploy_content):
        """Docker images must be tagged with the git SHA to ensure
        every deployment is traceable to a specific commit."""
        assert "github.sha" in deploy_content, (
            "Docker images must be tagged with github.sha for traceability"
        )

    def test_no_hardcoded_secrets_in_workflows(self, ci_content, deploy_content):
        """Workflow files must not contain hardcoded secret values such
        as API keys, passwords, or tokens. Secrets must be referenced
        via GitHub Actions secrets context only."""
        secret_patterns = [
            r"password\s*[:=]\s*[\"'][^$\s]",   # password with a literal value (not a ${{ }} reference)
            r"api_key\s*[:=]\s*[\"'][^$\s]",     # api_key with a literal value
            r"token\s*[:=]\s*[\"'][^$\s]",        # token with a literal value
            r"AKIA[0-9A-Z]{16}",                  # AWS access key pattern
            r"sk-[a-zA-Z0-9]{20,}",              # OpenAI-style API key pattern
        ]
        for name, content in [("ci.yml", ci_content), ("deploy.yml", deploy_content)]:
            for i, line in enumerate(content.splitlines()):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                for pattern in secret_patterns:
                    if re.search(pattern, stripped, re.IGNORECASE):
                        pytest.fail(
                            f"Possible hardcoded secret in {name} on line {i + 1}: "
                            f"{stripped}"
                        )
