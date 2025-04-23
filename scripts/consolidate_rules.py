import requests
import yaml
import os
import re
import shutil
import argparse
import json
from collections import defaultdict
from urllib.parse import urlparse
from datetime import datetime
import time

# --- 配置 ---

# 定义规则分类及其源本地文件路径
# 格式: '目标文件名 (无扩展名)': { 'urls': ['path1', 'path2', ...], 'merge': True/False }
# merge: True 表示合并所有源文件到 <category_name>.list
# merge: False 表示仅处理第一个源文件到 <category_name>.list (适用于单一源的情况)
RULE_CATEGORIES = {
    # --- AI 服务 ---
    'ai_all': {
        'urls': [
            'rulesets/classical/ai_all.list',
            'rulesets/custom/aioai.list',
            'rulesets/classical/skk_ai_non_ip.conf',
            'rulesets/classical/AiExtra.list',
            'rulesets/classical/Copilot.list',
            'rulesets/classical/GithubCopilot.list',
            'rulesets/classical/Claude.list',
        ],
        'merge': True
    },
    # --- 广告拦截整合 ---
    'ad_all': {
        'urls': [
            'rulesets/classical/BanAD.list',
            'rulesets/classical/BanProgramAD.list',
            'https://cdn.jsdelivr.net/gh/o0HalfLife0o/list@master/ad.txt',
            'https://easylist-downloads.adblockplus.org/easylistchina.txt',
            'https://gcore.jsdelivr.net/gh/217heidai/adblockfilters@main/rules/adblockdns.txt',
        ],
        'merge': True
    },
    # --- 直连规则整合 ---
    'direct_all': {
        'urls': [
            'rulesets/classical/LocalAreaNetwork.list',
            'rulesets/classical/GoogleCN.list',
            'rulesets/classical/SteamCN.list',
            'rulesets/classical/ChinaMedia.yaml',
            'rulesets/classical/Tencent.yaml',
            'rulesets/classical/LAN.yaml',
            'rulesets/classical/China.yaml',
            'rulesets/geosite/ChinaDomain.list',
        ],
        'merge': True
    },
    # --- 流媒体服务 ---
    'youtube': {
        'urls': [
            'rulesets/classical/GlobalMedia.yaml',
        ],
        'merge': False # 单一源
    },
    'netflix': {
        'urls': [
            'rulesets/classical/GlobalMedia.yaml',
        ],
        'merge': False # 单一源
    },
    'disney': {
        'urls': [
            './rulesets/classical/Disney+.yaml',
        ],
        'merge': False # 单一源
    },
    'tvb': {
        'urls': [
            './rulesets/custom/tvb.list',
        ],
        'merge': False # 单一源
    },
    # --- Apple 服务 ---
    'apple_domains': {
        'urls': [
            './rulesets/classical/Apple_classical.yaml',
        ],
        'merge': False # 单一源
    },
    # --- 微软服务 ---
    'microsoft': {
        'urls': [
            './rulesets/classical/Microsoft_classical.yaml',
            './rulesets/classical/Onedrive_classical.yaml',
        ],
        'merge': True
    },
    # --- GitHub ---
    'github': {
        'urls': [
            './rulesets/classical/Github_classical.yaml',
        ],
        'merge': False # 单一源
    },
    # --- Telegram ---
    'telegram': {
        'urls': [
            './rulesets/classical/Telegram_classical.yaml',
        ],
        'merge': False # 单一源
    },
    # --- 游戏平台 ---
    'gaming': {
        'urls': [
            './rulesets/classical/Nintendo.yaml',
            './rulesets/classical/PlayStation.yaml',
            './rulesets/classical/Epic.yaml',
            './rulesets/classical/Xbox.yaml',
        ],
        'merge': True
    },
    # --- Surge 使用的独立列表 ---
    'GoogleFCM': {
        'urls': ['./rulesets/classical/GoogleFCM.list'],
        'merge': False
    },
    'BiliBili': {
        'urls': ['./rulesets/classical/blackmatrix7_BiliBili.list'],
        'merge': False
    },
    # --- PCDN 拦截 ---
    'ban_pcdn': {
        'urls': [
            'https://cdn.jsdelivr.net/gh/susetao/PCDNFilter-CHN-@main/PCDNFilter.txt',
            'https://thhbdd.github.io/Block-pcdn-domains/ban.txt',
        ],
        'merge': True
    },
    # --- 以下是原配置中定义但 Surge 配置未使用的，已注释/删除 ---
    # 'reject_domains': {...},
    # 'direct_ips': {...},
    # 'spotify': {...},
    # 'tiktok': {...},
    # 'proxy_common': {...},
    # 'Cloudflare': {...},
}

