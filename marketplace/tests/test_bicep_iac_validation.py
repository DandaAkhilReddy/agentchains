"""Tests for Bicep Infrastructure-as-Code validation.

Parses Bicep files as plain text to validate:
- Orchestrator (main.bicep) module deployments and dependencies
- Production SKUs for all Azure resources
- Security hardening (network access, TLS, purge protection)
- Parameter files for production deployment
- Port and probe consistency with the Dockerfile
"""

import json
import pathlib
import re

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
INFRA_DIR = PROJECT_ROOT / "infra"
MODULES_DIR = INFRA_DIR / "modules"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_bicep(path: pathlib.Path) -> str:
    """Read a Bicep file and return its contents as a string."""
    assert path.is_file(), f"Bicep file not found: {path}"
    return path.read_text(encoding="utf-8")


def _read_json(path: pathlib.Path) -> dict:
    """Read a JSON file and return parsed contents."""
    assert path.is_file(), f"JSON file not found: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


# ===========================================================================
# 1. Orchestrator (5 tests)
# ===========================================================================

class TestOrchestrator:
    """Validate main.bicep deploys all required modules with correct dependencies."""

    def test_main_bicep_deploys_all_nine_modules(self):
        """main.bicep must deploy all 9 modules."""
        content = _read_bicep(INFRA_DIR / "main.bicep")

        expected_modules = [
            "insights",
            "postgres",
            "redis",
            "storage",
            "keyvault",
            "search",
            "openai",
            "servicebus",
            "containerapp",
        ]
        for module in expected_modules:
            # Match module declaration like: module insights 'modules/insights.bicep'
            pattern = rf"module\s+{module}\s+"
            assert re.search(pattern, content), (
                f"Module '{module}' not found in main.bicep"
            )

    def test_containerapp_depends_on_all_other_modules(self):
        """containerapp module must dependsOn all 8 other modules."""
        content = _read_bicep(INFRA_DIR / "main.bicep")

        # Extract the dependsOn block for the containerapp module
        containerapp_match = re.search(
            r"module\s+containerapp\b.*?dependsOn\s*:\s*\[(.*?)\]",
            content,
            re.DOTALL,
        )
        assert containerapp_match, (
            "containerapp module or its dependsOn block not found in main.bicep"
        )

        depends_on_block = containerapp_match.group(1)
        expected_deps = [
            "insights", "postgres", "redis", "keyvault",
            "search", "openai", "servicebus", "storage",
        ]
        for dep in expected_deps:
            assert dep in depends_on_block, (
                f"containerapp does not depend on '{dep}' in main.bicep"
            )

    def test_required_params_exist(self):
        """main.bicep must declare required parameters."""
        content = _read_bicep(INFRA_DIR / "main.bicep")

        required_params = [
            "location",
            "environment",
            "tenantId",
            "postgresAdminLogin",
            "postgresAdminPassword",
        ]
        for param in required_params:
            pattern = rf"param\s+{param}\s+"
            assert re.search(pattern, content), (
                f"Required parameter '{param}' not found in main.bicep"
            )

    def test_environment_param_has_allowed_values(self):
        """environment param must have @allowed with dev, staging, prod."""
        content = _read_bicep(INFRA_DIR / "main.bicep")

        allowed_match = re.search(
            r"@allowed\(\[([^\]]+)\]\)\s*param\s+environment\s+",
            content,
        )
        assert allowed_match, (
            "@allowed decorator for environment param not found in main.bicep"
        )

        allowed_values = allowed_match.group(1)
        for env in ["dev", "staging", "prod"]:
            assert f"'{env}'" in allowed_values, (
                f"'{env}' not in @allowed values for environment param"
            )

    def test_project_name_has_default_agentchains(self):
        """projectName param should default to 'agentchains'."""
        content = _read_bicep(INFRA_DIR / "main.bicep")

        pattern = r"param\s+projectName\s+string\s*=\s*'agentchains'"
        assert re.search(pattern, content), (
            "projectName default 'agentchains' not found in main.bicep"
        )


# ===========================================================================
# 2. Production SKUs (7 tests)
# ===========================================================================

