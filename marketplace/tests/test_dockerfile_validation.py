"""
Dockerfile validation tests.

Pure file-parsing tests that read the Dockerfile as text and verify
its structure, security practices, and health/port configuration.
No Docker daemon or application imports required.
"""

import pathlib
import re

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCKERFILE = PROJECT_ROOT / "Dockerfile"


@pytest.fixture(scope="module")
def dockerfile_content():
    """Read the Dockerfile content once for all tests in this module."""
    assert DOCKERFILE.exists(), f"Dockerfile not found at {DOCKERFILE}"
    return DOCKERFILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def dockerfile_lines(dockerfile_content):
    """Return the Dockerfile split into individual lines."""
    return dockerfile_content.splitlines()


# ---------------------------------------------------------------------------
# Structure tests (7)
# ---------------------------------------------------------------------------


class TestDockerfileStructure:
    """Verify the multi-stage build structure of the Dockerfile."""

    def test_two_from_stages_exist(self, dockerfile_content):
        """The Dockerfile must have exactly two FROM instructions — one
        for node:20 (frontend build) and one for python:3.11 (backend)."""
        from_lines = [
            line for line in dockerfile_content.splitlines()
            if line.strip().upper().startswith("FROM")
        ]
        assert len(from_lines) == 2, f"Expected 2 FROM stages, found {len(from_lines)}: {from_lines}"
        combined = " ".join(from_lines).lower()
        assert "node:20" in combined, "First stage must use node:20"
        assert "python:3.11" in combined, "Second stage must use python:3.11"

    def test_frontend_stage_named_frontend_build(self, dockerfile_content):
        """The Node.js build stage must be named 'frontend-build' so the
        backend stage can COPY artifacts from it."""
        assert re.search(
            r"FROM\s+node:20.*\s+AS\s+frontend-build", dockerfile_content, re.IGNORECASE
        ), "Frontend stage must be named 'frontend-build'"

    def test_uses_npm_ci_not_npm_install(self, dockerfile_content):
        """npm ci must be used instead of npm install to guarantee
        deterministic, lockfile-based dependency installation."""
        assert "npm ci" in dockerfile_content, "Dockerfile should use 'npm ci'"
        # Ensure plain 'npm install' (without ci) is not present
        install_matches = re.findall(r"npm\s+install(?!\s*-)", dockerfile_content)
        assert len(install_matches) == 0, (
            "Dockerfile should NOT use 'npm install'; use 'npm ci' instead"
        )

    def test_pip_install_uses_no_cache_dir(self, dockerfile_content):
        """pip install must use --no-cache-dir to keep the image small."""
        assert "pip install --no-cache-dir" in dockerfile_content, (
            "pip install must include --no-cache-dir flag"
        )

    def test_frontend_dist_copied_to_static(self, dockerfile_content):
        """Frontend build artifacts must be copied from the frontend-build
        stage into the static/ directory of the backend stage."""
        assert "COPY --from=frontend-build /frontend/dist/ static/" in dockerfile_content, (
            "Frontend dist must be copied to static/ via "
            "'COPY --from=frontend-build /frontend/dist/ static/'"
        )

    def test_workdir_set_to_app(self, dockerfile_content):
        """WORKDIR must be set to /app in the backend stage."""
        # Match WORKDIR /app that is NOT /app/ or /app-something
        assert re.search(r"WORKDIR\s+/app\b", dockerfile_content), (
            "WORKDIR must be set to /app"
        )

    def test_labels_present(self, dockerfile_content):
        """The image must include maintainer and description labels for
        discoverability and documentation."""
        assert re.search(r'LABEL\s+maintainer=', dockerfile_content), (
            "LABEL maintainer must be present"
        )
        assert re.search(r'LABEL\s+description=', dockerfile_content), (
            "LABEL description must be present"
        )


# ---------------------------------------------------------------------------
# Security tests (4)
# ---------------------------------------------------------------------------


