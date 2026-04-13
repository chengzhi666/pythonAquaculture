# ============================================================
# 第一步：安装 LLaMA-Factory + 拉取 Qwen2.5-1.5B-Instruct
# 在 PowerShell 中执行此脚本
# ============================================================

Write-Host "=== Step 1/3: 克隆 LLaMA-Factory ===" -ForegroundColor Cyan
if (-not (Test-Path "LLaMA-Factory")) {
    git clone --depth 1 https://github.com/hiyouga/LLaMA-Factory.git
} else {
    Write-Host "LLaMA-Factory 已存在，跳过克隆"
}

Write-Host "`n=== Step 2/3: 安装依赖 ===" -ForegroundColor Cyan
Write-Host "建议在独立虚拟环境中安装，避免和项目 venv 冲突："
Write-Host "  python -m venv finetune_env"
Write-Host "  .\finetune_env\Scripts\Activate.ps1"
Write-Host ""
Write-Host "然后执行以下命令："
Write-Host "  cd LLaMA-Factory"
Write-Host "  pip install -e '.[torch,metrics]'"
Write-Host "  pip install modelscope rouge-chinese bert-score jieba"
Write-Host ""

Write-Host "`n=== Step 3/3: 从 ModelScope 下载 Qwen2.5-1.5B-Instruct ===" -ForegroundColor Cyan
Write-Host "执行以下 Python 命令（约 3GB，国内网络几分钟）："
Write-Host @"
python -c "
from modelscope import snapshot_download
snapshot_download(
    'qwen/Qwen2.5-1.5B-Instruct',
    local_dir='./models/Qwen2.5-1.5B-Instruct'
)
print('模型下载完成！')
"
"@

Write-Host "`n=== 完成后的目录结构 ===" -ForegroundColor Green
Write-Host @"
finetune/
├── LLaMA-Factory/          # 框架
│   └── data/
│       ├── dataset_info.json  # 需要注册数据集（第二步）
│       └── aquaculture_sft.jsonl  # 复制过来的语料
├── models/
│   └── Qwen2.5-1.5B-Instruct/  # 基座模型
├── configs/
│   └── qwen_qlora_sft.yaml     # 训练配置（第三步）
├── evaluate_model.py            # 评测脚本（第五步）
└── setup_llamafactory.ps1       # 本文件
"@