# 定义输出目录
OUTPUT_DIR_CLASSICAL = "rulesets/classical"
OUTPUT_DIR_CUSTOM = "rulesets/custom" # 自定义规则目录 (仅用于输入)
STATS_FILE = "rule_stats.json"  # 统计信息文件

# --- 工具函数 ---

def clean_output_directories():
    """清空输出目录中由本脚本生成的文件，保留 custom 和其他非脚本生成文件"""
    print(f"尝试清理目录: {OUTPUT_DIR_CLASSICAL} 中由脚本生成的文件...")
    cleaned_count = 0
    errors = 0
    if os.path.exists(OUTPUT_DIR_CLASSICAL):
        try:
            # 只删除 RULE_CATEGORIES 中定义的输出文件
            generated_files = {f"{category}.list" for category in RULE_CATEGORIES.keys()}
            for filename in os.listdir(OUTPUT_DIR_CLASSICAL):
                if filename in generated_files:
                    file_path = os.path.join(OUTPUT_DIR_CLASSICAL, filename)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                            cleaned_count += 1
                    except Exception as e:
                        print(f"删除文件 {file_path} 失败: {e}")
                        errors += 1
            if errors == 0:
                print(f"成功清理 {cleaned_count} 个由脚本生成的规则文件。")
            else:
                print(f"清理完成，清理了 {cleaned_count} 个文件，遇到 {errors} 个错误。")
        except Exception as e:
            print(f"清理目录 {OUTPUT_DIR_CLASSICAL} 时发生错误: {e}")
    else:
        print(f"创建目录: {OUTPUT_DIR_CLASSICAL}")
        os.makedirs(OUTPUT_DIR_CLASSICAL, exist_ok=True)

    # 确保 custom 目录存在
    if not os.path.exists(OUTPUT_DIR_CUSTOM):
        print(f"创建目录: {OUTPUT_DIR_CUSTOM}")
        os.makedirs(OUTPUT_DIR_CUSTOM, exist_ok=True)

def read_local_file_content(file_path):
    """读取本地文件内容，返回文本。"""
    # 规范化相对路径，确保它相对于项目根目录
    if not os.path.isabs(file_path):
        # 获取脚本所在目录的父目录（项目根目录）
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if '__file__' in globals() else os.getcwd()
        abs_path = os.path.normpath(os.path.join(script_dir, file_path))
    else:
        abs_path = file_path

    if not os.path.exists(abs_path):
        print(f"警告: 本地文件 {abs_path} (源路径: {file_path}) 不存在")
        return None
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except UnicodeDecodeError:
        # 尝试其他编码
        for enc in ['gbk', 'gb2312', 'big5']:
            try:
                with open(abs_path, 'r', encoding=enc) as f:
                    content = f.read()
                return content
            except UnicodeDecodeError:
                continue
        print(f"错误: 无法解码本地文件 {abs_path} 的内容")
        return None
    except Exception as e:
        print(f"读取本地文件 {abs_path} 失败: {e}")
        return None

def fetch_url_content(url):
    """从 URL 下载内容，返回文本。"""
    print(f"  正在下载: {url} ...")
    try:
        response = requests.get(url, timeout=30) # 增加超时
        response.raise_for_status() # 检查 HTTP 错误
        # 尝试使用 UTF-8 解码，如果失败则让 requests 自动检测
        try:
            content = response.content.decode('utf-8')
        except UnicodeDecodeError:
            response.encoding = response.apparent_encoding # 让 requests 猜测编码
            content = response.text
        return content
    except requests.exceptions.RequestException as e:
        print(f"错误: 下载 URL {url} 失败: {e}")
        return None
    except Exception as e:
        print(f"错误: 处理 URL {url} 时发生未知错误: {e}")
        return None

