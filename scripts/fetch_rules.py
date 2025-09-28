#!/usr/bin/env python3
"""根据 manifest 下载远程规则文件。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Set

try:
    import requests
except ImportError:  # pragma: no cover - 仅在缺库时触发
    print("ERROR: 需要安装 requests，请运行 'pip install requests'。", file=sys.stderr)
    sys.exit(1)

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rulesforme import ManifestError, ManifestSource, RulesetManifest, load_manifest  # noqa: E402


DEFAULT_TIMEOUT = 30
DEFAULT_CHUNK_SIZE = 65536


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="下载 manifest 中定义的远程规则文件")
    parser.add_argument(
        "--manifest",
        default=str(ROOT_DIR / "config" / "ruleset_manifest.yaml"),
        help="manifest 文件位置，默认使用仓库内 config/ruleset_manifest.yaml",
    )
    parser.add_argument(
        "--sources",
        nargs="*",
        help="仅下载指定 source id（空则下载全部远程源）",
    )
    parser.add_argument(
        "--categories",
        nargs="*",
        help="限制在指定分类引用的源，常与 --sources 互斥",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印将要执行的下载，不实际写入",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"单个请求的超时时间（秒），默认 {DEFAULT_TIMEOUT}",
    )
    return parser.parse_args()


def determine_source_ids(manifest: RulesetManifest, args: argparse.Namespace) -> List[str]:
    if args.sources:
        return args.sources
    if args.categories:
        source_ids: Set[str] = set()
        for cat_name in args.categories:
            if cat_name not in manifest.categories:
                raise ManifestError(f"未知分类: {cat_name}")
            source_ids.update(manifest.categories[cat_name].sources)
        return sorted(source_ids)
    return [sid for sid, src in manifest.sources.items() if src.type == "remote"]


def resolve_destination(manifest: RulesetManifest, source: ManifestSource) -> Path:
    target_path = Path(source.target)
    if target_path.parts and target_path.parts[0] == manifest.defaults.cache_root:
        relative = Path(*target_path.parts[1:]) if len(target_path.parts) > 1 else Path("")
        dest_root = ROOT_DIR / manifest.defaults.cache_root
        dest = dest_root / relative
    else:
        dest_root = ROOT_DIR / manifest.defaults.download_root
        dest = dest_root / target_path
    return dest


def download_source(session: requests.Session, source: ManifestSource, dest: Path, *, timeout: int, dry_run: bool) -> bool:
    if source.uri is None:
        raise ManifestError(f"source '{source.id}' 缺少 uri，无法下载")

    if dry_run:
        print(f"[DRY-RUN] 将下载 {source.uri} -> {dest}")
        return True

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest.with_suffix(dest.suffix + ".tmp")

    try:
        with session.get(source.uri, timeout=timeout, stream=True) as response:
            response.raise_for_status()
            with tmp_path.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=DEFAULT_CHUNK_SIZE):
                    if chunk:
                        fh.write(chunk)
    except requests.RequestException as exc:
        if source.critical:
            raise ManifestError(f"下载关键源 '{source.id}' 失败: {exc}") from exc
        print(f"WARN: 下载非关键源 '{source.id}' 失败: {exc}")
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return False

    tmp_path.replace(dest)
    print(f"下载完成: {source.id} -> {dest}")
    return True


def main() -> int:
    args = parse_args()
    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as exc:
        print(f"载入 manifest 失败: {exc}")
        return 1

    try:
        source_ids = determine_source_ids(manifest, args)
    except ManifestError as exc:
        print(f"参数错误: {exc}")
        return 1

    if not source_ids:
        print("无可下载的 source")
        return 0

    session = requests.Session()
    success = True
    for source_id in source_ids:
        try:
            source = manifest.source_for(source_id)
        except ManifestError as exc:
            print(f"配置错误: {exc}")
            success = False
            continue
        if source.type != "remote":
            continue
        dest = resolve_destination(manifest, source)
        try:
            download_source(session, source, dest, timeout=args.timeout, dry_run=args.dry_run)
        except ManifestError as exc:
            print(exc)
            success = False
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
