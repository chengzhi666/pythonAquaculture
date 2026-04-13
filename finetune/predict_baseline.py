"""
第四步：对基座模型（无 LoRA）做同样的预测
用于和微调后的模型进行对比，产出论文表格中的"微调前 vs 微调后"数据

使用方法：
  cd finetune/LLaMA-Factory
  llamafactory-cli train ../../configs/qwen_qlora_predict_base.yaml

或使用本脚本手动生成（非 LLaMA-Factory 方式，作为备选）：
  cd finetune
  python predict_baseline.py
"""

import json
from pathlib import Path

# 如果 LLaMA-Factory predict 不方便对基座跑，这个脚本用 transformers 直接加载基座做推理
# 这样论文可以有"基座模型 vs 微调模型"的对比

def main():
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
    except ImportError:
        print("需要安装 transformers：pip install transformers torch")
        return

    PROJECT_ROOT = Path(__file__).parent.parent
    MODEL_DIR = Path(__file__).parent / "models" / "Qwen2.5-1.5B-Instruct"
    TEST_FILE = Path(__file__).parent / "LLaMA-Factory" / "data" / "aquaculture_sft_test.json"
    OUTPUT_FILE = Path(__file__).parent / "saves" / "baseline_predictions.jsonl"

    if not MODEL_DIR.exists():
        print(f"错误：找不到模型目录 {MODEL_DIR}")
        return
    if not TEST_FILE.exists():
        print(f"错误：找不到测试集 {TEST_FILE}")
        print("请先运行 prepare_dataset.py")
        return

    # 加载测试集
    with open(TEST_FILE, "r", encoding="utf-8") as f:
        test_data = json.load(f)
    print(f"测试集：{len(test_data)} 条")

    # 加载模型 (4-bit 量化以适应 6GB 显存)
    print("正在加载基座模型（4-bit 量化）...")
    try:
        from transformers import BitsAndBytesConfig
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
        )
        model = AutoModelForCausalLM.from_pretrained(
            str(MODEL_DIR),
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )
    except Exception:
        print("4-bit 加载失败，尝试 float16 加载...")
        model = AutoModelForCausalLM.from_pretrained(
            str(MODEL_DIR),
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )

    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR), trust_remote_code=True)
    model.eval()

    # 逐条推理
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    results = []

    for i, item in enumerate(test_data):
        prompt = item["instruction"]
        if item.get("input"):
            prompt += "\n" + item["input"]

        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=False,
                temperature=1.0,
            )

        # 只取新生成的 token
        generated = outputs[0][inputs["input_ids"].shape[1]:]
        prediction = tokenizer.decode(generated, skip_special_tokens=True)

        results.append({
            "predict": prediction,
            "label": item["output"],
            "instruction": item["instruction"],
            "template_type": item.get("template_type", "unknown"),
        })

        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(test_data)}] 已完成")

    # 保存
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n✅ 基座模型预测完成，保存到：{OUTPUT_FILE}")
    print(f"共 {len(results)} 条预测结果")


if __name__ == "__main__":
    main()
