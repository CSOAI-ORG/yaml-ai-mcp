"""
YAML AI MCP Server
YAML validation, conversion and linting tools powered by MEOK AI Labs.
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
    import yaml
    return yaml


@mcp.tool()
def validate_yaml(content: str) -> dict:
    """Validate YAML syntax and return parsed structure info.

    Args:
        content: YAML string to validate
    """
    _check_rate_limit("validate_yaml")
    try:
        yaml = _get_yaml()
        docs = list(yaml.safe_load_all(content))
        doc_count = len(docs)
        root_type = type(docs[0]).__name__ if docs else "empty"
        keys = list(docs[0].keys()) if isinstance(docs[0], dict) else []
        return {"valid": True, "documents": doc_count, "root_type": root_type,
                "top_level_keys": keys[:20], "message": "Valid YAML"}
    except ImportError:
        return {"error": "PyYAML required. Install with: pip install pyyaml"}
    except Exception as e:
        line = getattr(e, 'problem_mark', None)
        loc = {"line": line.line + 1, "column": line.column + 1} if line else {}
        return {"valid": False, "error": str(e), "location": loc}


@mcp.tool()
def convert_yaml_json(content: str, direction: str = "yaml_to_json") -> dict:
    """Convert between YAML and JSON formats.

    Args:
        content: Content string to convert
        direction: 'yaml_to_json' or 'json_to_yaml'
    """
    _check_rate_limit("convert_yaml_json")
    try:
        yaml = _get_yaml()
        if direction == "yaml_to_json":
            data = yaml.safe_load(content)
            result = json.dumps(data, indent=2, default=str)
            return {"direction": direction, "result": result, "success": True}
        elif direction == "json_to_yaml":
            data = json.loads(content)
            result = yaml.dump(data, default_flow_style=False, sort_keys=False)
            return {"direction": direction, "result": result, "success": True}
        else:
            return {"error": "direction must be 'yaml_to_json' or 'json_to_yaml'"}
    except ImportError:
        return {"error": "PyYAML required. Install with: pip install pyyaml"}
    except Exception as e:
        return {"error": str(e), "success": False}


@mcp.tool()
def lint_yaml(content: str) -> dict:
    """Lint YAML content for style issues and best practices.

    Args:
        content: YAML content to lint
    """
    _check_rate_limit("lint_yaml")
    issues = []
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        if line.rstrip() != line:
            issues.append({"line": i, "severity": "warning", "message": "Trailing whitespace"})
        if '\t' in line:
            issues.append({"line": i, "severity": "error", "message": "Tab character found (use spaces)"})
        if len(line) > 120:
            issues.append({"line": i, "severity": "warning", "message": f"Line too long ({len(line)} > 120)"})
        if line.strip().startswith('- ') and i > 1:
            prev = lines[i-2] if i >= 2 else ""
            curr_indent = len(line) - len(line.lstrip())
            if curr_indent % 2 != 0:
                issues.append({"line": i, "severity": "warning", "message": "Odd indentation (prefer 2-space)"})
    if lines and lines[-1].strip() != '':
        issues.append({"line": len(lines), "severity": "info", "message": "No trailing newline"})
    if content.startswith('---'):
        pass
    else:
        issues.append({"line": 1, "severity": "info", "message": "Consider adding document start marker (---)"})
    try:
        yaml = _get_yaml()
        yaml.safe_load(content)
    except ImportError:
        pass
    except Exception as e:
        issues.insert(0, {"line": 0, "severity": "error", "message": f"Parse error: {e}"})
    score = max(0, 100 - len([i for i in issues if i["severity"] == "error"]) * 20
                - len([i for i in issues if i["severity"] == "warning"]) * 5)
    return {"issues": issues[:50], "issue_count": len(issues), "score": score, "lines": len(lines)}


@mcp.tool()
def merge_yaml(documents: list[str], strategy: str = "deep") -> dict:
    """Merge multiple YAML documents into one.

    Args:
        documents: List of YAML strings to merge
        strategy: 'deep' (recursive merge) or 'shallow' (top-level only)
    """
    _check_rate_limit("merge_yaml")
    try:
        yaml = _get_yaml()
        parsed = [yaml.safe_load(d) for d in documents]
        if not all(isinstance(p, dict) for p in parsed):
            return {"error": "All documents must be YAML mappings (dicts) for merging"}
        def deep_merge(a, b):
            result = dict(a)
            for k, v in b.items():
                if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                    result[k] = deep_merge(result[k], v)
                else:
                    result[k] = v
            return result
        merged = {}
        for doc in parsed:
            if strategy == "deep":
                merged = deep_merge(merged, doc)
            else:
                merged.update(doc)
        result = yaml.dump(merged, default_flow_style=False, sort_keys=False)
        return {"merged": result, "documents_merged": len(documents), "strategy": strategy,
                "total_keys": len(merged)}
    except ImportError:
        return {"error": "PyYAML required. Install with: pip install pyyaml"}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run()