class TestDockerfileSecurity:
    """Verify security best practices in the Dockerfile."""

    def test_non_root_user_created(self, dockerfile_content):
        """A dedicated non-root user 'appuser' must be created so the
        container does not run processes as root."""
        assert re.search(r"adduser.*appuser", dockerfile_content), (
            "A non-root user 'appuser' must be created with adduser"
        )

    def test_user_directive_exists(self, dockerfile_content):
        """A USER directive must be present and set to 'appuser'."""
        assert re.search(r"^USER\s+appuser\s*$", dockerfile_content, re.MULTILINE), (
            "USER directive must be set to 'appuser'"
        )

    def test_user_directive_before_cmd(self, dockerfile_lines):
        """The USER directive must appear before CMD so the application
        runs as the non-root user, not as root."""
        user_index = None
        cmd_index = None
        for i, line in enumerate(dockerfile_lines):
            stripped = line.strip()
            if stripped.startswith("USER "):
                user_index = i
            if stripped.startswith("CMD "):
                cmd_index = i
        assert user_index is not None, "USER directive not found"
        assert cmd_index is not None, "CMD directive not found"
        assert user_index < cmd_index, (
            f"USER (line {user_index + 1}) must come before CMD (line {cmd_index + 1})"
        )

    def test_no_hardcoded_secrets(self, dockerfile_lines):
        """The Dockerfile must not contain hardcoded secrets such as
        password=, secret=, or api_key= with actual values."""
        secret_patterns = [r"password\s*=", r"secret\s*=", r"api_key\s*="]
        for i, line in enumerate(dockerfile_lines):
            stripped = line.strip()
            # Skip comment lines
            if stripped.startswith("#"):
                continue
            for pattern in secret_patterns:
                match = re.search(pattern, stripped, re.IGNORECASE)
                if match:
                    pytest.fail(
                        f"Possible hardcoded secret on line {i + 1}: {stripped}"
                    )


# ---------------------------------------------------------------------------
# Health & Ports tests (4)
# ---------------------------------------------------------------------------


class TestDockerfileHealthAndPorts:
    """Verify health-check configuration and port consistency."""

    def test_healthcheck_directive_defined(self, dockerfile_content):
        """A HEALTHCHECK directive must be present so the orchestrator
        can detect unhealthy containers."""
        assert "HEALTHCHECK" in dockerfile_content, "HEALTHCHECK directive must be defined"

    def test_healthcheck_targets_health_endpoint(self, dockerfile_content):
        """The HEALTHCHECK must target the /api/v1/health endpoint."""
        assert "/api/v1/health" in dockerfile_content, (
            "HEALTHCHECK must target /api/v1/health"
        )

    def test_expose_port_matches_cmd_port(self, dockerfile_content):
        """The EXPOSE port and the port passed to uvicorn in CMD must
        match (both should be 8080)."""
        expose_match = re.search(r"EXPOSE\s+(\d+)", dockerfile_content)
        assert expose_match, "EXPOSE directive not found"
        expose_port = expose_match.group(1)

        cmd_match = re.search(r'--port["\s,]+(\d+)', dockerfile_content)
        assert cmd_match, "CMD with --port not found"
        cmd_port = cmd_match.group(1)

        assert expose_port == cmd_port, (
            f"EXPOSE port ({expose_port}) must match CMD port ({cmd_port})"
        )

    def test_env_port_matches_expose_port(self, dockerfile_content):
        """ENV PORT must match the EXPOSE port to ensure consistent
        port configuration throughout the Dockerfile."""
        env_match = re.search(r"ENV\s+PORT\s*=\s*(\d+)", dockerfile_content)
        assert env_match, "ENV PORT not found"
        env_port = env_match.group(1)

        expose_match = re.search(r"EXPOSE\s+(\d+)", dockerfile_content)
        assert expose_match, "EXPOSE directive not found"
        expose_port = expose_match.group(1)

        assert env_port == expose_port, (
            f"ENV PORT ({env_port}) must match EXPOSE port ({expose_port})"
        )