def parse_list_content(content):
    """解析 .list/.txt/.conf 文件内容，提取域名模式，并转换为 Surge 格式 (超严格模式 + 白名单)。"""
    rules = set()
    # --- 白名单定义 ---
    # 这些域名及其所有子域名不会被此列表屏蔽
    whitelisted_domains = {
        "github.com",
        "notion.so",
        # 可以根据需要添加更多核心域名
        # "google.com",
        # "apple.com",
        # "microsoft.com",
        # "icloud.com",
    }

    if content is None:
        return rules
    lines = content.splitlines()
    for line in lines:
        line = line.strip()
        # 移除注释和空行
        if not line or line.startswith(('#', '!', ';')):
            continue

        # 忽略 ABP 元素隐藏/注入规则
        if '##' in line or '#?#' in line or '#@#' in line:
            continue

        # 忽略包含 ABP 选项/修饰符的规则
        if '$' in line:
            continue

        # --- 移除对 URL-REGEX 的处理 ---
        # if line.startswith('/') and line.endswith('/'):
        #     continue

        # --- 处理 AdGuard/ABP 域名规则: ||domain.com^ 或 ||domain.com ---
        if line.startswith('||'):
            domain_part = line[2:].rstrip('^')
            if not domain_part or '$' in domain_part: # 跳过空的或仍包含修饰符的
                continue

            # --- 白名单检查 ---
            is_whitelisted = False
            # 检查是否是白名单域名本身或其子域名
            normalized_domain = domain_part.lstrip('*.') # 去掉通配符和前导点进行检查
            for w_domain in whitelisted_domains:
                if normalized_domain == w_domain or normalized_domain.endswith('.' + w_domain):
                    # print(f"  跳过白名单规则: {line} (匹配 {w_domain})") # 调试时开启
                    is_whitelisted = True
                    break
            if is_whitelisted:
                continue
            # --- 白名单检查结束 ---

            # 简单的域名/关键词验证 (允许 *)
            if re.match(r"^[a-zA-Z0-9.\-\*]+$", domain_part):
                if '*' in domain_part:
                    keyword = domain_part.lstrip('.')
                    # 进一步过滤过于宽泛的关键词？例如，太短的？
                    if len(keyword) > 2: # 避免像 *, a*, etc. 这样太短的关键词
                         rules.add(f"DOMAIN-KEYWORD,{keyword}")
                else:
                    # 确保不是纯 IP 地址
                    if not re.match(r"^(\d{1,3}\.){3}\d{1,3}$", domain_part):
                         rules.add(f"DOMAIN-SUFFIX,{domain_part}")
            continue # 处理完 || 规则就继续下一行

        # --- 处理已有的 Surge/Clash 格式规则 (保留) ---
        rule = line.split('#')[0].split('//')[0].strip()
        if rule:
            parts = rule.split(',')
            if len(parts) > 1 and parts[0].isupper() and '-' in parts[0]:
                 if re.match(r"^[A-Z\-]+$", parts[0]):
                    # --- 对已有的 Surge 规则也做白名单检查？ ---
                    # 例如，如果规则是 DOMAIN-SUFFIX,api.github.com，也应该跳过
                    value_part = parts[1].strip()
                    is_whitelisted = False
                    for w_domain in whitelisted_domains:
                        if value_part == w_domain or value_part.endswith('.' + w_domain):
                            # print(f"  跳过白名单 Surge/Clash 规则: {rule} (匹配 {w_domain})") # 调试时开启
                            is_whitelisted = True
                            break
                    if not is_whitelisted:
                        rules.add(rule)
                    # else: # 规则值在白名单内，跳过
                    #    pass

    return rules

