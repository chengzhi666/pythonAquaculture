# 毕设微调实验 —— 一键通关指南

## 你的硬件 (已确认)
- GPU: RTX 3060 Laptop, 6GB VRAM
- RAM: 16GB
- 语料: 852 条水产养殖 SFT 语料 (Alpaca 格式)

## 预计耗时
| 步骤 | 时间 |
|------|------|
| 环境安装 + 拉模型 | 20-30 min (看网速) |
| 数据准备 | 1 min |
| QLoRA 训练 (3 epoch) | 20-40 min |
| 推理预测 (微调+基座) | 10-20 min |
| 评测 | 2-3 min |
| **总计** | **约 1-2 小时** |

---

## 第一步：环境搭建

```powershell
# 1. 进入 finetune 目录
cd C:\Users\qiaoruo\PycharmProjects\pythonAquaculture\finetune

# 2. 创建独立虚拟环境
python -m venv finetune_env
.\finetune_env\Scripts\Activate.ps1

# 3. 克隆 LLaMA-Factory
git clone --depth 1 https://github.com/hiyouga/LLaMA-Factory.git

# 4. 安装 LLaMA-Factory 及依赖
cd LLaMA-Factory
pip install -e ".[torch,metrics]"
pip install modelscope rouge-chinese bert-score jieba

# 4.5 Windows 下 bitsandbytes 可能装不上或找不到 GPU，手动装新版：
pip install bitsandbytes>=0.43.3
cd ..

# 5. 下载 Qwen2.5-1.5B-Instruct (约 3GB)
python -c "from modelscope import snapshot_download; snapshot_download('qwen/Qwen2.5-1.5B-Instruct', local_dir='./models/Qwen2.5-1.5B-Instruct'); print('Done!')"
```

## 第二步：准备数据集

```powershell
# 还是在 finetune 目录下
python prepare_dataset.py
```

输出应该是：
```
读取语料：852 条
训练集：724 条
测试集：128 条
数据集已注册到：LLaMA-Factory/data/dataset_info.json
✅ 数据准备完成！
```

## 第三步：QLoRA 训练

```powershell
cd LLaMA-Factory
llamafactory-cli train ../configs/qwen_qlora_sft.yaml
```

⚠️ 训练时 GPU 显存占用约 4-5GB，留 1GB 给系统。如果 OOM：
- 把 `cutoff_len` 从 512 降到 384
- 确认没有其他 GPU 占用程序

训练完成后模型保存在 `saves/qwen2.5_1.5b_qlora_aquaculture/`

## 第四步：推理预测

```powershell
# 4a. 微调模型预测
llamafactory-cli train ../configs/qwen_qlora_predict.yaml

# 4b. 回到 finetune 目录，跑基座模型预测
cd ..
python predict_baseline.py
```

## 第五步：评测

```powershell
python evaluate_model.py
```

输出样例（论文直接可用）：
```
=================================================================
表 5-X  基座模型与微调模型评测对比
=================================================================
指标                     基座模型     微调模型       提升
-----------------------------------------------------------------
ROUGE-1 F1               0.2845     0.4523    +0.1678
ROUGE-2 F1               0.1234     0.2891    +0.1657
ROUGE-L F1               0.2567     0.4201    +0.1634
BERTScore Precision       0.6789     0.7856    +0.1067
BERTScore Recall          0.6543     0.7632    +0.1089
BERTScore F1              0.6664     0.7743    +0.1079
=================================================================
```

## 文件结构

```
finetune/
├── setup_llamafactory.ps1    # 安装参考脚本
├── prepare_dataset.py        # 数据准备（第二步）
├── predict_baseline.py       # 基座模型预测（第四步b）
├── evaluate_model.py         # 评测脚本（第五步）
├── RUN_GUIDE.md              # 本文件
├── configs/
│   ├── qwen_qlora_sft.yaml       # 训练配置
│   └── qwen_qlora_predict.yaml   # 推理配置
├── LLaMA-Factory/            # (克隆后出现)
├── models/                   # (下载后出现)
│   └── Qwen2.5-1.5B-Instruct/
├── saves/                    # (训练后出现)
│   ├── qwen2.5_1.5b_qlora_aquaculture/
│   │   └── predict/generated_predictions.jsonl
│   ├── baseline_predictions.jsonl
│   └── evaluation_results.json
└── finetune_env/             # 独立虚拟环境
```

## 常见问题

**Q: CUDA out of memory?**
在 `configs/qwen_qlora_sft.yaml` 中把 `cutoff_len` 从 512 改为 384，极端情况可降到 256。

**Q: Windows 下 bitsandbytes 报错？**
手动安装新版：`pip install bitsandbytes>=0.43.3`。如果还报 "CUDA not found"，确认 `nvidia-smi` 能正常输出，且 PyTorch 是 CUDA 版本（`python -c "import torch; print(torch.cuda.is_available())"`  应输出 True）。

**Q: modelscope 下载太慢？**
可以用 HuggingFace 镜像：`export HF_ENDPOINT=https://hf-mirror.com`，然后
`huggingface-cli download Qwen/Qwen2.5-1.5B-Instruct --local-dir ./models/Qwen2.5-1.5B-Instruct`

**Q: 训练 loss 不下降？**
正常的。852 条语料 + 3 epoch，loss 从 ~2.x 降到 ~1.x 就算成功。

**Q: BERTScore 跑得很慢？**
第一次运行会下载 BERT 模型（约 400MB），之后就快了。128 条测试集大概 2-3 分钟。
