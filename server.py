"""
YAML AI MCP Server
YAML parsing, validation, and conversion tools powered by MEOK AI Labs.
"""

import json
import time
from collections import defaultdict
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("yaml-ai-mcp")

_call_counts: dict[str, list[float]] = defaultdict(list)
FREE_TIER_LIMIT = 50
WINDOW = 86400


def _check_rate_limit(tool_name: str) -> None:
    now = time.time()
    _call_counts[tool_name] = [t for t in _call_counts[tool_name] if now - t < WINDOW]
    if len(_call_counts[tool_name]) >= FREE_TIER_LIMIT:
        raise ValueError(f"Rate limit exceeded for {tool_name}. Free tier: {FREE_TIER_LIMIT}/day. Upgrade at https://meok.ai/pricing")
    _call_counts[tool_name].append(now)


def _get_yaml():
    try:
        import yaml
        return yaml
    except ImportError:
        raise ValueError("PyYAML required. Install: pip install pyyaml")


@mcp.tool()
def validate_yaml(content: str) -> dict:
    """Validate YAML syntax and report any errors.

    Args:
        content: YAML string to validate
    """
    _check_rate_limit("validate_yaml")
    yaml = _get_yaml()
    try:
        docs = list(yaml.safe_load_all(content))
        doc_count = len(docs)
        keys = []
        if doc_count > 0 and isinstance(docs[0], dict):
            keys = list(docs[0].keys())
        return {"valid": True, "documents": doc_count, "top_level_keys": keys}
    except yaml.YAMLError as e:
        error_info = {"valid": False, "error": str(e)}
        if hasattr(e, 'problem_mark'):
            mark = e.problem_mark
            error_info["line"] = mark.line + 1
            error_info["column"] = mark.column + 1
        return error_info


@mcp.tool()
def convert_yaml_json(content: str, direction: str = "yaml_to_json") -> dict:
    """Convert between YAML and JSON formats.

    Args:
        content: Input content string
        direction: Conversion direction - 'yaml_to_json' or 'json_to_yaml'
    """
    _check_rate_limit("convert_yaml_json")
    yaml = _get_yaml()
    if direction == "yaml_to_json":
        try:
            data = yaml.safe_load(content)
            result = json.dumps(data, indent=2, default=str)
            return {"result": result, "direction": direction, "success": True}
        except Exception as e:
            return {"error": str(e), "direction": direction, "success": False}
    elif direction == "json_to_yaml":
        try:
            data = json.loads(content)
            result = yaml.dump(data, default_flow_style=False, sort_keys=False)
            return {"result": result, "direction": direction, "success": True}
        except Exception as e:
            return {"error": str(e), "direction": direction, "success": False}
    else:
        return {"error": "direction must be 'yaml_to_json' or 'json_to_yaml'", "success": False}


@mcp.tool()
def lint_yaml(content: str) -> dict:
    """Lint YAML content for style issues and best practices.

    Args:
        content: YAML string to lint
    """
    _check_rate_limit("lint_yaml")
    yaml = _get_yaml()
    issues = []
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        if line.rstrip() != line:
            issues.append({"line": i, "issue": "trailing_whitespace", "severity": "warning"})
        if '\t' in line:
            issues.append({"line": i, "issue": "tab_character", "severity": "error", "message": "YAML should use spaces, not tabs"})
        if len(line) > 120:
            issues.append({"line": i, "issue": "line_too_long", "severity": "warning", "length": len(line)})
    if not content.startswith('---'):
        issues.append({"line": 1, "issue": "missing_document_start", "severity": "info", "message": "Consider adding --- at the start"})
    if content and not content.endswith('\n'):
        issues.append({"line": len(lines), "issue": "missing_final_newline", "severity": "warning"})
    try:
        yaml.safe_load(content)
        parse_valid = True
    except yaml.YAMLError:
        parse_valid = False
        issues.append({"line": 0, "issue": "parse_error", "severity": "error"})
    return {"valid": parse_valid, "issues": issues, "issue_count": len(issues),
            "errors": sum(1 for i in issues if i["severity"] == "error"),
            "warnings": sum(1 for i in issues if i["severity"] == "warning")}


@mcp.tool()
def merge_yaml(yaml_a: str, yaml_b: str, strategy: str = "deep") -> dict:
    """Merge two YAML documents together.

    Args:
        yaml_a: First YAML document (base)
        yaml_b: Second YAML document (overlay)
        strategy: Merge strategy - 'deep' (recursive merge) or 'shallow' (top-level only)
    """
    _check_rate_limit("merge_yaml")
    yaml = _get_yaml()
    try:
        a = yaml.safe_load(yaml_a) or {}
        b = yaml.safe_load(yaml_b) or {}
    except yaml.YAMLError as e:
        return {"error": f"YAML parse error: {e}", "success": False}

    def deep_merge(base, overlay):
        result = base.copy()
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    if not isinstance(a, dict) or not isinstance(b, dict):
        return {"error": "Both inputs must be YAML mappings for merge", "success": False}
    if strategy == "deep":
        merged = deep_merge(a, b)
    else:
        merged = {**a, **b}
    result = yaml.dump(merged, default_flow_style=False, sort_keys=False)
    return {"result": result, "strategy": strategy, "keys_a": len(a), "keys_b": len(b),
            "keys_merged": len(merged), "success": True}


if __name__ == "__main__":
    mcp.run()