def parse_yaml_content(content):
    """解析 YAML 文件内容 (主要是 blackmatrix7 的格式)，提取 payload"""
    rules = set()
    if content is None:
        return rules
    try:
        # 尝试移除 YAML 文件头部的注释和空行
        cleaned_content_lines = []
        in_payload = False
        for line in content.splitlines():
            stripped_line = line.strip()
            if stripped_line.startswith('payload:'):
                in_payload = True
            if not stripped_line or stripped_line.startswith('#'):
                 # 保留 payload 块内的注释行（如果需要）？当前不保留
                continue
            cleaned_content_lines.append(line)

        cleaned_content = "\n".join(cleaned_content_lines)

        # 添加必要的 YAML 结构以帮助解析列表
        if not cleaned_content.strip().startswith('payload:'):
             # 如果 payload 不在顶层，尝试查找
            if 'payload:' in cleaned_content:
                 # 尝试从 payload 开始解析
                 payload_start_index = cleaned_content.find('payload:')
                 cleaned_content = cleaned_content[payload_start_index:]
            else:
                # 假设整个内容就是规则列表，尝试包装
                cleaned_content = "payload:\n" + "\n".join([f"  - '{line.strip()}'" for line in cleaned_content.splitlines() if line.strip()])


        data = yaml.safe_load(cleaned_content)

        if isinstance(data, dict) and 'payload' in data and isinstance(data['payload'], list):
            for item in data['payload']:
                item_str = str(item).strip() # 转换为字符串并清理
                if item_str and not item_str.startswith('#'):
                    # 去除行尾注释
                    item_str = item_str.split('#')[0].strip()
                    if item_str: # 再次检查非空
                        # 基本的域名/IP/关键词验证 (非常宽松)
                        # 允许规则包含空格
                        if re.match(r"^[a-zA-Z0-9\.\-\_\:\/\*\+\,\s]+$", item_str):
                            rules.add(item_str)
                        # else:
                        #      print(f"  跳过YAML中疑似无效规则: {item_str}") # 调试时开启
        elif isinstance(data, list): # 如果直接解析出列表
             for item in data:
                item_str = str(item).strip()
                if item_str and not item_str.startswith('#'):
                    item_str = item_str.split('#')[0].strip()
                    if item_str:
                         if re.match(r"^[a-zA-Z0-9\.\-\_\:\/\*\+\,\s]+$", item_str):
                            rules.add(item_str)
                        # else:
                        #      print(f"  跳过YAML列表中疑似无效规则: {item_str}") # 调试时开启
        else:
            # 如果解析失败或结构不符，尝试按行解析作为后备
            print(f"警告: YAML内容 {type(data)} 不符合预期结构，尝试按行解析...")
            rules.update(parse_list_content(content)) # 使用 list 解析器作为后备

    except yaml.YAMLError as e:
        print(f"错误: 解析YAML内容失败: {e}, 尝试按行解析...")
        # 如果YAML解析失败，尝试将其视为普通列表文件
        rules.update(parse_list_content(content))
    except Exception as e:
        print(f"处理YAML时发生意外错误: {e}")
        rules.update(parse_list_content(content))
    return rules

def write_rules_to_file(rules, output_path):
    """将规则集合写入文件，每行一条"""
    # 确保目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    try:
        # 按字母顺序排序写入，增加可读性
        sorted_rules = sorted(list(rules))
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Rule count: {len(sorted_rules)}\n")
            f.write(f"# Generated by consolidate_rules.py\n")
            f.write(f"# Last updated: {datetime.now().isoformat()}\n")
            for rule in sorted_rules:
                f.write(rule + '\n')
        # print(f"成功写入 {len(sorted_rules)} 条规则到 {output_path}") # 由调用者打印
        return len(sorted_rules)
    except IOError as e:
        print(f"错误: 写入 {output_path} 失败: {e}")
        return 0
    except Exception as e:
        print(f"写入文件 {output_path} 时发生意外错误: {e}")
        return 0

def load_existing_rules(file_path):
    """加载现有规则文件中的规则，跳过注释行"""
    rules = set()
    if not os.path.exists(file_path):
        return rules

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                rules.add(line)
        return rules
    except Exception as e:
        print(f"加载现有规则文件 {file_path} 时出错: {e}")
        return set()

def process_local_file(file_path):
    """处理单个本地文件，读取并解析内容"""
    print(f"  处理本地文件: {file_path}...")
    try:
        content = read_local_file_content(file_path)
        if content is None:
            print(f"  警告: 无法从 {file_path} 获取内容，跳过...")
            return set()

        # 根据文件扩展名猜测类型
        if file_path.endswith('.yaml') or file_path.endswith('.yml'):
            # print(f"  解析为YAML...")
            return parse_yaml_content(content)
        elif file_path.endswith('.list') or file_path.endswith('.txt') or file_path.endswith('.conf'):
            # print(f"  解析为LIST/TXT/CONF...")
            return parse_list_content(content)
        else: # 默认按 .list 处理
            print(f"  警告: 未知文件类型 {file_path}, 尝试按 LIST/TXT 解析...")
            return parse_list_content(content)
    except Exception as e:
        print(f"  处理本地文件 {file_path} 时出错: {e}")
        return set()

