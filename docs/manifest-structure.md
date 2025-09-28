# ruleset_manifest.yaml 结构概览

```yaml
version: 1
metadata:
  description: "RulesForMe rule source manifest"
  generated_at: "2025-09-28T04:01:56Z"
defaults:
  download_root: rulesets
  cache_root: cache
  encoding: utf-8

sources:
  - id: classical_banad_list
    type: remote              # remote | local
    uri: https://...
    path: rulesets/classical/BanAD.list  # 仅 type=local 使用
    target: classical/BanAD.list         # 相对 download_root
    format: list              # list | yaml | mrs | auto
    group: classical          # 目录/逻辑分组
    critical: true            # 失败是否终止流程

categories:
  ai_all:
    output: classical/ai_all.list
    merge: true
    parser: auto
    sources:
      - classical_ai_all_list
      - classical_aiextra_list

notifications:
  - channel: bark
    env_var: BARK_URL
    enabled: true
```

## 字段说明
- `version`: Manifest 版本号。
- `metadata`: 描述与生成信息，可用于追踪。
- `defaults`:
  - `download_root`: 远程下载产物默认落地目录前缀。
  - `cache_root`: 临时缓存前缀，供未直接落在 `rulesets/` 的资源使用。
  - `encoding`: 默认文本编码（后续可扩展为对象，定义超时、重试等）。
- `sources`: 统一的规则源注册表。
  - `id`: 唯一标识，供 `categories[*].sources` 引用。
  - `type`: `remote` 表示需要下载，`local` 表示仓库内已有文件。
  - `uri`: 远程资源地址（`type=remote` 必填）。
  - `path`: 仓库内现有文件路径（`type=local` 必填）。
  - `target`: 下载后/引用时的相对路径（基于 `download_root` 或 `cache_root`）。
  - `format`: 解析 hint（`list`、`yaml`、`mrs`、`auto`）。
  - `group`: 逻辑分组，通常与 `target` 的顶级目录一致，用于归档与日志聚合。
  - `critical`: `true` 表示下载失败应终止流程，`false` 可降级为 warning。
- `categories`: 输出分类配置。
  - `output`: 最终产物相对于 `rulesets/` 的路径；合并器应生成 `<download_root>/<output>`。
  - `merge`: 是否合并所有源；`false` 表示取第一个可用源。
  - `parser`: 解析策略（当前支持 `auto` 占位）。
  - `sources`: 引用 `sources[*].id` 的列表；后续可扩展为对象以携带变换参数。
- `notifications`: 预留通知渠道配置（Phase 2/3 使用）。

> 当前 manifest 初稿位于 `config/ruleset_manifest.yaml`，与此结构保持一致；如需扩展字段，请同步更新本文档与验证脚本。
