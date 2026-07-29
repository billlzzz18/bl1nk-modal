#!/usr/bin/env python3
"""Scan local data sources for metadata fields used by search service.

Sources:
  - /data/data/com.termux/files/usr/tmp/   (system temp)
  - ~/modal/                               (project root)
  - ~/.qwen/memories/                      (Qwen user memories)
  - ~/.qwen/                               (Qwen global config)
  - ~/.config/hermes/                      (Hermes global config, if exists)

Outputs discovered fields + example values for each source.
"""
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

HOME = os.environ.get("HOME", "/data/data/com.termux/files/home")
SOURCES = {
    "tmp": "/data/data/com.termux/files/usr/tmp",
    "project": os.path.join(HOME, "modal"),
    "qwen_memories": os.path.join(HOME, ".qwen", "memories"),
    "qwen": os.path.join(HOME, ".qwen"),
    "hermes_config": os.path.join(HOME, ".config", "hermes"),
    "hermes_hooks": os.path.join(HOME, ".hermes", "hooks"),
}


def scan_json(path: str, depth: int = 0) -> dict:
    """Recursively find all JSON keys in files under path."""
    fields = defaultdict(set)

    if not os.path.isdir(path) and not os.path.isfile(path):
        return {}

    files = []
    if os.path.isfile(path):
        files = [path]
    else:
        for root, dirs, fnames in os.walk(path):
            for fn in fnames:
                if fn.endswith((".json", ".jsonl", ".md", ".yaml", ".yml", ".toml", ".env")):
                    files.append(os.path.join(root, fn))

    for fp in files:
        try:
            content = Path(fp).read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        rel = os.path.relpath(fp, path) if os.path.isdir(path) else fp

        # JSON / JSONL
        if fp.endswith((".json", ".jsonl")):
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    try:
                        data = json.loads("{" + line.split("{", 1)[1].rsplit("}", 1)[0] + "}")
                    except (json.JSONDecodeError, IndexError):
                        continue
                _extract_keys(data, fields, rel)

        # YAML (simple key: value lines)
        elif fp.endswith((".yaml", ".yml")):
            for m in re.finditer(r'^(\w[\w_/-]*)\s*:', content, re.MULTILINE):
                fields["yaml_keys"].add(m.group(1))

        # TOML
        elif fp.endswith(".toml"):
            for m in re.finditer(r'^(\w[\w_]*)\s*[=:]', content, re.MULTILINE):
                fields["toml_keys"].add(m.group(1))

        # Markdown frontmatter (---\nkey: value\n---)
        elif fp.endswith(".md"):
            fm = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
            if fm:
                for m in re.finditer(r'^(\w[\w_-]*)\s*:', fm.group(1), re.MULTILINE):
                    fields["frontmatter_keys"].add(m.group(1))

        # .env
        elif fp.endswith(".env"):
            for m in re.finditer(r'^(\w[\w_]*)=', content, re.MULTILINE):
                fields["env_keys"].add(m.group(1))

    return {k: list(v)[:10] for k, v in fields.items()}  # limit to 10 examples


def _extract_keys(data, fields, source):
    if isinstance(data, dict):
        for k, v in data.items():
            fields["dict_keys"].add(str(k))
            _extract_keys(v, fields, source)
    elif isinstance(data, list):
        for item in data[:5]:  # sample first 5
            _extract_keys(item, fields, source)


def main():
    print("=" * 60)
    print("FIELD DISCOVERY SCAN")
    print("=" * 60)
    print()

    all_keys = defaultdict(set)

    for name, src_path in SOURCES.items():
        src_path = os.path.expandvars(os.path.expanduser(src_path))
        exists = os.path.exists(src_path)

        if exists:
            print(f"📁 [{name}] {src_path}")
            fields = scan_json(src_path)
            if fields:
                for cat, vals in fields.items():
                    for v in vals:
                        all_keys[cat].add(v)
                    print(f"   {cat}: {', '.join(str(v) for v in vals[:8])}")
                    if len(vals) > 8:
                        print(f"   ... +{len(vals)-8} more")
            else:
                print("   (no structured fields found)")
        else:
            print(f"📁 [{name}] (not found: {src_path})")
        print()

    print("=" * 60)
    print("SUMMARY — ALL DISCOVERED FIELDS")
    print("=" * 60)
    for cat in sorted(all_keys):
        vals = sorted(all_keys[cat])
        print(f"\n{cat} ({len(vals)}):")
        for v in vals[:20]:
            print(f"  • {v}")
        if len(vals) > 20:
            print(f"  ... +{len(vals)-20} more")

    # Generate search metadata field candidates
    dict_keys = all_keys.get("dict_keys", set())
    frontmatter = all_keys.get("frontmatter_keys", set())
    yaml_keys = all_keys.get("yaml_keys", set())
    toml_keys = all_keys.get("toml_keys", set())
    all_field_candidates = dict_keys | frontmatter | yaml_keys | toml_keys

    print(f"\n{'='*60}")
    print(f"SEARCH METADATA FIELD CANDIDATES ({len(all_field_candidates)} total)")
    print(f"{'='*60}")
    print()
    print("Fields from dicts + frontmatter + yaml + toml that could be")
    print("used as search metadata filters:")
    for f in sorted(all_field_candidates):
        print(f"  • {f}")


if __name__ == "__main__":
    main()