def load_stats():
    """加载统计信息"""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载统计文件失败: {e}")
    return {
        "last_update": None,
        "categories": {}
    }

def save_stats(stats):
    """保存统计信息"""
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        print(f"统计信息已保存到 {STATS_FILE}")
    except Exception as e:
        print(f"保存统计信息失败: {e}")

# --- 主逻辑 ---

def process_category(category, config, existing_rules=None):
    """处理单个分类的规则，从源列表（本地文件或 URL）读取。"""
    print(f"\n处理分类: {category}...")
    category_rules = set()
    sources = config.get('urls', []) # 现在 urls 可以包含本地路径或 URL
    should_merge = config.get('merge', True)

    if not sources:
        print(f"警告: 分类 {category} 没有定义源")
        return category_rules, 0

    source_count = 0
    processed_count = 0
    for source in sources:
        source_count += 1
        rules_from_source = set()
        content = None

        # 判断是 URL 还是本地文件
        if source.startswith('http://') or source.startswith('https://'):
            content = fetch_url_content(source)
            if content is None:
                print(f"  警告: 无法从 URL {source} 获取内容，跳过...")
                continue # 跳过这个源
            # 根据内容（或假定为 list/txt）解析
            # 注意：目前 URL 只支持 list/txt/conf 类型解析
            # 如果需要支持从 URL 加载 YAML，需要增加逻辑
            rules_from_source = parse_list_content(content)
            # print(f"  从 URL {source} 解析...") # 减少冗余输出
        else:
            # 本地文件处理逻辑 (复用 process_local_file)
            rules_from_source = process_local_file(source)
            # process_local_file 内部会打印日志，这里不再重复

        if rules_from_source:
            source_display_name = source if source.startswith('http') else os.path.basename(source)
            print(f"  从 {source_display_name} 获取到 {len(rules_from_source)} 条规则")
            category_rules.update(rules_from_source)
            processed_count += 1
        # else: # 函数内部已打印警告
        #     print(f"  警告: 从 {source} 提取的规则为空或处理失败")

        # 如果不合并，只处理第一个源
        if not should_merge and processed_count > 0: # 确保至少成功处理了一个
            break

    if source_count > 0 and processed_count == 0:
        print(f"警告: 分类 {category} 的所有源均未成功处理或为空。")

    # 合并后进行比较
    new_rules_count = 0
    if existing_rules is not None:
        new_rules = category_rules - existing_rules
        removed_rules = existing_rules - category_rules
        unchanged_rules = category_rules.intersection(existing_rules)
        new_rules_count = len(new_rules)

        print(f"分类 '{category}' 对比:")
        print(f"  - 总规则数: {len(category_rules)} (之前: {len(existing_rules)})")
        if new_rules_count > 0:
            print(f"  - 新增规则: {new_rules_count}")
        if len(removed_rules) > 0:
             print(f"  - 移除规则: {len(removed_rules)}")
        # print(f"  - 未变规则: {len(unchanged_rules)}") # 信息过多，默认隐藏

    else:
        # 首次创建
        new_rules_count = len(category_rules)
        print(f"分类 '{category}' 首次生成，总计独立规则: {new_rules_count}")

    return category_rules, new_rules_count # 返回处理后的完整规则集 和 新增数量

def write_category_rules(category, rules, output_dir):
    """将分类规则写入文件"""
    output_filename = f"{category}.list" # 始终使用 .list 扩展名
    output_path = os.path.join(output_dir, output_filename)
    return write_rules_to_file(rules, output_path)

def create(categories=None):
    """创建规则文件"""
    if categories is None:
        categories = RULE_CATEGORIES.keys()

    stats = load_stats()
    if stats["last_update"] is None:
        stats["last_update"] = datetime.now().isoformat()

    all_processed_rules = {}
    total_rules = 0

    for category in categories:
        if category not in RULE_CATEGORIES:
            print(f"错误: 未知分类 '{category}'")
            continue

        config = RULE_CATEGORIES[category]
        # 注意：create 时不传入 existing_rules
        rules, rule_count = process_category(category, config)
        all_processed_rules[category] = rules

        if category not in stats["categories"]:
            stats["categories"][category] = {"rule_count": 0, "last_updated": None}

        stats["categories"][category]["rule_count"] = len(rules)
        stats["categories"][category]["last_updated"] = datetime.now().isoformat()

        total_rules += len(rules)

    # 写入规则文件
    write_rules(all_processed_rules)

    message = f"总计创建 {total_rules} 条规则"
    print(f"\n{message}")
    stats["last_update"] = datetime.now().isoformat()
    save_stats(stats)

    return message

