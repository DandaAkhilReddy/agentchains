"""Export the OpenAPI schema to a JSON file.

Usage:
    python scripts/export_openapi.py              # writes docs/openapi.json
    python scripts/export_openapi.py --yaml       # writes docs/openapi.yaml
    python scripts/export_openapi.py --stdout      # prints to stdout
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from marketplace.main import app  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Export AgentChains OpenAPI schema")
    parser.add_argument("--output", default="docs/openapi.json", help="Output file path")
    parser.add_argument("--yaml", action="store_true", help="Export as YAML instead of JSON")
    parser.add_argument("--stdout", action="store_true", help="Print to stdout")
    args = parser.parse_args()

    schema = app.openapi()

    if args.stdout:
        print(json.dumps(schema, indent=2))
        return

    output_path = Path(args.output)
    if args.yaml:
        output_path = output_path.with_suffix(".yaml")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.yaml:
        try:
            import yaml

            with open(output_path, "w") as f:
                yaml.dump(schema, f, default_flow_style=False, sort_keys=False)
        except ImportError:
            print("PyYAML not installed. Install with: pip install pyyaml", file=sys.stderr)
            sys.exit(1)
    else:
        with open(output_path, "w") as f:
            json.dump(schema, f, indent=2)

    print(f"OpenAPI schema exported to {output_path}")
    print(f"  Paths: {len(schema.get('paths', {}))}")
    print(f"  Version: {schema.get('info', {}).get('version', 'unknown')}")


if __name__ == "__main__":
    main()