class TestProductionSKUs:
    """Validate that production SKU tiers are appropriately sized."""

    def test_postgres_prod_sku_tier_general_purpose(self):
        """PostgreSQL production SKU tier must be GeneralPurpose."""
        content = _read_bicep(MODULES_DIR / "postgres.bicep")
        assert "'GeneralPurpose'" in content, (
            "PostgreSQL prod SKU tier 'GeneralPurpose' not found in postgres.bicep"
        )

    def test_postgres_prod_ha_zone_redundant(self):
        """PostgreSQL production HA mode must be ZoneRedundant."""
        content = _read_bicep(MODULES_DIR / "postgres.bicep")
        assert "'ZoneRedundant'" in content, (
            "PostgreSQL prod HA mode 'ZoneRedundant' not found in postgres.bicep"
        )

    def test_redis_prod_sku_standard(self):
        """Redis production SKU must be Standard."""
        content = _read_bicep(MODULES_DIR / "redis.bicep")
        match = re.search(
            r"environment\s*==\s*'prod'\s*\?\s*'Standard'",
            content,
        )
        assert match, "Redis prod SKU 'Standard' not found in redis.bicep"

    def test_storage_prod_sku_standard_grs(self):
        """Storage production SKU must be Standard_GRS for geo-redundancy."""
        content = _read_bicep(MODULES_DIR / "storage.bicep")
        assert "'Standard_GRS'" in content, (
            "Storage prod SKU 'Standard_GRS' not found in storage.bicep"
        )

    def test_keyvault_prod_sku_premium(self):
        """KeyVault production SKU must be premium."""
        content = _read_bicep(MODULES_DIR / "keyvault.bicep")
        match = re.search(
            r"environment\s*==\s*'prod'\s*\?\s*'premium'",
            content,
        )
        assert match, "KeyVault prod SKU 'premium' not found in keyvault.bicep"

    def test_containerapp_prod_min_replicas_at_least_two(self):
        """Container App prod minReplicas must be >= 2."""
        content = _read_bicep(MODULES_DIR / "containerapp.bicep")
        match = re.search(
            r"minReplicas\s*=\s*environment\s*==\s*'prod'\s*\?\s*(\d+)",
            content,
        )
        assert match, "minReplicas prod ternary not found in containerapp.bicep"
        min_replicas = int(match.group(1))
        assert min_replicas >= 2, (
            f"Container App prod minReplicas is {min_replicas}, expected >= 2"
        )

    def test_postgres_geo_redundant_backup_enabled_for_prod(self):
        """PostgreSQL geoRedundantBackup must be Enabled for production."""
        content = _read_bicep(MODULES_DIR / "postgres.bicep")
        match = re.search(
            r"geoRedundantBackup\s*:\s*environment\s*==\s*'prod'\s*\?\s*'Enabled'",
            content,
        )
        assert match, (
            "geoRedundantBackup 'Enabled' for prod not found in postgres.bicep"
        )


# ===========================================================================
# 3. Security (5 tests)
# ===========================================================================

class TestSecurity:
    """Validate security hardening in Bicep modules."""

    def test_redis_disables_public_network_for_prod(self):
        """Redis must disable public network access in production."""
        content = _read_bicep(MODULES_DIR / "redis.bicep")
        match = re.search(
            r"publicNetworkAccess\s*:\s*environment\s*==\s*'prod'\s*\?\s*'Disabled'",
            content,
        )
        assert match, (
            "Redis publicNetworkAccess 'Disabled' for prod not found in redis.bicep"
        )

    def test_keyvault_enables_purge_protection_for_prod(self):
        """KeyVault must enable purge protection in production."""
        content = _read_bicep(MODULES_DIR / "keyvault.bicep")
        match = re.search(
            r"enablePurgeProtection\s*:\s*environment\s*==\s*'prod'\s*\?\s*true",
            content,
        )
        assert match, (
            "KeyVault enablePurgeProtection for prod not found in keyvault.bicep"
        )

    def test_storage_denies_public_blob_access(self):
        """Storage must deny public blob access (allowBlobPublicAccess: false)."""
        content = _read_bicep(MODULES_DIR / "storage.bicep")
        match = re.search(
            r"allowBlobPublicAccess\s*:\s*false",
            content,
        )
        assert match, (
            "Storage allowBlobPublicAccess: false not found in storage.bicep"
        )

    def test_tls_12_enforced_for_redis_and_storage(self):
        """Both Redis and Storage must enforce TLS 1.2 minimum."""
        redis_content = _read_bicep(MODULES_DIR / "redis.bicep")
        storage_content = _read_bicep(MODULES_DIR / "storage.bicep")

        # Redis uses minimumTlsVersion: '1.2'
        assert re.search(r"minimumTlsVersion\s*:\s*'1\.2'", redis_content), (
            "Redis minimumTlsVersion '1.2' not found in redis.bicep"
        )

        # Storage uses minimumTlsVersion: 'TLS1_2'
        assert re.search(r"minimumTlsVersion\s*:\s*'TLS1_2'", storage_content), (
            "Storage minimumTlsVersion 'TLS1_2' not found in storage.bicep"
        )

    def test_keyvault_public_network_disabled_for_prod(self):
        """KeyVault must disable public network access in production."""
        content = _read_bicep(MODULES_DIR / "keyvault.bicep")
        match = re.search(
            r"publicNetworkAccess\s*:\s*environment\s*==\s*'prod'\s*\?\s*'Disabled'",
            content,
        )
        assert match, (
            "KeyVault publicNetworkAccess 'Disabled' for prod not found in keyvault.bicep"
        )


