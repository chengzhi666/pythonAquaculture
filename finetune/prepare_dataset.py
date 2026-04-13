"""
第二步：准备数据集
- 将 852 条 Alpaca 格式语料复制到 LLaMA-Factory/data/ 目录
- 自动更新 dataset_info.json 注册数据集
- 按 85/15 比例拆分训练集和测试集（用于评测）

使用方法：
  cd finetune
  python prepare_dataset.py
"""

import json
import shutil
import random
from pathlib import Path

# === 路径配置 ===
PROJECT_ROOT = Path(__file__).parent.parent
SOURCE_JSONL = PROJECT_ROOT / "results" / "sft_dataset_real" / "sft_dataset.jsonl"
LLAMA_FACTORY_DIR = Path(__file__).parent / "LLaMA-Factory"
DATA_DIR = LLAMA_FACTORY_DIR / "data"

TRAIN_FILE = DATA_DIR / "aquaculture_sft_train.json"
TEST_FILE = DATA_DIR / "aquaculture_sft_test.json"
DATASET_INFO = DATA_DIR / "dataset_info.json"

SEED = 42
TEST_RATIO = 0.15  # 15% 用于评测，约 128 条


def load_jsonl(path: Path) -> list[dict]:
    """读取 JSONL 行"""
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def convert_to_alpaca(item: dict, *, keep_meta: bool = False) -> dict:
    """确保为标准 Alpaca 三字段格式（LLaMA-Factory 默认支持）。

    当 keep_meta=True 时额外保留 template_type 字段，
    供评测脚本按模板类型分组计算指标。
    """
    result = {
        "instruction": item.get("instruction", ""),
        "input": item.get("input", ""),
        "output": item.get("output", ""),
    }
    if keep_meta and item.get("template_type"):
        result["template_type"] = item["template_type"]
    return result


def main():
    # 检查源文件
    if not SOURCE_JSONL.exists():
        print(f"错误：找不到语料文件 {SOURCE_JSONL}")
        return

    # 检查 LLaMA-Factory 目录
    if not LLAMA_FACTORY_DIR.exists():
        print(f"错误：找不到 LLaMA-Factory 目录 {LLAMA_FACTORY_DIR}")
        print("请先执行第一步安装 LLaMA-Factory")
        return

    # 1. 读取并转换语料
    raw_data = load_jsonl(SOURCE_JSONL)
    print(f"读取语料：{len(raw_data)} 条")

    # 训练集只保留 Alpaca 三字段；测试集额外保留 template_type 供评测分组
    alpaca_data = [convert_to_alpaca(item) for item in raw_data]
    alpaca_data_with_meta = [convert_to_alpaca(item, keep_meta=True) for item in raw_data]

    # 2. 拆分训练/测试集
    random.seed(SEED)
    indices = list(range(len(alpaca_data)))
    random.shuffle(indices)

    test_size = int(len(alpaca_data) * TEST_RATIO)
    test_indices = set(indices[:test_size])

    train_data = [alpaca_data[i] for i in range(len(alpaca_data)) if i not in test_indices]
    test_data = [alpaca_data_with_meta[i] for i in range(len(alpaca_data)) if i in test_indices]

    print(f"训练集：{len(train_data)} 条")
    print(f"测试集：{len(test_data)} 条")

    # 3. 保存为 JSON 文件（LLaMA-Factory 用 JSON 列表格式）
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(TRAIN_FILE, "w", encoding="utf-8") as f:
        json.dump(train_data, f, ensure_ascii=False, indent=2)
    print(f"训练集已保存到：{TRAIN_FILE}")

    with open(TEST_FILE, "w", encoding="utf-8") as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)
    print(f"测试集已保存到：{TEST_FILE}")

    # 4. 注册到 dataset_info.json
    if DATASET_INFO.exists():
        with open(DATASET_INFO, "r", encoding="utf-8") as f:
            ds_info = json.load(f)
    else:
        ds_info = {}

    ds_info["aquaculture_sft_train"] = {
        "file_name": "aquaculture_sft_train.json",
        "formatting": "alpaca",
        "columns": {
            "prompt": "instruction",
            "query": "input",
            "response": "output",
        },
    }

    ds_info["aquaculture_sft_test"] = {
        "file_name": "aquaculture_sft_test.json",
        "formatting": "alpaca",
        "columns": {
            "prompt": "instruction",
            "query": "input",
            "response": "output",
        },
    }

    with open(DATASET_INFO, "w", encoding="utf-8") as f:
        json.dump(ds_info, f, ensure_ascii=False, indent=2)
    print(f"数据集已注册到：{DATASET_INFO}")

    print("\n✅ 数据准备完成！可以进行第三步训练。")


if __name__ == "__main__":
    main()
