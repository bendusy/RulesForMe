const fs = require('fs');
const path = require('path');
const { URL } = require('url');
const https = require('https'); // 引入 https 模块

// 新增一个函数用于从 URL 获取内容
function fetchUrlContent(url) {
    return new Promise((resolve, reject) => {
        https.get(url, (res) => {
            let data = '';
            res.on('data', (chunk) => {
                data += chunk;
            });
            res.on('end', () => {
                resolve(data);
            });
        }).on('error', (err) => {
            reject(err);
        });
    });
}

// Country codes and flags mapping
const COUNTRY_MAP = {
    'US': ['🇺🇸', '美国', '美', 'States', 'US'],
    'HK': ['🇭🇰', '香港', '港', 'Hong', 'HK'],
    'SG': ['🇸🇬', '新加坡', '新', 'Singapore', 'SG'],
    // Add more countries as needed using the same format
    'FR': ['🇫🇷', '法国', '法', 'France', 'FR'],
    'RU': ['🇷🇺', '俄罗斯', '俄', 'Russia', 'RU'],
    'NL': ['🇳🇱', '荷兰', '荷', 'Netherlands', 'NL'],
    'CH': ['🇨🇭', '瑞士', '瑞', 'Switzerland', 'CH'],
    'KR': ['🇰🇷', '韩国', '韩', 'Korea', 'KR'],
    'CA': ['🇨🇦', '加拿大', '加', 'Canada', 'CA'],
    'UN': ['🇺🇳', '未知', 'UN'],
    'FI': ['🇫🇮', '芬兰', '芬', 'Finland', 'FI'],
    'DE': ['🇩🇪', '德国', '德', 'Germany', 'DE'],
    'PK': ['🇵🇰', '巴基斯坦', '巴', 'Pakistan', 'PK'],
    'MD': ['🇲🇩', '摩尔多瓦', '摩', 'Moldova', 'MD'],
    'AE': ['🇦🇪', '阿联酋', '阿', 'Emirates', 'AE'],
    'ES': ['🇪🇸', '西班牙', '西', 'Spain', 'ES'],
    'IL': ['🇮🇱', '以色列', '以', 'Israel', 'IL'],
    'IT': ['🇮🇹', '意大利', '意', 'Italy', 'IT'],
    'GB': ['🇬🇧', '英国', '英', 'United Kingdom', 'UK'],
    'CN': ['🇨🇳', '中国', '中', 'CN'],
    'JP': ['🇯🇵', '日本', '日', 'Japan', 'JP'],
    'TW': ['🇹🇼', '台湾', '台', 'Taiwan', 'TW'],
    'AU': ['🇦🇺', '澳大利亚', '澳', 'Australia', 'AU'],
    'IN': ['🇮🇳', '印度', '印', 'India', 'IN'],
    'BR': ['🇧🇷', '巴西', '巴西', 'Brazil', 'BR']
};

// 服务关键词映射
const SERVICE_KEYWORDS = {
    'NETFLIX': ['Netflix', 'NF', 'NETFLIX', 'netflix', 'nf', '奈飞'],
    'OPENAI': ['OpenAI', 'OPENAI', 'openai', 'ChatGPT', 'GPT', 'chatgpt', 'gpt'],
    'GEMINI': ['Gemini', 'GEMINI', 'gemini', 'Bard', 'bard'],
    'DISNEY': ['Disney', 'DISNEY', 'disney', 'DisneyPlus', 'Disney+', 'disney+'],
    'STREAMING': ['Streaming', 'streaming', 'STREAM', 'stream', '流媒体']
};

// Reverse map for faster lookup
const REVERSE_COUNTRY_MAP = {};
for (const [code, keywords] of Object.entries(COUNTRY_MAP)) {
    keywords.forEach(keyword => {
        REVERSE_COUNTRY_MAP[keyword] = code;
    });
}
const COUNTRY_CODES_FOR_REGEX = Object.keys(COUNTRY_MAP);

// --- Parsing Functions ---

function safeDecodeURIComponent(component) {
    try {
        return decodeURIComponent(component);
    } catch (e) {
        // If decoding fails (e.g., malformed URI), return the original string
        return component;
    }
}

