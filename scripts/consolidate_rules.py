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

# --- 配置 ---

# 定义规则分类及其源 URL
# 格式: '目标文件名': { 'urls': ['url1', 'url2', ...], 'type': 'domain'/'ipcidr'/'classical', 'merge': True/False }
# 注意：这里的 key (如 'reject_domains') 将用于生成文件名 (reject_domains.list)
# 并且需要在 config.yaml 的 rule-providers 中引用
# merge 参数表示是否将不同来源的规则合并到一个文件中，True表示合并，False表示分别保留
RULE_CATEGORIES = {
    # --- REJECT 类 ---
    'reject_domains': {
        'urls': [
            'https://testingcf.jsdelivr.net/gh/ACL4SSR/ACL4SSR@master/Clash/BanAD.list',
            'https://raw.githubusercontent.com/Loyalsoldier/v2ray-rules-dat/release/reject-list.txt',
            'https://raw.githubusercontent.com/Steve5wutongyu6/DNSBlock/refs/heads/main/BlackList.txt',
            'https://testingcf.jsdelivr.net/gh/ACL4SSR/ACL4SSR@master/Clash/BanProgramAD.list',
            'https://raw.githubusercontent.com/cmliu/ACL4SSR/main/Clash/adobe.list',
            # 你可以在这里添加更多 REJECT 类型的 URL
        ],
        'type': 'classical', # classical 兼容 domain, keyword, ip 等
        'merge': True # 合并去重
    },
    # --- DIRECT 类 (国内域名/IP等) ---
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
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/ChinaMax/ChinaMax_Classical.yaml', # Blackmatrix China
            # 你可以添加更多 DIRECT 类型的 URL
        ],
        'type': 'classical',
        'merge': True # 合并去重
    },
    'direct_ips': {
        'urls': [
            'https://testingcf.jsdelivr.net/gh/ACL4SSR/ACL4SSR@master/Clash/ChinaCompanyIp.list',
            # 添加其他需要直连的 IP 规则 URL
        ],
        'type': 'ipcidr', # 明确指定 IP 类型
        'merge': True # 合并去重
    },
    # --- PROXY 类 (默认走代理，但不合并，保持按服务分类) ---
    # 不再整合全球媒体规则，每个单独保留
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
        'merge': False
    },
    'tiktok': {
        'urls': [
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/TikTok/TikTok_No_Resolve.yaml',
        ],
        'type': 'classical',
        'merge': False
    },
    # 微软服务
    'microsoft': {
        'urls': [
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Microsoft/Microsoft_No_Resolve.yaml',
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/OneDrive/OneDrive.yaml',
        ],
        'type': 'classical',
        'merge': False
    },
    # GitHub
    'github': {
        'urls': [
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/GitHub/GitHub.yaml',
        ],
        'type': 'classical',
        'merge': False
    },
    # Telegram
    'telegram': {
        'urls': [
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Telegram/Telegram.yaml',
        ],
        'type': 'classical',
        'merge': False
    },
    # 游戏平台整合
    'gaming': {
        'urls': [
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Nintendo/Nintendo.yaml',
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/PlayStation/PlayStation.yaml',
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Epic/Epic.yaml',
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Xbox/Xbox.yaml',
        ],
        'type': 'classical',
        'merge': True # 游戏平台可以合并
    },
    # 通用代理（其他未分类项）
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
        'merge': False # 通用代理规则不合并
    },
    # --- AI 服务类 (单独分类，方便指定特定策略组) ---
    'ai_domains': {
        'urls': [
            'rulesets/custom/aioai.list', # 我们自己的完整AI规则集（自定义目录）
            'https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/OpenAI/OpenAI_No_Resolve.yaml', # OpenAI Classical
            'https://raw.githubusercontent.com/juewuy/ShellClash/master/rules/ai.list', # AiExtra
            'https://raw.githubusercontent.com/cmliu/ACL4SSR/main/Clash/Copilot.list',
            'https://raw.githubusercontent.com/cmliu/ACL4SSR/main/Clash/GithubCopilot.list',
            'https://raw.githubusercontent.com/cmliu/ACL4SSR/main/Clash/Claude.list',
        ],
        'type': 'classical',
        'merge': True # AI服务合并
    },
    # --- Apple 服务类 (单独分类) ---
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
OUTPUT_DIR_CUSTOM = "rulesets/custom" # 如果你想把自定义规则放这里
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
                if os.path.isfile(file_path):
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
    if url.startswith('./') or url.startswith('/') or url.startswith('..'):
        try:
            with open(url, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except UnicodeDecodeError:
            # 尝试其他编码
            for enc in ['gbk', 'gb2312', 'big5']:
                try:
                    with open(url, 'r', encoding=enc) as f:
                        content = f.read()
                    return content
                except UnicodeDecodeError:
                    continue
            print(f"错误: 无法解码本地文件 {url} 的内容")
            return None
        except Exception as e:
            print(f"读取本地文件 {url} 失败: {e}")
            return None
    
    # 如果是远程URL
    headers = {'User-Agent': 'Mozilla/5.0 Clash Rule Consolidation Script'}
    try:
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        response.raise_for_status() # 如果请求失败则抛出异常
        # 尝试多种编码解码
        content = None
        encodings = ['utf-8', 'gbk', 'gb2312', 'big5']
        for enc in encodings:
            try:
                content = response.content.decode(enc)
                # print(f"Decoded {url} with {enc}")
                break
            except UnicodeDecodeError:
                continue
        if content is None:
            print(f"错误: 无法解码来自 {url} 的内容")
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
        # 简单的规则提取 (可以根据需要扩展更复杂的处理逻辑)
        # 例如，移除 Surge/Quantumult X 的策略标签
        parts = re.split(r'[,\s]+', line)
        rule = parts[0] # 通常第一个部分是规则本身
        # 进一步清理可能的 URL 路径等 (可选)
        # if rule.startswith('http'): rule = urlparse(rule).netloc
        if rule:
            # 尝试去除行尾注释
            rule = rule.split('#')[0].strip()
            if rule: # 再次检查非空
                rules.add(rule)
    return rules

def parse_yaml_content(content):
    """解析 YAML 文件内容 (主要是 blackmatrix7 的格式)，提取 payload"""
    rules = set()
    if content is None:
        return rules
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict) and 'payload' in data and isinstance(data['payload'], list):
            for item in data['payload']:
                item_str = str(item).strip() # 转换为字符串并清理
                if item_str and not item_str.startswith('#'):
                    # 去除行尾注释
                    item_str = item_str.split('#')[0].strip()
                    if item_str: # 再次检查非空
                        rules.add(item_str)
        else:
            print(f"警告: YAML内容不符合预期结构（缺少'payload'列表）")
    except yaml.YAMLError as e:
        print(f"错误: 解析YAML内容失败: {e}")
    return rules

