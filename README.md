# RulesForMe

这是一个用于整合和管理Clash规则的项目，可以自动从多个来源收集、合并和去重规则，并生成可直接用于Clash的规则文件。

## 特性

- 支持从多个来源收集规则
- 自动合并和去重规则
- 支持按类别组织规则
- 提供完整的CRUD操作（创建、读取、更新、删除）
- 自动统计和记录规则数量变化
- 支持通过Bark进行更新通知
- 通过GitHub Action自动定期更新规则
- 支持MetaCubeX格式的规则文件(.mrs)

## 使用方法

### 本地使用

1. 克隆仓库：

```bash
git clone https://github.com/bendusy/RulesForMe.git
cd RulesForMe
```

2. 安装依赖：

```bash
pip install requests pyyaml
```

3. 运行脚本：

```bash
# 创建所有规则
python scripts/consolidate_rules.py create --clean

# 更新特定类别规则
python scripts/consolidate_rules.py update --categories netflix disney

# 查看规则统计信息
python scripts/consolidate_rules.py read

# 查看特定分类的规则
python scripts/consolidate_rules.py read --categories netflix

# 删除规则
python scripts/consolidate_rules.py delete --categories tiktok

# 发送更新通知
python scripts/consolidate_rules.py update --notify
```

### 参数说明

- `action`: 必须指定的操作类型，可选值为`create`、`read`、`update`、`delete`
- `--categories`: 要处理的规则分类，不指定则处理所有分类
- `--clean`: 清理输出目录，重新生成所有文件
- `--notify`: 操作完成后发送Bark通知

## 自动更新配置

本项目使用GitHub Actions进行自动更新。默认每天UTC时间3:00（北京时间11:00）自动运行。工作流程会：

1. 检出最新代码
2. 设置Python环境
3. 创建必要的目录结构
4. 下载MetaCubeX格式的规则文件(.mrs)
5. 运行Python脚本更新规则并发送通知
6. 提交并推送更改到仓库

### 配置Bark通知

1. 在GitHub仓库设置中添加Secret：
   - 名称：`BARK_URL`
   - 值：您的Bark推送URL，格式如`https://api.day.app/yourkey/`

2. 也可以在本地设置环境变量：

```bash
# Linux/Mac
export BARK_URL="https://api.day.app/yourkey/"

# Windows
set BARK_URL=https://api.day.app/yourkey/
```

如果Bark服务不稳定，脚本会尝试最多3次推送，每次超时限制为10秒，同时确保即使推送失败，规则更新流程也能继续执行。

## 规则类别

目前支持的规则类别包括：

- `reject_domains`: 广告和恶意域名拦截规则
- `direct_domains`: 国内直连域名规则
- `direct_ips`: 国内直连IP规则
- `direct_all`: 所有直连规则的合集
- 流媒体服务: `netflix`, `disney`, `youtube`, `spotify`, `tiktok`等
- 科技公司服务: `microsoft`, `github`, `telegram`等
- `gaming`: 游戏平台规则
- `proxy_common`: 通用代理规则
- `ai_domains`: AI服务规则
- `apple_domains`: 苹果服务规则

## 自定义规则

项目支持在`rulesets/custom`目录中放置自定义规则文件。此目录中的规则不会被脚本清理，便于用户添加和维护自己的规则集。

### 现有自定义规则

- `aioai.list`: AI服务相关域名规则，包括OpenAI、Google AI、Claude等
- `notion.list`: Notion工作区及依赖服务的域名规则
- `WeChat.list`: 微信及相关服务的域名规则
- `tvb.list`: TVB流媒体服务的域名规则
- `ArgoTunnel.list`: Cloudflare Argo Tunnel服务的域名规则

### 添加自定义规则

1. 将您的规则文件放入`rulesets/custom`目录
2. 在`scripts/consolidate_rules.py`中的`RULE_CATEGORIES`字典中引用该文件：

```python
'your_category': {
    'urls': [
        'rulesets/custom/your_rule.list',  # 您的自定义规则
        # 其他来源...
    ],
    'type': 'classical',
    'merge': True/False  # 是否与同类规则合并
},
```

## 自定义规则源

如需自定义规则源，请编辑`scripts/consolidate_rules.py`文件中的`RULE_CATEGORIES`字典。

## 故障排除

### GitHub Actions 权限问题

如果遇到GitHub Actions执行失败，提示"Permission denied"或"403 Forbidden"错误，请检查：

1. 确保工作流文件中包含以下权限配置：
```yaml
permissions:
  contents: write
```

2. 检查仓库的Actions权限设置：Settings > Actions > General > Workflow permissions

### Bark通知失败

如果Bark通知失败，可能是因为：

1. Bark服务器暂时不可用或网络问题
2. `BARK_URL`环境变量未正确设置
3. URL格式不正确

本项目已实现了通知失败的容错处理，确保即使通知失败，规则更新也能正常完成。如果Bark服务持续不稳定，可以考虑更换为其他通知服务。

## 许可

MIT License