function parseVmess(url) {
    try {
        if (!url.startsWith("vmess://")) return null;

        const encodedPart = url.substring("vmess://".length);
        let decodedStr;
        try {
            decodedStr = Buffer.from(encodedPart, 'base64').toString('utf-8');
        } catch (e) {
            console.error(`Error decoding Vmess Base64: ${url} - ${e.message}`);
            return null;
        }

        let data;
        try {
            data = JSON.parse(decodedStr);
        } catch (e) {
            console.error(`Error parsing Vmess JSON: ${decodedStr} from ${url} - ${e.message}`);
            return null;
        }

        const name = data.ps || "vmess_node";
        const server = data.add;
        const port = data.port;
        const uuid = data.id;
        const alterId = data.aid || 0;
        const network = data.net || "tcp";
        const tls = data.tls === "tls";
        const path = data.path || "/";
        const host = data.host || "";
        const sni = data.sni || (tls ? host : ""); // Use host as default SNI if TLS is enabled

        if (!server || !port || !uuid) {
            console.warn(`Skipping Vmess due to missing info: ${url}`);
            return null;
        }

        const params = [
            `username=${uuid}`,
            `alterId=${alterId}`,
            `udp-relay=true`,
        ];

        if (network === "ws") {
            params.push("ws=true");
            params.push(`ws-path=${path}`);
            if (host) {
                // Ensure host doesn't contain invalid header characters, although unlikely for host
                const safeHost = String(host).replace(/[:\(\)<>@,;\\"\/\[\]?={} \t]/g, '');
                params.push(`ws-headers={Host=${safeHost}}`);
            }
        } else if (network !== "tcp") {
            console.warn(`Skipping unsupported Vmess network: ${network} in ${url}`);
            return null; // Skip unsupported network types for now
        }

        if (tls) {
            params.push("tls=true");
            if (sni) {
                params.push(`sni=${sni}`);
            }
            params.push("skip-cert-verify=true"); // Common for self-signed certs
        }

        return `${name} = vmess, ${server}, ${port}, ${params.join(', ')}`;

    } catch (e) {
        console.error(`Error parsing Vmess: ${url} - ${e.message}`);
        return null;
    }
}

function parseSs(url) {
    try {
        if (!url.startsWith("ss://")) return null;

        const hashIndex = url.indexOf('#');
        const name = hashIndex !== -1 ? safeDecodeURIComponent(url.substring(hashIndex + 1)) : "ss_node";
        const mainPart = hashIndex !== -1 ? url.substring("ss://".length, hashIndex) : url.substring("ss://".length);

        let credServerPart;
        // Check if the main part might be base64 encoded (no '@' before potential creds)
        if (!mainPart.includes('@') && mainPart.length > 5) { // Basic check if it could be base64
             try {
                 credServerPart = Buffer.from(mainPart, 'base64').toString('utf-8');
             } catch(e) {
                  console.warn(`SS Base64 decoding failed for main part, assuming format ss://method:pass@host:port : ${mainPart} in ${url}`);
                  credServerPart = mainPart; // Fallback if decoding fails
             }
        } else {
             // Try decoding the part before '@'
             const atIndex = mainPart.lastIndexOf('@');
             if (atIndex !== -1) {
                 const credPart = mainPart.substring(0, atIndex);
                 const serverPart = mainPart.substring(atIndex + 1);
                 try {
                     const decodedCred = Buffer.from(credPart, 'base64').toString('utf-8');
                     credServerPart = `${decodedCred}@${serverPart}`;
                 } catch (e) {
                     // console.warn(`SS Base64 decoding failed for cred part, assuming format ss://method:pass@host:port : ${credPart} in ${url}`);
                     credServerPart = mainPart; // Assume not encoded if decode fails
                 }
             } else {
                  // No '@' found, and didn't decode as full base64 -> Invalid format likely
                  console.warn(`Invalid SS format (no '@' found): ${url}`);
                  return null;
             }
        }


        const atIndexCredServer = credServerPart.lastIndexOf('@');
        if (atIndexCredServer === -1) {
            console.warn(`Invalid SS format after potential decoding (no '@'): ${credServerPart} in ${url}`);
            return null;
        }

        const credPartFinal = credServerPart.substring(0, atIndexCredServer);
        const serverPortFinal = credServerPart.substring(atIndexCredServer + 1);

        const colonIndexCred = credPartFinal.indexOf(':');
        if (colonIndexCred === -1) {
            console.warn(`Invalid SS credential format (no ':'): ${credPartFinal} in ${url}`);
            return null;
        }
        const method = credPartFinal.substring(0, colonIndexCred);
        const password = credPartFinal.substring(colonIndexCred + 1);


        const colonIndexServer = serverPortFinal.lastIndexOf(':');
        if (colonIndexServer === -1) {
            console.warn(`Invalid SS server:port format (no ':'): ${serverPortFinal} in ${url}`);
            return null;
        }
        const server = serverPortFinal.substring(0, colonIndexServer);
        const portStr = serverPortFinal.substring(colonIndexServer + 1);
        const port = parseInt(portStr, 10);

        if (!method || !password || !server || isNaN(port)) {
            console.warn(`Skipping SS due to missing/invalid info: ${url}`);
            return null;
        }

        return `${name} = ss, ${server}, ${port}, encrypt-method=${method}, password=${password}, udp-relay=true`;

    } catch (e) {
        console.error(`Error parsing SS: ${url} - ${e.message}`);
        return null;
    }
}

function parseTrojan(url) {
    try {
        if (!url.startsWith("trojan://")) return null;

        const parsed = new URL(url);
        const name = parsed.hash ? safeDecodeURIComponent(parsed.hash.substring(1)) : "trojan_node";
        const password = parsed.username || parsed.password; // password can be in username field
        const server = parsed.hostname;
        const port = parsed.port;

        if (!password || !server || !port) {
            console.warn(`Skipping Trojan due to missing info: ${url}`);
            return null;
        }

        const params = [
            `password=${password}`,
            "udp-relay=true"
        ];

        // TLS is default unless security=none (which we don't handle explicitly for Surge)
        params.push("tls=true");
        const sni = parsed.searchParams.get('sni') || server; // Default to server hostname
        if (sni) {
            params.push(`sni=${sni}`);
        }
        if (parsed.searchParams.get('allowInsecure') === '1' || parsed.searchParams.get('skip-cert-verify') === '1') {
            params.push("skip-cert-verify=true");
        }

        // Check for WebSocket
        if (parsed.searchParams.get('type') === 'ws') {
            params.push("ws=true");
            const wsPath = parsed.searchParams.get('path') || '/';
            params.push(`ws-path=${wsPath}`);
            const wsHost = parsed.searchParams.get('host') || sni; // Default to SNI
            if (wsHost) {
                 const safeHost = String(wsHost).replace(/[:\(\)<>@,;\\"\/\[\]?={} \t]/g, '');
                 params.push(`ws-headers={Host=${safeHost}}`);
            }
        }

        return `${name} = trojan, ${server}, ${port}, ${params.join(', ')}`;

    } catch (e) {
        console.error(`Error parsing Trojan: ${url} - ${e.message}`);
        return null;
    }
}


function parseVless(url) {
    try {
        if (!url.startsWith("vless://")) return null;

        const parsed = new URL(url);
        const name = parsed.hash ? safeDecodeURIComponent(parsed.hash.substring(1)) : "vless_node";
        const uuid = parsed.username; // UUID is in username part
        const server = parsed.hostname;
        const port = parsed.port;

        if (!uuid || !server || !port) {
            console.warn(`Skipping VLESS due to missing info: ${url}`);
            return null;
        }

        const params = [
            `username=${uuid}`,
            "udp-relay=true"
        ];

        const network = parsed.searchParams.get('type') || 'tcp';
        const security = parsed.searchParams.get('security') || 'none';
        const flow = parsed.searchParams.get('flow') || '';
        const sni = parsed.searchParams.get('sni') || (security === 'tls' || security === 'reality' ? server : "");
        const fp = parsed.searchParams.get('fp') || '';
        const pbk = parsed.searchParams.get('pbk') || '';
        const sid = parsed.searchParams.get('sid') || '';

        if (security === 'tls') {
            params.push("tls=true");
            if (sni) {
                params.push(`sni=${sni}`);
            }
            if (parsed.searchParams.get('allowInsecure') === '1') {
                 params.push("skip-cert-verify=true");
            }
            if (flow && flow !== "none") {
                 params.push(`flow=${flow}`);
            }
            if (fp) {
                 params.push(`client-fingerprint=${fp}`);
            }
        } else if (security === 'reality') {
             params.push("tls=true"); // Reality uses TLS layer
             params.push("reality=true");
             if (sni) {
                 params.push(`sni=${sni}`); // Reality SNI
             }
             if (pbk) {
                 params.push(`public-key=${pbk}`);
             }
             if (sid) {
                 params.push(`short-id=${sid}`);
             }
             if (fp) {
                 params.push(`client-fingerprint=${fp}`);
             }
             // skip-cert-verify is implicit
        }

        if (network === 'ws') {
            params.push("ws=true");
            const wsPath = parsed.searchParams.get('path') || '/';
            params.push(`ws-path=${wsPath}`);
            const wsHost = parsed.searchParams.get('host') || sni || server; // Default priority: host > sni > server
             if (wsHost) {
                 const safeHost = String(wsHost).replace(/[:\(\)<>@,;\\"\/\[\]?={} \t]/g, '');
                 params.push(`ws-headers={Host=${safeHost}}`);
            }
        } else if (network === 'grpc') {
            params.push("grpc=true");
            const serviceName = parsed.searchParams.get('serviceName') || '';
            if (serviceName) {
                params.push(`grpc-service-name=${safeDecodeURIComponent(serviceName)}`);
            }
            // const grpcMode = parsed.searchParams.get('mode') || ''; // Surge doesn't typically use mode=gun/multi param
        } else if (network !== 'tcp') {
            console.warn(`Skipping unsupported VLESS network type: ${network} in ${url}`);
            return null;
        }

        return `${name} = vless, ${server}, ${port}, ${params.join(', ')}`;

    } catch (e) {
        console.error(`Error parsing VLESS: ${url} - ${e.message}`);
        return null;
    }
}

function parseHysteria(url) {
    try {
        if (!url.startsWith("hysteria://")) return null;

        const parsed = new URL(url); // Hysteria 1 often uses host:port directly, not standard URL auth
        const name = parsed.hash ? safeDecodeURIComponent(parsed.hash.substring(1)) : "hysteria_node";
        const server = parsed.hostname;
        const port = parsed.port;

        if (!server || !port) {
            console.warn(`Skipping Hysteria due to missing info: ${url}`);
            return null;
        }

        const queryParams = parsed.searchParams;
        const authStr = queryParams.get('auth_str') || queryParams.get('auth') || ''; // Prefer auth_str
        const protocol = queryParams.get('protocol') || 'udp';
        const sni = queryParams.get('peer') || queryParams.get('sni') || server; // Prefer peer
        const insecure = queryParams.get('insecure') === '1' || queryParams.get('skip-cert-verify') === '1';
        let upMbps = queryParams.get('upmbps') || '10';
        let downMbps = queryParams.get('downmbps') || '50';
        const alpn = queryParams.get('alpn') || 'hysteria';
        const obfs = queryParams.get('obfs') || '';
        const obfsPassword = queryParams.get('obfs-password') || ''; // Surge uses obfs-password

        // Clean up speed values
        upMbps = String(upMbps).replace(/[^0-9]/g, '');
        downMbps = String(downMbps).replace(/[^0-9]/g, '');
        let upSpeed = parseInt(upMbps, 10);
        let downSpeed = parseInt(downMbps, 10);
        if (isNaN(upSpeed)) upSpeed = 10;
        if (isNaN(downSpeed)) downSpeed = 50;

        const params = [
            `auth-str=${authStr}`,
            `protocol=${protocol}`,
            `sni=${sni}`,
            `up-mbps=${upSpeed}`,
            `down-mbps=${downSpeed}`,
            `alpn=${alpn}`,
            "udp-relay=true"
        ];

        if (insecure) {
            params.push("skip-cert-verify=true");
        }
        if (obfs) {
            params.push(`obfs=${obfs}`);
            if (obfsPassword) { // Add obfs-password only if obfs is present
                params.push(`obfs-password=${obfsPassword}`);
            }
        }

        return `${name} = hysteria, ${server}, ${port}, ${params.join(', ')}`;

    } catch (e) {
        console.error(`Error parsing Hysteria: ${url} - ${e.message}`);
        return null;
    }
}

function parseHysteria2(url) {
    try {
        if (!url.startsWith("hysteria2://")) return null;

        const parsed = new URL(url);
        const name = parsed.hash ? safeDecodeURIComponent(parsed.hash.substring(1)) : "hysteria2_node";
        const password = parsed.username || parsed.password; // Password is in username
        const server = parsed.hostname;
        const port = parsed.port;

        if (!password || !server || !port) {
            console.warn(`Skipping Hysteria2 due to missing info: ${url}`);
            return null;
        }

        const queryParams = parsed.searchParams;
        const sni = queryParams.get('sni') || server;
        const insecure = queryParams.get('insecure') === '1' || queryParams.get('skip-cert-verify') === '1';
        const obfs = queryParams.get('obfs') || '';
        const obfsPassword = queryParams.get('obfs-password') || ''; // Surge uses obfs-password

        const params = [
            `password=${password}`,
            `sni=${sni}`,
            "udp-relay=true"
        ];

        if (insecure) {
            params.push("skip-cert-verify=true");
        }
        if (obfs) {
            params.push(`obfs=${obfs}`);
             if (obfsPassword) { // Add obfs-password only if obfs is present
                 params.push(`obfs-password=${obfsPassword}`);
             }
        }

        return `${name} = hysteria2, ${server}, ${port}, ${params.join(', ')}`;

    } catch (e) {
        console.error(`Error parsing Hysteria2: ${url} - ${e.message}`);
        return null;
    }
}

// 新增一个函数用于提取协议类型
function getProtocolFromURL(url) {
    if (url.startsWith('vmess://')) return 'VMess';
    if (url.startsWith('ss://')) return 'SS';
    if (url.startsWith('trojan://')) return 'Trojan';
    if (url.startsWith('vless://')) return 'VLess';
    if (url.startsWith('hysteria://')) return 'Hysteria';
    if (url.startsWith('hysteria2://')) return 'Hysteria2';
    return 'Unknown';
}

// 新增一个函数用于检测服务关键词
function detectServices(nodeName) {
    const services = [];
    for (const [service, keywords] of Object.entries(SERVICE_KEYWORDS)) {
        for (const keyword of keywords) {
            if (nodeName.includes(keyword)) {
                services.push(service);
                break; // 只需要匹配一次即可
            }
        }
    }
    return services;
}

// 新增一个函数用于清理节点名称中的无关信息
function cleanNodeName(originalName) {
    // 不需要保留的信息模式
    const patterns = [
        /\d+\.\d+[xX]/i, // 例如 2.0x, 1.5x 等倍率
        /\d+\s*[Mm][Bb][Pp][Ss]/i, // 例如 10Mbps, 5 mbps 等速度信息
        /\d+\s*[Gg][Bb]/i, // 例如 10GB, 5gb 等容量信息
        /付费/i, /过期/i, /到期/i, /剩余/i, // 付费信息
        /高速/i, /标准/i, /普通/i, /\b(VIP|vip)\b/i, // 等级信息
        /中转/i, /直连/i, /隧道/i, // 连接方式信息
        /\d{1,2}\/\d{1,2}/, // 日期格式，如 06/30
        /[A-Za-z0-9]{8}(-[A-Za-z0-9]{4}){3}-[A-Za-z0-9]{12}/, // UUID格式
        /[\u4e00-\u9fa5]+节点/, // 中文+节点
        /[\u4e00-\u9fa5]+专线/, // 中文+专线
        /[\u4e00-\u9fa5]+(?:上海|北京|广州|深圳|杭州)/, // 中文+城市名
        /(?:上海|北京|广州|深圳|杭州)[\u4e00-\u9fa5]+/, // 城市名+中文
    ];
    
    // 保留的服务关键词
    const servicesToKeep = ['Netflix', 'NF', 'NETFLIX', 'netflix', 'nf', '奈飞', 
                           'OpenAI', 'OPENAI', 'openai', 'ChatGPT', 'GPT', 'chatgpt', 'gpt',
                           'Gemini', 'GEMINI', 'gemini', 'Bard', 'bard',
                           'Disney', 'DISNEY', 'disney', 'DisneyPlus', 'Disney+', 'disney+',
                           'Streaming', 'streaming', 'STREAM', 'stream', '流媒体'];
    
    // 创建一个临时字符串存储清理后的名称
    let cleanedName = originalName;
    
    // 应用模式进行清理，但保留服务关键词
    patterns.forEach(pattern => {
        cleanedName = cleanedName.replace(pattern, '');
    });
    
    // 删除多余的符号
    cleanedName = cleanedName.replace(/[,，\s\-_\|]{2,}/g, ' ').trim();
    
    // 如果剩余内容太短，返回原名，否则返回清理后的名称
    return cleanedName.length < 2 ? originalName : cleanedName;
}

// 修改格式化节点名称函数，使用国家中文名和旗帜
function formatNodeName(originalName, countryCode, protocol, index) {
    // 清理节点名称中的无关信息
    const cleanedName = cleanNodeName(originalName);
    
    // 检测是否包含特殊服务关键词
    const services = detectServices(cleanedName);
    const serviceTag = services.length > 0 ? `|${services.join('|')}` : '';
    
    // 获取国家信息
    const countryInfo = COUNTRY_MAP[countryCode] || [];
    const countryFlag = countryInfo[0] || '';
    const countryName = countryInfo[1] || countryCode;
    
    // 格式化为：旗帜中文-协议-编号
    return `${countryFlag}${countryName}-${protocol}-${String(index).padStart(2, '0')}${serviceTag}`;
}

// --- Main Logic ---

function getCountryCode(nodeName) {
    // Prioritize keyword matches
    for (const [keyword, code] of Object.entries(REVERSE_COUNTRY_MAP)) {
         // Use word boundaries for codes like US, HK etc.
         if (COUNTRY_CODES_FOR_REGEX.includes(code)) {
             // Need case-insensitive regex match for keywords like 'US' or 'Hong Kong'
             const regex = new RegExp(`\\b${keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i');
             if (regex.test(nodeName)) {
                 return code;
             }
         } else if (nodeName.includes(keyword)) { // Simple includes for flags or longer names
             return code;
         }
    }
     // Fallback to check flags again if no text match
    for (const [code, keywords] of Object.entries(COUNTRY_MAP)) {
         const flag = keywords[0]; // Assuming flag is the first item
         if (nodeName.includes(flag)) {
             return code;
         }
     }
    return "OTHERS"; // Default if no match
}


const parsers = {
    "vmess://": parseVmess,
    "ss://": parseSs,
    "trojan://": parseTrojan,
    "vless://": parseVless,
    "hysteria://": parseHysteria,
    "hysteria2://": parseHysteria2,
    // Add other protocols here if needed
};

// 增加特殊服务分类
const categorizedProxies = {};

// 初始化国家分类
Object.keys(COUNTRY_MAP).forEach(code => {
    categorizedProxies[code] = [];
});
// 添加OTHERS分类
categorizedProxies['OTHERS'] = [];

// 初始化特殊服务分类
Object.keys(SERVICE_KEYWORDS).forEach(service => {
    categorizedProxies[service] = [];
});

// 为了跟踪每个国家和协议的节点编号
const countryProtocolCounter = {};

const inputFilePath = path.join('converter', 'base'); // Relative path from workspace root
const remoteUrl = 'https://raw.githubusercontent.com/roosterkid/openproxylist/main/V2RAY_RAW.txt'; // 新增远程 URL
const outputFilePath = 'surge_proxies_js.txt';

/**
 * 检测字符串是否是base64编码
 * 
 * @param {string} str 要检测的字符串
 * @returns {boolean} 是否可能是base64编码
 */
function isBase64(str) {
    // 一个基本的base64检测函数，可能有一些边缘情况不能完全覆盖
    if (typeof str !== 'string') return false;
    if (str.length % 4 !== 0) return false;
    
    // Base64使用的字符集
    const base64Regex = /^[A-Za-z0-9+/=]+$/;
    return base64Regex.test(str);
}

// 声明在全局作用域
let globalConvertedCount = 0;
let globalSkippedCount = 0;

// 使用 async IIFE (Immediately Invoked Function Expression) 来处理异步操作
(async () => {
    try {
        let localFileContent = '';
        let remoteFileContent = '';
        let localReadSuccess = false;
        let remoteFetchSuccess = false;

        // 1. 尝试读取本地文件
        try {
            // Check if input file exists
            if (!fs.existsSync(inputFilePath)) {
                 console.warn(`本地输入文件 '${inputFilePath}' 不存在。将尝试仅从远程 URL 获取。`);
                // throw new Error(`Input file '${inputFilePath}' not found. Make sure 'base' exists in the converter directory.`);
            } else {
                // 首先以二进制形式读取文件内容
                const fileBuffer = fs.readFileSync(inputFilePath);

                // 尝试将内容视为base64编码的字符串解码
                // 将前128个字节转为字符串来检测是否为base64
                const sampleContent = fileBuffer.subarray(0, Math.min(128, fileBuffer.length)).toString('utf8').trim();

                if (isBase64(sampleContent)) {
                    console.log('检测到本地文件为 base64 编码。尝试解码...');
                    try {
                        // 尝试将整个文件内容作为base64解码
                        localFileContent = Buffer.from(fileBuffer.toString().trim(), 'base64').toString('utf8');
                        console.log('本地文件 Base64 解码成功！');
                        localReadSuccess = true;
                    } catch (e) {
                        console.warn(`本地文件 Base64 解码失败: ${e.message}。将尝试按 UTF-8 读取。`);
                        localFileContent = fileBuffer.toString('utf8');
                        localReadSuccess = true; // 即使解码失败，也按 UTF-8 读取了
                    }
                } else {
                    // 如果不是base64编码，直接作为UTF-8读取
                    console.log('本地文件似乎是纯文本。按 UTF-8 读取。');
                    localFileContent = fileBuffer.toString('utf8');
                    localReadSuccess = true;
                }
            }
        } catch (e) {
            console.warn(`读取本地文件 '${inputFilePath}' 出错: ${e.message}。将尝试仅从远程 URL 获取。`);
        }

        // 2. 尝试获取远程内容
        try {
            console.log(`正在从 ${remoteUrl} 获取内容...`);
            remoteFileContent = await fetchUrlContent(remoteUrl);
            console.log('成功从远程 URL 获取内容。');
            remoteFetchSuccess = true;
        } catch (e) {
            console.warn(`从 ${remoteUrl} 获取内容失败: ${e.message}。将尝试仅使用本地文件。`);
        }

        // 3. 检查是否有任何可用内容
        if (!localReadSuccess && !remoteFetchSuccess) {
            throw new Error("本地文件读取和远程 URL 获取均失败，无法继续。");
        }

        // 4. 合并内容
        const combinedContent = localFileContent + '\n' + remoteFileContent; // 用换行符分隔
        const lines = combinedContent.split('\n');
        console.log(`共加载 ${lines.length} 行（包含本地和远程）。`);

        // 5. 处理合并后的行 (原有的处理逻辑)
        let convertedCount = 0;
        let skippedCount = 0;

        lines.forEach(line => {
            line = line.trim();
            if (!line) return;

            let surgeProxyLine = null;
            let nodeNameForCountry = "";
            let originalProtocol = "";

            for (const [prefix, parserFunc] of Object.entries(parsers)) {
                if (line.startsWith(prefix)) {
                    originalProtocol = getProtocolFromURL(line);
                    surgeProxyLine = parserFunc(line);
                    if (surgeProxyLine) {
                        // Extract name from the generated line for country detection
                        const match = surgeProxyLine.match(/^([^=]+?)\s*=/);
                        if (match && match[1]) {
                            nodeNameForCountry = match[1].trim();
                        } else {
                            // Fallback: try extracting name from original URL hash
                            try {
                                const parsedOriginal = new URL(line);
                                if(parsedOriginal.hash) {
                                    nodeNameForCountry = safeDecodeURIComponent(parsedOriginal.hash.substring(1));
                                }
                            } catch(e) { /* Ignore parsing errors for fallback */ }
                        }
                        convertedCount++;
                    } else {
                        skippedCount++;
                    }
                    break; // Found a matching parser
                }
            }

            if (surgeProxyLine && nodeNameForCountry) {
                 // 检测节点国家
                 const countryCode = getCountryCode(nodeNameForCountry);
                 const targetCategory = COUNTRY_CODES_FOR_REGEX.includes(countryCode) ? countryCode : 'OTHERS';

                 // 初始化计数器（如果不存在）
                 if (!countryProtocolCounter[countryCode]) {
                     countryProtocolCounter[countryCode] = {};
                 }
                 if (!countryProtocolCounter[countryCode][originalProtocol]) {
                     countryProtocolCounter[countryCode][originalProtocol] = 0;
                 }

                 // 增加计数
                 countryProtocolCounter[countryCode][originalProtocol]++;

                 // 创建新的节点名称
                 const newNodeName = formatNodeName(
                     nodeNameForCountry,
                     countryCode,
                     originalProtocol,
                     countryProtocolCounter[countryCode][originalProtocol]
                 );

                 // 替换原来的节点名称
                 surgeProxyLine = surgeProxyLine.replace(/^([^=]+?)\s*=/, `${newNodeName} =`);

                 // 添加到对应国家分类中
                 if (!categorizedProxies[targetCategory]) {
                     categorizedProxies[targetCategory] = []; // 防止未初始化
                 }
                 categorizedProxies[targetCategory].push(surgeProxyLine);

                 // 检测是否需要加入特殊服务分类
                 const services = detectServices(nodeNameForCountry);
                 services.forEach(service => {
                     if (categorizedProxies[service]) {
                         categorizedProxies[service].push(surgeProxyLine);
                     }
                 });
            } else if (surgeProxyLine) { // If name extraction failed but line was generated
                categorizedProxies['OTHERS'].push(surgeProxyLine);
            }
            // else: Ignored or failed lines are implicitly skipped
        });

        // 将数据保存到全局变量
        globalConvertedCount = convertedCount;
        globalSkippedCount = skippedCount;

        console.log(`转换摘要: ${convertedCount} 个节点已转换, ${skippedCount} 个节点已跳过。`);

        // --- Output --- (原有的输出逻辑)
        try {
            let outputContent = "# Surge Proxy Configuration - Generated by Script (JavaScript Version)\n";
            outputContent += "# 生成的配置文件包含节点和分组，请复制到Surge配置文件对应部分\n\n";

            // 只保留指定的国家和服务
            const filteredCountryOrder = ['US', 'HK', 'SG', 'OTHERS'];
            const filteredServiceOrder = ['NETFLIX', 'OPENAI', 'GEMINI', 'DISNEY'];

            // 确保只输出有节点的分类
            const validCountryOrder = filteredCountryOrder.filter(category =>
                categorizedProxies[category] && categorizedProxies[category].length > 0
            );
            const validServiceOrder = filteredServiceOrder.filter(service =>
                categorizedProxies[service] && categorizedProxies[service].length > 0
            );

            // 先输出所有代理节点
            outputContent += "# ==================== [Proxy] ====================\n";
            validCountryOrder.forEach(category => {
                if (categorizedProxies[category] && categorizedProxies[category].length > 0) {
                    // 获取国家信息用于显示更友好的名称
                    const countryInfo = COUNTRY_MAP[category];
                    const groupTitle = countryInfo ? `${countryInfo[0]} ${countryInfo[1]}` : category;

                    outputContent += `# ========== ${groupTitle} 节点 (${categorizedProxies[category].length}) ==========\n`;
                    // Sort lines within category alphabetically by node name (the part before '=')
                    const sortedLines = categorizedProxies[category].sort((a, b) => {
                         const nameA = (a.match(/^([^=]+?)\s*=/) || ['', ''])[1].trim();
                         const nameB = (b.match(/^([^=]+?)\s*=/) || ['', ''])[1].trim();
                         return nameA.localeCompare(nameB);
                    });
                    outputContent += sortedLines.join('\n') + '\n\n'; // Add a blank line between categories
                }
            });

            // 然后输出代理分组配置
            outputContent += "\n# ==================== [Proxy Group] ====================\n";

            // 添加主分组
            outputContent += "# 主策略组\n";
            outputContent += "PROXY = select, ";

            // 将所有国家分组添加到主策略组
            const countryGroups = validCountryOrder.map(code => {
                // 将国家代码映射为友好名称
                const countryInfo = COUNTRY_MAP[code];
                if (countryInfo) {
                    return `${countryInfo[0]} ${countryInfo[1]}`; // 例如：🇺🇸 美国
                }
                return code; // 如果没有找到映射，使用代码
            });

            // 将特殊服务分组添加到主策略组
            const serviceGroups = validServiceOrder.map(service => service);

            // 组合所有分组名称
            outputContent += [...countryGroups, ...serviceGroups].join(', ') + '\n\n';

            // 添加国家分组
            outputContent += "# 国家和地区分组\n";
            validCountryOrder.forEach(category => {
                if (categorizedProxies[category] && categorizedProxies[category].length > 0) {
                    // 获取国家信息用于显示更友好的名称
                    const countryInfo = COUNTRY_MAP[category];
                    const groupName = countryInfo ? `${countryInfo[0]} ${countryInfo[1]}` : category;

                    outputContent += `${groupName} = select, `;

                    // 从该分类中提取所有节点名称
                    const nodeNames = categorizedProxies[category].map(line => {
                        const match = line.match(/^([^=]+?)\s*=/);
                        return match ? match[1].trim() : null;
                    }).filter(Boolean); // 过滤掉null值

                    outputContent += nodeNames.join(', ') + '\n';
                }
            });

            // 添加特殊服务分组
            if (validServiceOrder.length > 0) {
                outputContent += "\n# 特殊服务分组\n";
                validServiceOrder.forEach(service => {
                    if (categorizedProxies[service] && categorizedProxies[service].length > 0) {
                        outputContent += `${service} = select, `;

                        // 从该分类中提取所有节点名称
                        const nodeNames = categorizedProxies[service].map(line => {
                            const match = line.match(/^([^=]+?)\s*=/);
                            return match ? match[1].trim() : null;
                        }).filter(Boolean); // 过滤掉null值

                        outputContent += nodeNames.join(', ') + '\n';
                    }
                });
            }

            fs.writeFileSync(outputFilePath, outputContent, 'utf-8');

            console.log(`成功转换节点并保存到 '${outputFilePath}'`);
            console.log("文件已生成，包含代理节点和代理分组配置。");
            console.log(`共转换 ${globalConvertedCount} 个节点，跳过 ${globalSkippedCount} 个节点。`);
            console.log(`生成了 ${validCountryOrder.length} 个国家/地区分组和 ${validServiceOrder.length} 个特殊服务分组。`);

        } catch (e) {
            console.error(`写入输出文件 '${outputFilePath}' 时出错: ${e.message}`);
            process.exit(1);
        }

    } catch (e) {
        console.error(`处理文件时发生错误: ${e.message}`);
        process.exit(1);
    }
})(); // 立即执行 async IIFE