def read(category=None):
    """读取规则文件"""
    stats = load_stats()

    if category is None:
        # 列出所有类别及其规则数量
        print("\n规则统计信息:")
        if not stats["categories"]:
             print("  无可用统计信息。请先运行 'create' 或 'update'。")
             return
        for cat, info in stats["categories"].items():
            print(f"  {cat}: {info['rule_count']} 条规则 (最后更新: {info.get('last_updated', '未知')})")
    else:
        if category not in stats["categories"] and category not in RULE_CATEGORIES:
            print(f"错误: 分类 '{category}' 不存在或未定义")
            return

        # 读取并显示特定类别的规则文件
        output_dir = OUTPUT_DIR_CLASSICAL
        output_filename = f"{category}.list"
        output_path = os.path.join(output_dir, output_filename)

        if not os.path.exists(output_path):
            print(f"错误: 文件 {output_path} 不存在")
            # 尝试从 stats 获取数量
            count_from_stats = stats.get("categories", {}).get(category, {}).get("rule_count", "未知")
            print(f"根据统计，分类 '{category}' 应有 {count_from_stats} 条规则。")
            return

        rules = load_existing_rules(output_path)
        print(f"\n分类 '{category}' (文件: {output_path}) 包含 {len(rules)} 条规则:")
        # 限制输出数量，避免刷屏
        max_lines_to_show = 50
        rules_list = sorted(rules)
        for i, rule in enumerate(rules_list):
             if i < max_lines_to_show:
                 print(f"  {rule}")
             elif i == max_lines_to_show:
                 print(f"  ... (还有 {len(rules_list) - max_lines_to_show} 条规则未显示)")
                 break

def update(categories=None):
    """更新规则文件"""
    if categories is None:
        categories = RULE_CATEGORIES.keys()

    stats = load_stats()
    all_processed_rules = {}
    total_updated_rules = 0 # 计算更新的总规则数，而非新增
    category_changes = []

    print("开始更新规则...")

    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR_CLASSICAL, exist_ok=True)

    for category in categories:
        if category not in RULE_CATEGORIES:
            print(f"错误: 未知分类 '{category}'，跳过")
            continue

        config = RULE_CATEGORIES[category]
        output_dir = OUTPUT_DIR_CLASSICAL # 所有规则都写入 classical 目录
        output_filename = f"{category}.list"
        output_path = os.path.join(output_dir, output_filename)

        # 加载现有规则用于比较
        existing_rules = load_existing_rules(output_path)
        old_count = len(existing_rules)

        # 处理规则（读取本地文件、解析、合并）
        rules, new_rule_count = process_category(category, config, existing_rules)
        all_processed_rules[category] = rules
        new_count = len(rules)
        total_updated_rules += new_count # 累加最终规则数

        if category not in stats["categories"]:
            stats["categories"][category] = {"rule_count": 0, "last_updated": None}

        stats["categories"][category]["rule_count"] = new_count
        stats["categories"][category]["last_updated"] = datetime.now().isoformat()

        # 检查是否有变化：规则数量变化 或 实际规则内容变化（通过比较集合哈希值可能更精确，但当前实现基于数量和new_rule_count）
        # 即使 new_rule_count 为 0，数量也可能因规则移除而改变
        if old_count != new_count or new_rule_count > 0:
            change_desc = f"{old_count}→{new_count}"
            diff = new_count - old_count
            if diff != 0:
                 change_desc += f" ({'+' if diff > 0 else ''}{diff})"
            # if new_rule_count > 0 and diff == 0: # 如果只有新增但总数不变（即同时有移除）
            #      change_desc += f" (内容变化)" # 简化描述
            category_changes.append(f"{category}: {change_desc}")
        # else:
             # print(f"分类 '{category}' 无变化.") # 可选：打印无变化信息

    # 写入规则文件
    write_rules(all_processed_rules)

    change_details = "，".join(category_changes) if category_changes else "无变化"
    message = f"规则更新完成。共处理 {len(categories)} 个类别，总规则数 {total_updated_rules}。变化详情: {change_details}"
    print(f"\n{message}")
    stats["last_update"] = datetime.now().isoformat()
    save_stats(stats)

    return message