# ===========================================================================
# 4. Parameter Files (3 tests)
# ===========================================================================

class TestParameterFiles:
    """Validate production parameter file exists and has correct values."""

    def test_parameters_prod_json_exists(self):
        """parameters.prod.json must exist in the infra directory."""
        params_file = INFRA_DIR / "parameters.prod.json"
        assert params_file.is_file(), (
            f"parameters.prod.json not found at {params_file}"
        )

    def test_parameters_prod_sets_environment_prod(self):
        """parameters.prod.json must set environment to 'prod'."""
        params = _read_json(INFRA_DIR / "parameters.prod.json")
        env_value = params.get("parameters", {}).get("environment", {}).get("value")
        assert env_value == "prod", (
            f"parameters.prod.json environment is '{env_value}', expected 'prod'"
        )

    def test_parameters_prod_uses_keyvault_references_for_secrets(self):
        """parameters.prod.json should use Key Vault references for sensitive params."""
        params = _read_json(INFRA_DIR / "parameters.prod.json")
        parameters = params.get("parameters", {})

        # These sensitive parameters should use keyVault references
        secret_params = [
            "postgresAdminPassword",
            "containerRegistryUsername",
            "containerRegistryPassword",
        ]
        for param_name in secret_params:
            param_def = parameters.get(param_name, {})
            assert "reference" in param_def, (
                f"'{param_name}' in parameters.prod.json should use a keyVault "
                f"reference but has keys: {list(param_def.keys())}"
            )
            assert "keyVault" in param_def.get("reference", {}), (
                f"'{param_name}' reference does not contain a keyVault block"
            )


# ===========================================================================
# 5. Port Consistency -- WILL CATCH REAL BUGS (2 tests)
# ===========================================================================

class TestPortConsistency:
    """Validate that containerapp.bicep ports and probes match the Dockerfile.

    The Dockerfile exposes port 8080 and uses /api/v1/health as the health
    check path. The Bicep file currently has port 8000 and /health -- these
    are known bugs that these tests are designed to catch.
    """

    def test_containerapp_target_port_matches_dockerfile(self):
        """containerapp.bicep targetPort must be 8080 to match Dockerfile EXPOSE.

        KNOWN BUG: containerapp.bicep currently sets targetPort: 8000 but
        the Dockerfile EXPOSEs 8080. This test asserts the CORRECT value
        and is expected to FAIL until the bug is fixed.
        """
        content = _read_bicep(MODULES_DIR / "containerapp.bicep")

        # The Dockerfile uses: EXPOSE 8080 and CMD [..., "--port", "8080"]
        # So the Bicep targetPort must also be 8080
        match = re.search(r"targetPort\s*:\s*(\d+)", content)
        assert match, "targetPort not found in containerapp.bicep"

        target_port = int(match.group(1))
        assert target_port == 8080, (
            f"containerapp.bicep targetPort is {target_port}, but Dockerfile "
            f"EXPOSEs 8080. This is a deployment bug -- the container will "
            f"listen on 8080 but Azure will route traffic to {target_port}."
        )

    def test_containerapp_probe_path_matches_app_health_endpoint(self):
        """containerapp.bicep probe paths must be '/api/v1/health'.

        KNOWN BUG: containerapp.bicep currently uses '/health' but the
        Dockerfile HEALTHCHECK and the FastAPI app use '/api/v1/health'.
        This test asserts the CORRECT value and is expected to FAIL until
        the bug is fixed.
        """
        content = _read_bicep(MODULES_DIR / "containerapp.bicep")

        # Find all probe path entries
        probe_paths = re.findall(r"path\s*:\s*'([^']+)'", content)
        assert len(probe_paths) > 0, (
            "No probe paths found in containerapp.bicep"
        )

        for path in probe_paths:
            assert path == "/api/v1/health", (
                f"containerapp.bicep probe path is '{path}', but the app's "
                f"health endpoint is '/api/v1/health'. This mismatch will "
                f"cause Azure to report the container as unhealthy."
            )
