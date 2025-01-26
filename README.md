# RulesForMe
一个用于管理和配置规则的项目。

## 项目说明
RulesForMe 是一个规则配置管理工具,支持通过 .ini 文件定制不同国家/地区的规则配置。

## 文件结构
- `RFM_Online_SomeCountry.ini` - 特定国家/地区的规则配置文件
- `aioai.list` - AI 服务相关域名规则
- `google.list` - Google 服务相关域名规则
- `notion.list` - Notion 服务相关域名规则
- `WeChat.list` - 微信服务相关域名规则
- `iptv.list` - IPTV 服务相关域名规则
- `LICENSE` - 项目许可证文件
- `.gitattributes` - Git 属性配置文件

## 使用说明
1. 选择或创建对应国家/地区的 .ini 配置文件
2. 按照配置文件格式编写规则
3. 保存并应用规则配置

## 规则文件说明
- `aioai.list`: 包含 OpenAI、Google AI、Claude 等 AI 服务的域名规则
- `google.list`: Google 基础服务的域名规则
- `notion.list`: Notion 工作区及其依赖服务的域名规则
- `WeChat.list`: 微信及其相关服务的域名规则
- `iptv.list`: IPTV 流媒体服务的域名规则

## 致谢
- [ACL4SSR](https://github.com/ACL4SSR/ACL4SSR) - 提供基础规则集
- [cmliu/ACL4SSR](https://github.com/cmliu/ACL4SSR) - 提供扩展规则集
- [juewuy/ShellClash](https://github.com/juewuy/ShellClash) - 提供AI相关规则

## 许可证
本项目采用 MIT 许可证，详细信息请参见 [LICENSE](LICENSE) 文件。