def delete(categories=None):
    """删除规则文件"""
    if categories is None:
        print("错误: 必须指定要删除的分类")
        return "错误: 未指定删除分类"

    stats = load_stats()
    deleted_count = 0
    deleted_categories = []

    for category in categories:
        output_dir = OUTPUT_DIR_CLASSICAL
        output_filename = f"{category}.list"
        output_path = os.path.join(output_dir, output_filename)

        if os.path.exists(output_path):
            try:
                os.remove(output_path)
                print(f"已删除 {output_path}")
                deleted_count += 1
                deleted_categories.append(category)

                if category in stats["categories"]:
                    del stats["categories"][category]
            except Exception as e:
                print(f"删除 {output_path} 失败: {e}")
        else:
            print(f"文件 {output_path} 不存在，无需删除")

    message = f"总计删除 {deleted_count} 个规则文件: {', '.join(deleted_categories)}"
    print(f"\n{message}")
    if deleted_count > 0:
        stats["last_update"] = datetime.now().isoformat()
        save_stats(stats)

    return message

def write_rules(all_processed_rules):
    """写入所有规则文件，文件名基于分类键"""
    print("\n写入规则文件...")
    written_files = 0
    total_rules_written = 0
    for category, rules in all_processed_rules.items():
        # 跳过没有规则内容的分类，避免创建空文件
        if not rules:
            print(f"跳过空分类: {category}")
            continue

        config = RULE_CATEGORIES.get(category, {}) # Get config for this category
        output_dir = OUTPUT_DIR_CLASSICAL # 所有文件写入 classical 目录

        # 使用 category key 作为文件名
        output_filename = f"{category}.list" # 统一使用 .list 扩展名
        output_path = os.path.join(output_dir, output_filename)

        count = write_rules_to_file(rules, output_path)
        if count > 0:
            print(f"分类 '{category}' 已写入 {count} 条规则到 {output_path}")
            written_files += 1
            total_rules_written += count
        else:
            print(f"写入分类 '{category}' 失败或为空")

    print(f"\n总计写入 {written_files} 个规则文件，共 {total_rules_written} 条规则。")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='规则整合工具 (本地文件处理)')
    parser.add_argument('action', choices=['create', 'read', 'update', 'delete'], help='要执行的操作: create (强制重新生成), read (读取统计或分类), update (更新规则), delete (删除分类规则)')
    parser.add_argument('--categories', nargs='+', help='要处理的分类 (默认全部)', default=None)
    parser.add_argument('--clean', action='store_true', help='在 create 或 update 前清理由本脚本生成的 rulesets/classical 文件')
    parser.add_argument('--notify', action='store_true', help='完成后发送Bark通知 (需要配置BARK_URL环境变量)')

    args = parser.parse_args()

    if args.clean:
        # 清理只应该在 create 或 update 时执行
        if args.action in ['create', 'update']:
            clean_output_directories()
        else:
            print("警告: --clean 标志仅在 'create' 或 'update' 操作时生效。")

    result_message = ""
    start_time = datetime.now()

    # 确保输出目录存在（如果 clean 没有执行）
    if not args.clean and args.action in ['create', 'update']:
         os.makedirs(OUTPUT_DIR_CLASSICAL, exist_ok=True)
         # os.makedirs(OUTPUT_DIR_CUSTOM, exist_ok=True) # Custom 目录不需要脚本创建

    if args.action == 'create':
        # Create 强制重新生成所有指定的（或全部）分类
        print("执行 'create' 操作，将从本地文件重新生成规则...")
        result_message = create(args.categories)
    elif args.action == 'read':
        # Read 读取统计信息或特定分类的内容
        read(args.categories[0] if args.categories else None) # read 只接受一个分类名或None
        result_message = "读取操作完成。" # Read 操作通常不需要通知消息
    elif args.action == 'update':
        # Update 检查更新并写入变化的分类
        print("执行 'update' 操作，将检查并更新规则...")
        result_message = update(args.categories)
    elif args.action == 'delete':
        # Delete 删除指定的分类文件
        if not args.categories:
            parser.error("delete 操作需要通过 --categories 指定至少一个分类")
        print(f"执行 'delete' 操作，将删除指定的分类规则文件: {args.categories}...")
        result_message = delete(args.categories)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print(f"\n规则处理操作 '{args.action}' 已完成。用时: {duration:.2f} 秒")

    # 发送推送通知 (仅对 create, update, delete 发送有意义的消息)
    if args.notify and args.action in ['create', 'update', 'delete'] and result_message:
        title = f"规则合并 - {args.action.capitalize()}"
        # 对于 update，使用更详细的 result_message
        if args.action == 'update':
            content = f"{result_message}\n用时: {duration:.2f}秒"
        elif args.action == 'create':
             content = f"规则已重新创建。\n{result_message}\n用时: {duration:.2f}秒"
        elif args.action == 'delete':
             content = f"{result_message}\n用时: {duration:.2f}秒"

        send_bark_notification(title, content)
    elif os.environ.get('CI') == 'true' and args.action in ['create', 'update', 'delete'] and result_message:
        # 在 CI 环境下，即使没有 --notify 也尝试发送通知
        title = f"规则合并 CI - {args.action.capitalize()}"
        content = f"{result_message}\n用时: {duration:.2f}秒"
        print("CI 环境，尝试发送 Bark 通知...")
        send_bark_notification(title, content)

