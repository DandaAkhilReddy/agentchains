#!/usr/bin/env python3
"""SDK generator — fetches OpenAPI spec and generates client SDKs.

Generates lightweight client libraries for Python, JavaScript, and Go
from the live ``/openapi.json`` endpoint of the AgentChains marketplace.

Usage::

    python scripts/generate_sdk.py --url http://localhost:8000 --output sdks/
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

_PYTHON_CLIENT_TEMPLATE = '''\
"""Auto-generated AgentChains Python SDK — v{version}."""

from __future__ import annotations

from typing import Any

import httpx


class AgentChainsClient:
    """Lightweight HTTP client for the AgentChains marketplace API."""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        headers: dict[str, str] = {{"Accept": "application/json"}}
        if api_key:
            headers["Authorization"] = f"Bearer {{api_key}}"
        self._client = httpx.Client(base_url=self.base_url, headers=headers, timeout=30)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AgentChainsClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # --- generated helpers ---------------------------------------------------

{methods}
'''

_PYTHON_METHOD_TEMPLATE = '''\
    def {method_name}(self, **kwargs: Any) -> Any:
        """{summary}"""
        resp = self._client.request("{http_method}", "{path}", params=kwargs)
        resp.raise_for_status()
        return resp.json()
'''

_JS_CLIENT_TEMPLATE = '''\
/**
 * Auto-generated AgentChains JavaScript SDK — v{version}
 */

class AgentChainsClient {{
  constructor(baseUrl = "http://localhost:8000", apiKey = null) {{
    this.baseUrl = baseUrl.replace(/\\/+$/, "");
    this.apiKey = apiKey;
  }}

  async _request(method, path, params = {{}}) {{
    const url = new URL(path, this.baseUrl);
    if (method === "GET") {{
      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
    }}
    const headers = {{ "Accept": "application/json" }};
    if (this.apiKey) {{
      headers["Authorization"] = `Bearer ${{this.apiKey}}`;
    }}
    const opts = {{ method, headers }};
    if (method !== "GET" && Object.keys(params).length) {{
      headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(params);
    }}
    const resp = await fetch(url.toString(), opts);
    if (!resp.ok) throw new Error(`HTTP ${{resp.status}}: ${{await resp.text()}}`);
    return resp.json();
  }}

{methods}
}}

module.exports = {{ AgentChainsClient }};
'''

_JS_METHOD_TEMPLATE = '''\
  /** {summary} */
  async {method_name}(params = {{}}) {{
    return this._request("{http_method}", "{path}", params);
  }}
'''

_GO_CLIENT_TEMPLATE = '''\
// Auto-generated AgentChains Go SDK — v{version}
package agentchains

import (
\t"bytes"
\t"encoding/json"
\t"fmt"
\t"io"
\t"net/http"
)

// Client is a lightweight HTTP client for the AgentChains marketplace API.
type Client struct {{
\tBaseURL  string
\tAPIKey   string
\tHTTPClient *http.Client
}}

// NewClient creates a new AgentChains API client.
func NewClient(baseURL string, apiKey string) *Client {{
\treturn &Client{{
\t\tBaseURL:    baseURL,
\t\tAPIKey:     apiKey,
\t\tHTTPClient: &http.Client{{}},
\t}}
}}

func (c *Client) doRequest(method, path string, body interface{{}}) (map[string]interface{{}}, error) {{
\tvar reqBody io.Reader
\tif body != nil {{
\t\tb, err := json.Marshal(body)
\t\tif err != nil {{
\t\t\treturn nil, err
\t\t}}
\t\treqBody = bytes.NewReader(b)
\t}}
\treq, err := http.NewRequest(method, c.BaseURL+path, reqBody)
\tif err != nil {{
\t\treturn nil, err
\t}}
\treq.Header.Set("Accept", "application/json")
\tif c.APIKey != "" {{
\t\treq.Header.Set("Authorization", "Bearer "+c.APIKey)
\t}}
\tif body != nil {{
\t\treq.Header.Set("Content-Type", "application/json")
\t}}
\tresp, err := c.HTTPClient.Do(req)
\tif err != nil {{
\t\treturn nil, err
\t}}
\tdefer resp.Body.Close()
\tif resp.StatusCode >= 400 {{
\t\treturn nil, fmt.Errorf("HTTP %d", resp.StatusCode)
\t}}
\tvar result map[string]interface{{}}
\tif err := json.NewDecoder(resp.Body).Decode(&result); err != nil {{
\t\treturn nil, err
\t}}
\treturn result, nil
}}

{methods}
'''

_GO_METHOD_TEMPLATE = '''\
// {method_name} — {summary}
func (c *Client) {method_name}() (map[string]interface{{}}, error) {{
\treturn c.doRequest("{http_method}", "{path}", nil)
}}
'''


def _sanitize_name(operation_id: str) -> str:
    """Convert an operationId or path into a valid function name."""
    name = operation_id.replace("-", "_").replace(".", "_").replace("/", "_")
    # Remove leading underscores
    return name.lstrip("_")


def _go_public_name(name: str) -> str:
    """Convert a snake_case name to Go PascalCase."""
    return "".join(part.capitalize() for part in name.split("_"))


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


def _collect_operations(spec: dict[str, Any]) -> list[dict[str, str]]:
    """Extract a flat list of operations from an OpenAPI spec."""
    ops: list[dict[str, str]] = []
    for path, methods in spec.get("paths", {}).items():
        for method, details in methods.items():
            if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            op_id = details.get("operationId", path)
            summary = details.get("summary", op_id)
            ops.append(
                {
                    "path": path,
                    "http_method": method.upper(),
                    "operation_id": op_id,
                    "summary": summary,
                }
            )
    return ops


def generate_python(spec: dict[str, Any], output_dir: Path) -> None:
    """Generate a Python SDK into *output_dir*/python/."""
    dest = output_dir / "python"
    dest.mkdir(parents=True, exist_ok=True)

    version = spec.get("info", {}).get("version", "0.0.0")
    operations = _collect_operations(spec)

    methods = ""
    for op in operations:
        methods += _PYTHON_METHOD_TEMPLATE.format(
            method_name=_sanitize_name(op["operation_id"]),
            summary=op["summary"],
            http_method=op["http_method"],
            path=op["path"],
        )

    code = _PYTHON_CLIENT_TEMPLATE.format(version=version, methods=methods)
    (dest / "agentchains_client.py").write_text(code, encoding="utf-8")
    (dest / "__init__.py").write_text(
        f'"""AgentChains Python SDK v{version}."""\n\nfrom .agentchains_client import AgentChainsClient\n\n__all__ = ["AgentChainsClient"]\n',
        encoding="utf-8",
    )
    logger.info("Python SDK generated at %s", dest)


def generate_javascript(spec: dict[str, Any], output_dir: Path) -> None:
    """Generate a JavaScript SDK into *output_dir*/javascript/."""
    dest = output_dir / "javascript"
    dest.mkdir(parents=True, exist_ok=True)

    version = spec.get("info", {}).get("version", "0.0.0")
    operations = _collect_operations(spec)

    methods = ""
    for op in operations:
        methods += _JS_METHOD_TEMPLATE.format(
            method_name=_sanitize_name(op["operation_id"]),
            summary=op["summary"],
            http_method=op["http_method"],
            path=op["path"],
        )

    code = _JS_CLIENT_TEMPLATE.format(version=version, methods=methods)
    (dest / "agentchains_client.js").write_text(code, encoding="utf-8")

    pkg = {
        "name": "agentchains-sdk",
        "version": version,
        "description": "AgentChains JavaScript SDK",
        "main": "agentchains_client.js",
        "license": "MIT",
    }
    (dest / "package.json").write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")
    logger.info("JavaScript SDK generated at %s", dest)


def generate_go(spec: dict[str, Any], output_dir: Path) -> None:
    """Generate a Go SDK into *output_dir*/go/."""
    dest = output_dir / "go"
    dest.mkdir(parents=True, exist_ok=True)

    version = spec.get("info", {}).get("version", "0.0.0")
    operations = _collect_operations(spec)

    methods = ""
    for op in operations:
        methods += _GO_METHOD_TEMPLATE.format(
            method_name=_go_public_name(_sanitize_name(op["operation_id"])),
            summary=op["summary"],
            http_method=op["http_method"],
            path=op["path"],
        )

    code = _GO_CLIENT_TEMPLATE.format(version=version, methods=methods)
    (dest / "client.go").write_text(code, encoding="utf-8")

    go_mod = f"module github.com/agentchains/sdk-go\n\ngo 1.21\n"
    (dest / "go.mod").write_text(go_mod, encoding="utf-8")
    logger.info("Go SDK generated at %s", dest)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AgentChains client SDKs from OpenAPI spec")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the running AgentChains server (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--output",
        default="sdks/",
        help="Output directory for generated SDKs (default: sdks/)",
    )
    parser.add_argument(
        "--spec-file",
        default=None,
        help="Path to a local openapi.json file (skips HTTP fetch)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output)

    if args.spec_file:
        logger.info("Reading OpenAPI spec from %s", args.spec_file)
        spec = json.loads(Path(args.spec_file).read_text(encoding="utf-8"))
    else:
        spec_url = f"{args.url.rstrip('/')}/openapi.json"
        logger.info("Fetching OpenAPI spec from %s", spec_url)
        try:
            resp = httpx.get(spec_url, timeout=30)
            resp.raise_for_status()
            spec = resp.json()
        except httpx.HTTPError as exc:
            logger.error("Failed to fetch OpenAPI spec: %s", exc)
            sys.exit(1)

    logger.info(
        "OpenAPI spec: %s v%s — %d paths",
        spec.get("info", {}).get("title", "?"),
        spec.get("info", {}).get("version", "?"),
        len(spec.get("paths", {})),
    )

    generate_python(spec, output_dir)
    generate_javascript(spec, output_dir)
    generate_go(spec, output_dir)

    logger.info("SDK generation complete. Output: %s", output_dir.resolve())


if __name__ == "__main__":
    main()
