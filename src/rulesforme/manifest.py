"""Manifest data structures and loader for RulesForMe."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml


class ManifestError(Exception):
    """Raised when the manifest file is invalid or inconsistent."""


_ALLOWED_SOURCE_TYPES = {"remote", "local"}
_ALLOWED_FORMATS = {"auto", "list", "yaml", "mrs"}
_ALLOWED_PARSERS = {"auto", "list", "yaml", "mrs"}


@dataclass
class ManifestDefaults:
    download_root: str = "rulesets"
    cache_root: str = "cache"
    encoding: str = "utf-8"

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "ManifestDefaults":
        if data is None:
            return cls()
        unexpected = set(data) - {"download_root", "cache_root", "encoding"}
        if unexpected:
            raise ManifestError(f"未知 defaults 字段: {', '.join(sorted(unexpected))}")
        return cls(**{k: data.get(k, getattr(cls(), k)) for k in ("download_root", "cache_root", "encoding")})


@dataclass
class ManifestSource:
    id: str
    type: str
    target: str
    format: str = "auto"
    critical: bool = True
    group: Optional[str] = None
    uri: Optional[str] = None
    path: Optional[str] = None

    def normalize(self) -> None:
        if self.group is None:
            self.group = self.target.split("/", 1)[0]

    def validate(self) -> None:
        if not self.id:
            raise ManifestError("source 定义缺少 id")
        if self.type not in _ALLOWED_SOURCE_TYPES:
            raise ManifestError(f"source '{self.id}' 的 type 非法: {self.type}")
        if self.format not in _ALLOWED_FORMATS:
            raise ManifestError(f"source '{self.id}' 的 format 非法: {self.format}")
        _require_relative(self.target, f"source '{self.id}' 的 target")
        if self.type == "remote":
            if not self.uri:
                raise ManifestError(f"source '{self.id}' 为 remote 但缺少 uri")
            if not _is_http_url(self.uri):
                raise ManifestError(f"source '{self.id}' 的 uri 非 http(s): {self.uri}")
        if self.type == "local":
            if not self.path:
                raise ManifestError(f"source '{self.id}' 为 local 但缺少 path")
            _require_relative(self.path, f"source '{self.id}' 的 path")
            if self.uri is not None:
                raise ManifestError(f"source '{self.id}' 为 local 不应定义 uri")
        if self.group:
            _require_relative(self.group, f"source '{self.id}' 的 group")


@dataclass
class ManifestCategory:
    output: str
    sources: List[str]
    merge: bool = True
    parser: str = "auto"

    def validate(self, known_sources: Iterable[str], name: str) -> None:
        if not self.sources:
            raise ManifestError(f"分类 '{name}' 必须指定至少一个 source")
        if self.parser not in _ALLOWED_PARSERS:
            raise ManifestError(f"分类 '{name}' 的 parser 非法: {self.parser}")
        _require_relative(self.output, f"分类 '{name}' 的 output")
        missing = [sid for sid in self.sources if sid not in known_sources]
        if missing:
            raise ManifestError(f"分类 '{name}' 引用了不存在的 source id: {', '.join(missing)}")


@dataclass
class RulesetManifest:
    version: int
    metadata: Dict[str, object]
    defaults: ManifestDefaults
    sources: Dict[str, ManifestSource] = field(default_factory=dict)
    categories: Dict[str, ManifestCategory] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict, *, base_path: Optional[Path] = None) -> "RulesetManifest":
        if not isinstance(data, dict):
            raise ManifestError("manifest 顶层结构必须是字典")
        version = data.get("version")
        if version != 1:
            raise ManifestError(f"不支持的 manifest version: {version}")
        metadata = data.get("metadata") or {}
        defaults = ManifestDefaults.from_dict(data.get("defaults"))

        raw_sources = data.get("sources")
        if not isinstance(raw_sources, list):
            raise ManifestError("sources 必须是列表")
        sources: Dict[str, ManifestSource] = {}
        for idx, item in enumerate(raw_sources):
            if not isinstance(item, dict):
                raise ManifestError(f"sources[{idx}] 不是字典")
            try:
                source = ManifestSource(
                    id=item["id"],
                    type=item["type"],
                    target=item["target"],
                    format=item.get("format", "auto"),
                    critical=item.get("critical", True),
                    group=item.get("group"),
                    uri=item.get("uri"),
                    path=item.get("path"),
                )
            except KeyError as exc:
                raise ManifestError(f"source 定义缺少字段: {exc.args[0]}") from exc
            if source.id in sources:
                raise ManifestError(f"source id 重复: {source.id}")
            source.normalize()
            source.validate()
            sources[source.id] = source

        raw_categories = data.get("categories")
        if not isinstance(raw_categories, dict):
            raise ManifestError("categories 必须是字典")
        categories: Dict[str, ManifestCategory] = {}
        for name, item in raw_categories.items():
            if not isinstance(item, dict):
                raise ManifestError(f"分类 '{name}' 定义必须是字典")
            try:
                category = ManifestCategory(
                    output=item["output"],
                    sources=list(item["sources"]),
                    merge=item.get("merge", True),
                    parser=item.get("parser", "auto"),
                )
            except KeyError as exc:
                raise ManifestError(f"分类 '{name}' 缺少字段: {exc.args[0]}") from exc
            category.validate(sources.keys(), name)
            categories[name] = category

        return cls(
            version=version,
            metadata=metadata,
            defaults=defaults,
            sources=sources,
            categories=categories,
        )

    def source_for(self, source_id: str) -> ManifestSource:
        try:
            return self.sources[source_id]
        except KeyError as exc:
            raise ManifestError(f"未找到 source: {source_id}") from exc


def _require_relative(value: str, field_label: str) -> None:
    if value.startswith("/"):
        raise ManifestError(f"{field_label} 不应为绝对路径: {value}")
    if ".." in Path(value).parts:
        raise ManifestError(f"{field_label} 不允许包含 ..: {value}")


def _is_http_url(url: str) -> bool:
    return url.startswith("https://") or url.startswith("http://")


def load_manifest(path: Path | str) -> RulesetManifest:
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise ManifestError(f"manifest 文件不存在: {manifest_path}")
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    return RulesetManifest.from_dict(data, base_path=manifest_path.parent)
