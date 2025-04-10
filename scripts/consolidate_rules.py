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

# 定义规则分类及其源 URL
# 格式: '目标文件名': { 'urls': ['url1', 'url2', ...], 'type': 'domain'/'ipcidr'/'classical', 'merge': True/False }
# merge 参数现在控制是否将此分类下的所有URL合并到一个以此分类名命名的文件中。
# True: 所有URL内容合并去重后写入 <category_name>.list
# False: (通常不推荐，除非特定需要) 理论上可以为每个URL单独创建文件，但当前实现仍合并到 <category_name>.list
RULE_CATEGORIES = {
    # --- REJECT 类 ---
    'reject_domains': {
        'urls': [
            'https://testingcf.jsdelivr.net/gh/ACL4SSR/ACL4SSR@master/Clash/BanAD.list',
            'https://raw.githubusercontent.com/Loyalsoldier/v2ray-rules-dat/release/reject-list.txt', # RejectList
            'https://raw.githubusercontent.com/Steve5wutongyu6/DNSBlock/refs/heads/main/BlackList.txt',
            'https://testingcf.jsdelivr.net/gh/ACL4SSR/ACL4SSR@master/Clash/BanProgramAD.list',
            'https://raw.githubusercontent.com/cmliu/ACL4SSR/main/Clash/adobe.list', # Adobe
        ],
        'type': 'classical',
        'merge': True # Merge all reject sources into reject_domains.list
    },
    # --- DIRECT 类 (合并所有直连规则) ---
    'direct_domains': {
        'urls': [
            'https://testingcf.jsdelivr.net/gh/ACL4SSR/ACL4SSR@master/Clash/LocalAreaNetwork.list',
            'https://testingcf.jsdelivr.net/gh/ACL4SSR/ACL4SSR@master/Clash/UnBan.list',
            'https://raw.githubusercontent.com/cmliu/ACL4SSR/refs/heads/main/Clash/CFnat.list',
            'https://testingcf.jsdelivr.net/gh/ACL4SSR/ACL4SSR@master/Clash/GoogleCN.list',
            'https://testingcf.jsdelivr.net/gh/ACL4SSR/ACL4SSR@master/Clash/Ruleset/SteamCN.list',
            'https://testingcf.jsdelivr.net/gh/ACL4SSR/ACL4SSR@master/Clash/ChinaDomain.list',
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/ChinaMedia/ChinaMedia.yaml',
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Tencent/Tencent.yaml',
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Lan/Lan.yaml',
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/ChinaMax/ChinaMax_Classical.yaml',
        ],
        'type': 'classical',
        'merge': True # Merge all direct domain sources into direct_domains.list
    },
    'direct_ips': {
        'urls': [
            'https://testingcf.jsdelivr.net/gh/ACL4SSR/ACL4SSR@master/Clash/ChinaCompanyIp.list',
        ],
        'type': 'ipcidr',
        'merge': True # Merge into direct_ips.list
    },
    # --- PROXY 类 (按服务独立文件) ---
    'netflix': {
        'urls': [
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Netflix/Netflix_Classical_No_Resolve.yaml',
        ],
        'type': 'classical',
        'merge': False
    },
    'disney': {
        'urls': [
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Disney/Disney_No_Resolve.yaml',
        ],
        'type': 'classical',
        'merge': False
    },
    'youtube': {
        'urls': [
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/YouTube/YouTube_No_Resolve.yaml',
        ],
        'type': 'classical',
        'merge': False
    },
    'spotify': {
        'urls': [
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Spotify/Spotify.yaml',
        ],
        'type': 'classical',
        'merge': True # Output to spotify.list
    },
    'tiktok': {
        'urls': [
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/TikTok/TikTok_No_Resolve.yaml',
        ],
        'type': 'classical',
        'merge': True # Output to tiktok.list
    },
    # 微软服务
    'microsoft': {
        'urls': [
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Microsoft/Microsoft_No_Resolve.yaml',
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/OneDrive/OneDrive.yaml',
        ],
        'type': 'classical',
        'merge': True # Merge MS sources into microsoft.list
    },
    'github': {
        'urls': [
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/GitHub/GitHub.yaml',
        ],
        'type': 'classical',
        'merge': True # Output to github.list
    },
    # Telegram
    'telegram': {
        'urls': [
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Telegram/Telegram.yaml',
        ],
        'type': 'classical',
        'merge': True # Output to telegram.list
    },
    'gaming': {
        'urls': [
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Nintendo/Nintendo.yaml',
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/PlayStation/PlayStation.yaml',
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Epic/Epic.yaml',
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Xbox/Xbox.yaml',
        ],
        'type': 'classical',
        'merge': True # Merge gaming sources into gaming.list
    },
    # Generic Proxy Rules
    'proxy_common': {
        'urls': [
            'https://raw.githubusercontent.com/qichiyuhub/rule/refs/heads/master/ProxyLite.list',
            'https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ProxyLite.list',
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Proxy/Proxy_Classical_No_Resolve.yaml',
            'https://raw.githubusercontent.com/cmliu/ACL4SSR/main/Clash/CMBlog.list',
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Cloudflare/Cloudflare.yaml',
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Bing/Bing.yaml',
            'https://testingcf.jsdelivr.net/gh/ACL4SSR/ACL4SSR@master/Clash/Ruleset/GoogleFCM.list',
            'https://raw.githubusercontent.com/SIJULY/Rules/main/Surge/talkatone.list', # Talkatone
        ],
        'type': 'classical',
        'merge': True # Merge into proxy_common.list
    },
     # --- AI 服务类 ---
    'ai_domains': {
        'urls': [
            './rulesets/custom/aioai.list', # Keep local custom file handling
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/OpenAI/OpenAI_No_Resolve.yaml',
            'https://raw.githubusercontent.com/juewuy/ShellClash/master/rules/ai.list',
            'https://raw.githubusercontent.com/cmliu/ACL4SSR/main/Clash/Copilot.list',
            'https://raw.githubusercontent.com/cmliu/ACL4SSR/main/Clash/GithubCopilot.list',
            'https://raw.githubusercontent.com/cmliu/ACL4SSR/main/Clash/Claude.list',
        ],
        'type': 'classical',
        'merge': True # Merge AI sources into ai_domains.list
    },
    # --- Apple 服务类 ---
    'apple_domains': {
        'urls': [
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Apple/Apple_Classical_No_Resolve.yaml'
        ],
        'type': 'classical',
        'merge': False # 保持独立
    }
    # 可以根据需要添加更多分类
}