# Bark推送功能 (保持不变)
def send_bark_notification(title, content):
    """
    使用Bark发送通知
    """
    bark_url = os.environ.get('BARK_URL')
    if not bark_url:
        print("未设置BARK_URL环境变量，跳过推送")
        return False

    # 尝试对内容进行 URL 编码，避免特殊字符问题
    from urllib.parse import quote
    # Bark 对路径参数的编码要求可能不同，有时不需要二次编码
    # encoded_content = quote(content) # 尝试不编码或仅编码特殊字符

    # Bark URL 通常格式为 https://api.day.app/YOUR_KEY/[title]/[body]
    # 尝试直接拼接，让 requests 处理编码
    try:
        # 保持 title 不编码，content 编码
        # full_url = f"{bark_url.rstrip('/')}/{quote(title)}/{quote(content)}"
        # 或者尝试 POST 请求，将 title 和 body 放入 data
        push_url = bark_url.rstrip('/') + '/'
        data = {
            'title': title,
            'body': content,
            # 可以添加其他 Bark 参数，如 'group', 'icon', 'url' 等
            # 'group': '规则同步'
        }
        # 添加超时设置和重试机制
        for attempt in range(3):  # 最多尝试3次
            try:
                # 使用 POST 发送
                response = requests.post(push_url, json=data, timeout=15) # 使用 json 参数
                # response = requests.get(full_url, timeout=15) # 如果用GET

                # Bark 成功响应通常是 200 OK，并返回 JSON
                if response.status_code == 200:
                    try:
                        result = response.json()
                        if result.get('code') == 200:
                            print(f"Bark推送成功: {title}")
                            return True
                        else:
                            print(f"Bark推送失败 (API返回错误): {result.get('message', response.text)}")
                            # 非服务器错误，不重试
                            return False
                    except json.JSONDecodeError:
                        print(f"Bark推送失败 (非JSON响应): {response.status_code}, {response.text}")
                        return False # 可能 URL 错误或 Bark 服务问题，不重试
                else:
                    print(f"Bark推送失败 (HTTP状态码): {response.status_code}, {response.text}")
                    # 如果是服务器错误(5xx)，等待后重试
                    if 500 <= response.status_code < 600 and attempt < 2:
                        print(f"等待3秒后重试... (尝试 {attempt+1}/3)")
                        time.sleep(3)
                        continue
                    return False
            except requests.Timeout:
                print(f"Bark推送超时 (尝试 {attempt+1}/3)")
                if attempt < 2:
                    time.sleep(3)
                    continue
                return False
            except requests.RequestException as req_err:
                print(f"Bark推送请求异常: {req_err}")
                return False # 网络或请求配置问题，不重试

        print("Bark推送最终失败 (多次尝试后)")
        return False
    except Exception as e:
        print(f"Bark推送异常: {e}")
        return False

if __name__ == "__main__":
    main() 