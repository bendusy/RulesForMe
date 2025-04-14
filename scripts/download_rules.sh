#!/bin/bash

# 创建目录
echo "创建目录结构..."
mkdir -p rulesets/geosite rulesets/geoip rulesets/classical rulesets/custom

echo "开始下载规则集..."

# --- MetaCubeX (.mrs) ---
curl -L -o 'rulesets/geosite/private_domain.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/private.mrs'
curl -L -o 'rulesets/geosite/ai.mrs' 'https://github.com/MetaCubeX/meta-rules-dat/raw/refs/heads/meta/geo/geosite/category-ai-!cn.mrs'
curl -L -o 'rulesets/geosite/youtube_domain.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/youtube.mrs'
curl -L -o 'rulesets/geosite/google_domain.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/google.mrs'
curl -L -o 'rulesets/geosite/github_domain.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/github.mrs'
curl -L -o 'rulesets/geosite/telegram_domain.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/telegram.mrs'
curl -L -o 'rulesets/geosite/netflix_domain.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/netflix.mrs'
curl -L -o 'rulesets/geosite/paypal_domain.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/paypal.mrs'
curl -L -o 'rulesets/geosite/onedrive_domain.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/onedrive.mrs'
curl -L -o 'rulesets/geosite/microsoft_domain.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/microsoft.mrs'
curl -L -o 'rulesets/geosite/apple_domain.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/apple-cn.mrs'
curl -L -o 'rulesets/geosite/speedtest_domain.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/ookla-speedtest.mrs'
curl -L -o 'rulesets/geosite/tiktok_domain.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/tiktok.mrs'
curl -L -o 'rulesets/geosite/gfw_domain.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/gfw.mrs'
curl -L -o 'rulesets/geosite/geolocation-!cn.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/geolocation-!cn.mrs'
curl -L -o 'rulesets/geosite/cn_domain.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/cn.mrs'
curl -L -o 'rulesets/geoip/cn_ip.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geoip/cn.mrs'
curl -L -o 'rulesets/geoip/google_ip.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geoip/google.mrs'
curl -L -o 'rulesets/geoip/telegram_ip.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geoip/telegram.mrs'
curl -L -o 'rulesets/geoip/netflix_ip.mrs' 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geoip/netflix.mrs'


# 其余的下载命令省略，与 GitHub Actions 工作流中相同

echo "下载完成！"