# 定义输出目录
OUTPUT_DIR_CLASSICAL = "rulesets/classical"
OUTPUT_DIR_CUSTOM = "rulesets/custom" # 自定义规则目录
STATS_FILE = "rule_stats.json"  # 统计信息文件

# --- 工具函数 ---

def clean_output_directories():
    """清空输出目录，以便重新生成所有文件，但保留custom目录中的文件"""
    # 清理classical目录
    if os.path.exists(OUTPUT_DIR_CLASSICAL):
        print(f"清理目录: {OUTPUT_DIR_CLASSICAL}")
        try:
            for filename in os.listdir(OUTPUT_DIR_CLASSICAL):
                file_path = os.path.join(OUTPUT_DIR_CLASSICAL, filename)
                if os.path.isfile(file_path) and not file_path.startswith(OUTPUT_DIR_CUSTOM): # 避免误删 custom 下的文件
                    os.unlink(file_path)
            print(f"成功清理 {OUTPUT_DIR_CLASSICAL}")
        except Exception as e:
            print(f"清理目录 {OUTPUT_DIR_CLASSICAL} 错误: {e}")
    else:
        print(f"创建目录: {OUTPUT_DIR_CLASSICAL}")
        os.makedirs(OUTPUT_DIR_CLASSICAL, exist_ok=True)

    # 仅确保custom目录存在，不清理
    if not os.path.exists(OUTPUT_DIR_CUSTOM):
        print(f"创建目录: {OUTPUT_DIR_CUSTOM}")
        os.makedirs(OUTPUT_DIR_CUSTOM, exist_ok=True)
    else:
        print(f"保留目录: {OUTPUT_DIR_CUSTOM}（不清理自定义规则）")