def write_rules_to_file(rules, output_path):
    """将规则集合写入文件，每行一条"""
    # 确保目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    try:
        # 按字母顺序排序写入，增加可读性
        sorted_rules = sorted(list(rules))
        with open(output_path, 'w', encoding='utf-8') as f:
            for rule in sorted_rules:
                f.write(rule + '\n')
        print(f"成功写入 {len(sorted_rules)} 条规则到 {output_path}")
        return len(sorted_rules)
    except IOError as e:
        print(f"错误: 写入 {output_path} 失败: {e}")
        return 0

def load_existing_rules(file_path):
    """加载现有规则文件中的规则"""
    if not os.path.exists(file_path):
        return set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if file_path.endswith('.yaml') or file_path.endswith('.yml'):
            return parse_yaml_content(content)
        else:
            return parse_list_content(content)
    except Exception as e:
        print(f"加载现有规则文件 {file_path} 时出错: {e}")
        return set()

def process_url(url):
    """处理单个URL，下载并解析内容"""
    print(f"  下载 {url}...")
    try:
        content = download_content(url)
        if content is None:
            print(f"  警告: 无法从 {url} 下载内容，跳过...")
            return set()

        if url.endswith('.yaml') or url.endswith('.yml'):
            print(f"  解析为YAML...")
            return parse_yaml_content(content)
        else: # 默认按 .list/.txt 处理
            print(f"  解析为LIST/TXT...")
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
        return category_rules, 0

    for url in urls:
        rules_from_url = process_url(url)
        if rules_from_url:
            print(f"  从 {url} 获取到 {len(rules_from_url)} 条规则")
            category_rules.update(rules_from_url)
        else:
            print(f"  警告: 从 {url} 提取的规则为空")

    if existing_rules is not None:
        new_rules = category_rules - existing_rules
        removed_rules = existing_rules - category_rules
        unchanged_rules = category_rules.intersection(existing_rules)
        
        print(f"分类 '{category}' 统计:")
        print(f"  - 总规则数: {len(category_rules)}")
        print(f"  - 新增规则: {len(new_rules)}")
        print(f"  - 移除规则: {len(removed_rules)}")
        print(f"  - 未变规则: {len(unchanged_rules)}")
        
        return category_rules, len(new_rules)
    else:
        print(f"分类 '{category}' 总计独立规则: {len(category_rules)}")
        return category_rules, len(category_rules)

