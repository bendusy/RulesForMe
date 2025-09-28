#!/usr/bin/env python3
"""校验 ruleset manifest 的一致性。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rulesforme import ManifestError, RulesetManifest, load_manifest  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="校验 config/ruleset_manifest.yaml")
    parser.add_argument(
        "--path",
        default=str(ROOT_DIR / "config" / "ruleset_manifest.yaml"),
        help="manifest 文件路径，默认使用仓库内 config/ruleset_manifest.yaml",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="将所有 warning 视为错误",
    )
    return parser.parse_args()


def validate_manifest(manifest: RulesetManifest, *, strict: bool = False) -> int:
    warnings: list[str] = []

    referenced_sources = set()
    for category in manifest.categories.values():
        referenced_sources.update(category.sources)

    unused = sorted(set(manifest.sources) - referenced_sources)
    if unused:
        warnings.append("存在未被分类引用的 source: " + ", ".join(unused))

    # 针对本地源检查文件存在性
    for source in manifest.sources.values():
        if source.type == "local":
            path = ROOT_DIR / source.path  # type: ignore[arg-type]
            if not path.exists():
                raise ManifestError(f"local source '{source.id}' 的文件不存在: {path}")

    if warnings:
        header = "发现以下告警:" if not strict else "严格模式下将告警视为错误:" 
        print(header)
        for item in warnings:
            print(f" - {item}")
        if strict:
            return 1
    return 0


def main() -> int:
    args = parse_args()
    try:
        manifest = load_manifest(args.path)
    except ManifestError as exc:
        print(f"Manifest 校验失败: {exc}")
        return 1
    except Exception as exc:  # 防止其它未预见异常静默
        print(f"载入 manifest 时出现未知错误: {exc}")
        return 1

    exit_code = validate_manifest(manifest, strict=args.strict)
    if exit_code == 0:
        print("Manifest 校验通过。")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