def download_content(url):
    """下载 URL 内容，支持重定向，返回文本。如果是本地文件路径，则直接读取。"""
    # 如果是本地文件路径
    if url.startswith('./') or os.path.isabs(url) or url.startswith('../'):
        # 规范化相对路径，确保它相对于脚本的工作目录
        if not os.path.isabs(url):
            script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
            file_path = os.path.normpath(os.path.join(script_dir, url))
        else:
            file_path = url

        if not os.path.exists(file_path):
            print(f"警告: 本地文件 {file_path} (源: {url}) 不存在")
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except UnicodeDecodeError:
            # 尝试其他编码
            for enc in ['gbk', 'gb2312', 'big5']:
                try:
                    with open(file_path, 'r', encoding=enc) as f:
                        content = f.read()
                    return content
                except UnicodeDecodeError:
                    continue
            print(f"错误: 无法解码本地文件 {file_path} 的内容")
            return None
        except Exception as e:
            print(f"读取本地文件 {file_path} 失败: {e}")
            return None

    # 如果是远程URL
    headers = {'User-Agent': 'Mozilla/5.0 Clash Rule Consolidation Script'}
    try:
        response = requests.get(url, headers=headers, timeout=60, allow_redirects=True) # 增加超时时间
        response.raise_for_status() # 如果请求失败则抛出异常
        # 尝试多种编码解码
        content = None
        # 优先尝试 UTF-8
        try:
            content = response.content.decode('utf-8')
            # print(f"Decoded {url} with utf-8")
        except UnicodeDecodeError:
            # 如果 UTF-8 失败，尝试其他常见编码
            encodings = ['gbk', 'gb2312', 'big5']
            for enc in encodings:
                try:
                    content = response.content.decode(enc)
                    # print(f"Decoded {url} with {enc}")
                    break
                except UnicodeDecodeError:
                    continue
            # 如果所有尝试都失败，记录错误
            if content is None:
                 # 最后尝试忽略错误进行解码
                try:
                    content = response.content.decode('utf-8', errors='ignore')
                    print(f"警告: 使用 'utf-8' (忽略错误) 解码 {url}")
                except Exception:
                     print(f"错误: 无法解码来自 {url} 的内容，即使忽略错误")
                     return None

        return content
    except requests.exceptions.RequestException as e:
        print(f"错误: 下载 {url} 失败: {e}")
        return None
    except Exception as e:
        print(f"意外错误，下载 {url}: {e}")
        return None

def parse_list_content(content):
    """解析 .list/.txt 文件内容，返回规则列表"""
    rules = set()
    if content is None:
        return rules
    lines = content.splitlines()
    for line in lines:
        line = line.strip()
        # 移除注释和空行
        if not line or line.startswith('#') or line.startswith('//') or line.startswith(';'):
            continue
        # 提取规则，去除行尾注释
        rule = line.split('#')[0].strip()
        # 跳过特殊指令或空规则
        if rule and not rule.startswith(('payload:', 'proxies:', 'proxy-groups:', 'rules:', 'rule-providers:')):
             # 基本的域名/IP/关键词验证 (非常宽松)
            if re.match(r"^[a-zA-Z0-9\.\-\_\:\/\*\+]+$", rule) or ',' in rule: # 允许逗号用于ipcidr等
                rules.add(rule)
            # else:
            #     print(f"  跳过疑似无效规则: {rule}") # 调试时开启
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
                        if re.match(r"^[a-zA-Z0-9\.\-\_\:\/\*\+]+$", item_str) or ',' in item_str:
                            rules.add(item_str)
                        # else:
                        #      print(f"  跳过YAML中疑似无效规则: {item_str}") # 调试时开启
        elif isinstance(data, list): # 如果直接解析出列表
             for item in data:
                item_str = str(item).strip()
                if item_str and not item_str.startswith('#'):
                    item_str = item_str.split('#')[0].strip()
                    if item_str:
                        if re.match(r"^[a-zA-Z0-9\.\-\_\:\/\*\+]+$", item_str) or ',' in item_str:
                            rules.add(item_str)
                        # else:
                        #      print(f"  跳过YAML列表中疑似无效规则: {item_str}") # 调试时开启
        else:
            # 如果解析失败或结构不符，尝试按行解析作为后备
            print(f"警告: YAML内容不符合预期结构，尝试按行解析...")
            rules.update(parse_list_content(content)) # 使用 list 解析器作为后备

    except yaml.YAMLError as e:
        print(f"错误: 解析YAML内容失败: {e}, 尝试按行解析...")
        # 如果YAML解析失败，尝试将其视为普通列表文件
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
            f.write(f"# Last updated: {datetime.now().isoformat()}\n")
            for rule in sorted_rules:
                f.write(rule + '\n')
        # print(f"成功写入 {len(sorted_rules)} 条规则到 {output_path}") # 由调用者打印
        return len(sorted_rules)
    except IOError as e:
        print(f"错误: 写入 {output_path} 失败: {e}")
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