def write_category_rules(category, rules, output_dir):
    """将分类规则写入文件"""
    output_filename = f"{category}.list"
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
    total_new_rules = 0
    category_changes = []
    
    for category in categories:
        if category not in RULE_CATEGORIES:
            print(f"错误: 未知分类 '{category}'")
            continue
            
        config = RULE_CATEGORIES[category]
        output_dir = OUTPUT_DIR_CLASSICAL
        output_filename = f"{category}.list"
        output_path = os.path.join(output_dir, output_filename)
        
        # 加载现有规则
        existing_rules = load_existing_rules(output_path)
        old_count = len(existing_rules)
        
        # 处理规则
        rules, new_rule_count = process_category(category, config, existing_rules)
        all_processed_rules[category] = rules
        new_count = len(rules)
        
        if category not in stats["categories"]:
            stats["categories"][category] = {"rule_count": 0, "last_updated": None}
        
        stats["categories"][category]["rule_count"] = new_count
        stats["categories"][category]["last_updated"] = datetime.now().isoformat()
        
        total_new_rules += new_rule_count
        if old_count != new_count:
            category_changes.append(f"{category}: {old_count}→{new_count}")
    
    # 写入规则文件
    write_rules(all_processed_rules)
    
    change_details = "，".join(category_changes) if category_changes else "无变化"
    message = f"更新了 {len(categories)} 个类别，新增 {total_new_rules} 条规则。{change_details}"
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
    """写入所有规则文件"""
    print("\n写入规则文件...")
    
    # 处理需要合并的规则
    direct_domains = set()
    ai_domains = set()
    
    for category, rules in all_processed_rules.items():
        if not rules:
            print(f"跳过空分类: {category}")
            continue
            
        config = RULE_CATEGORIES.get(category, {})
        output_dir = OUTPUT_DIR_CLASSICAL
        
        # 如果需要独立输出
        if not config.get('merge', True):
            write_category_rules(category, rules, output_dir)
            print(f"分类 '{category}' 写入为独立文件。")
            continue
        
        # 根据分类确定合并到哪个集合
        if category.startswith('direct_'):
            direct_domains.update(rules)
            print(f"从 '{category}' 合并 {len(rules)} 条规则到 direct_domains")
        elif category.startswith('ai_'):
            ai_domains.update(rules)
            print(f"从 '{category}' 合并 {len(rules)} 条规则到 ai_domains")
        elif category in ['reject_domains', 'gaming']:
            # 这些类别要单独输出而不合并
            write_category_rules(category, rules, output_dir)
            print(f"分类 '{category}' 写入为独立文件。")
    
    # 写入合并后的规则
    if direct_domains:
        write_category_rules('direct_all', direct_domains, OUTPUT_DIR_CLASSICAL)
        print(f"合并后的直连域名总计: {len(direct_domains)}")
    else:
        print("警告: 没有直连域名可合并")
    
    if ai_domains:
        write_category_rules('ai_all', ai_domains, OUTPUT_DIR_CLASSICAL)
        print(f"合并后的AI域名总计: {len(ai_domains)}")
    else:
        print("警告: 没有AI域名可合并")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='规则整合工具')
    parser.add_argument('action', choices=['create', 'read', 'update', 'delete'], help='要执行的操作')
    parser.add_argument('--categories', nargs='+', help='要处理的分类', default=None)
    parser.add_argument('--clean', action='store_true', help='清理输出目录')
    parser.add_argument('--notify', action='store_true', help='完成后发送Bark通知')
    
    args = parser.parse_args()
    
    if args.clean:
        clean_output_directories()
    
    result_message = ""
    start_time = datetime.now()
    
    if args.action == 'create':
        result_message = create(args.categories)
    elif args.action == 'read':
        read(args.categories[0] if args.categories else None)
    elif args.action == 'update':
        result_message = update(args.categories)
    elif args.action == 'delete':
        result_message = delete(args.categories)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print(f"\n规则整合过程已完成。用时: {duration:.2f} 秒")
    
    # 发送推送通知
    if args.notify or os.environ.get('CI') == 'true':
        title = f"规则更新 - {args.action}"
        content = f"{result_message}\n用时: {duration:.2f}秒"
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
    
    try:
        full_url = f"{bark_url.rstrip('/')}/{title}/{content}"
        response = requests.get(full_url)
        if response.status_code == 200:
            print(f"Bark推送成功: {title}")
            return True
        else:
            print(f"Bark推送失败: {response.status_code}, {response.text}")
            return False
    except Exception as e:
        print(f"Bark推送异常: {e}")
        return False

if __name__ == "__main__":
    main() 