def process_url(url):
    """处理单个URL，下载并解析内容"""
    print(f"  处理: {url}...")
    try:
        content = download_content(url)
        if content is None:
            print(f"  警告: 无法从 {url} 获取内容，跳过...")
            return set()

        # 根据文件扩展名或内容猜测类型
        if url.endswith('.yaml') or url.endswith('.yml'):
            # print(f"  解析为YAML...")
            return parse_yaml_content(content)
        # elif url.endswith('.list') or url.endswith('.txt'):
        #     # print(f"  解析为LIST/TXT...")
        #     return parse_list_content(content)
        else: # 默认按 .list/.txt 处理，或者如果YAML解析失败后也会走到这里
            # print(f"  默认解析为LIST/TXT...")
            return parse_list_content(content)
    except Exception as e:
        print(f"  处理URL {url} 时出错: {e}")
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
    """处理单个分类的规则"""
    print(f"\n处理分类: {category}...")
    category_rules = set()
    urls = config.get('urls', [])

    if not urls:
        print(f"警告: 分类 {category} 没有定义URL")
        # 即使没有URL，也要检查是否存在同名的本地文件（可能已手动放置）
        output_filename = f"{category}.list"
        output_path = os.path.join(OUTPUT_DIR_CLASSICAL, output_filename)
        if os.path.exists(output_path):
             print(f"  发现已存在的本地文件: {output_path}，加载其内容...")
             local_rules = load_existing_rules(output_path)
             category_rules.update(local_rules)
             print(f"  从本地文件 {output_path} 加载了 {len(local_rules)} 条规则")
        return category_rules, 0

    for url in urls:
        rules_from_url = process_url(url)
        if rules_from_url:
            print(f"  从 {url} 获取到 {len(rules_from_url)} 条规则")
            category_rules.update(rules_from_url)
        # else: # 不再打印空规则的警告，process_url内部会打印错误
        #     print(f"  警告: 从 {url} 提取的规则为空")

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
        for cat, info in stats["categories"].items():
            print(f"  {cat}: {info['rule_count']} 条规则 (最后更新: {info.get('last_updated', '未知')})")
    else:
        if category not in stats["categories"]:
            print(f"错误: 分类 '{category}' 不存在")
            return
            
        # 读取并显示特定类别的规则文件
        output_dir = OUTPUT_DIR_CLASSICAL
        output_filename = f"{category}.list"
        output_path = os.path.join(output_dir, output_filename)
        
        if not os.path.exists(output_path):
            print(f"错误: 文件 {output_path} 不存在")
            return
            
        rules = load_existing_rules(output_path)
        print(f"\n分类 '{category}' 包含 {len(rules)} 条规则:")
        for rule in sorted(rules):
            print(f"  {rule}")

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

        # 处理规则（下载、解析、合并）
        rules, new_rule_count = process_category(category, config, existing_rules)
        all_processed_rules[category] = rules
        new_count = len(rules)
        total_updated_rules += new_count # 累加最终规则数

        if category not in stats["categories"]:
            stats["categories"][category] = {"rule_count": 0, "last_updated": None}

        stats["categories"][category]["rule_count"] = new_count
        stats["categories"][category]["last_updated"] = datetime.now().isoformat()

        if old_count != new_count or new_rule_count > 0 : # 如果数量变化或有新增规则
            change_desc = f"{old_count}→{new_count}"
            if new_rule_count > 0 and old_count != new_count:
                 change_desc += f" ({'+' if new_count > old_count else ''}{new_count - old_count})"
            elif new_rule_count > 0:
                 change_desc += f" (+{new_rule_count})"
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
    parser = argparse.ArgumentParser(description='规则整合工具')
    parser.add_argument('action', choices=['create', 'read', 'update', 'delete'], help='要执行的操作: create (强制重新生成), read (读取统计或分类), update (更新规则), delete (删除分类规则)')
    parser.add_argument('--categories', nargs='+', help='要处理的分类 (默认全部)', default=None)
    parser.add_argument('--clean', action='store_true', help='在 create 或 update 前清理 rulesets/classical 目录')
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
         os.makedirs(OUTPUT_DIR_CUSTOM, exist_ok=True)

    if args.action == 'create':
        # Create 强制重新生成所有指定的（或全部）分类
        print("执行 'create' 操作，将重新下载和生成规则...")
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
        title = f"规则同步 - {args.action.capitalize()}"
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
        title = f"规则同步 CI - {args.action.capitalize()}"
        content = f"{result_message}\n用时: {duration:.2f}秒"
        print("CI 环境，尝试发送 Bark 通知...")
        send_bark_notification(title, content)

# Bark推送功能
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
    encoded_content = quote(content)

    try:
        # 保持 title 不编码，content 编码
        full_url = f"{bark_url.rstrip('/')}/{title}/{encoded_content}"
        # 添加超时设置和重试机制
        for attempt in range(3):  # 最多尝试3次
            try:
                response = requests.get(full_url, timeout=15)  # 增加超时时间
                if response.status_code == 200:
                    print(f"Bark推送成功: {title}")
                    return True
                else:
                    print(f"Bark推送失败: {response.status_code}, {response.text}")
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
        print("Bark推送最终失败 (多次尝试后)")
        return False
    except Exception as e:
        print(f"Bark推送异常: {e}")
        return False

if __name__ == "__main__":
    main() 