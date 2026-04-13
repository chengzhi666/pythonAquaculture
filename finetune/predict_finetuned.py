"""
微调模型推理脚本（transformers + peft，绕过 LLaMA-Factory 在 Windows 上的缓存问题）

常用命令：
  python predict_finetuned.py --max-samples 8 --overwrite
  python predict_finetuned.py --max-samples 20 --max-new-tokens 128
  python predict_finetuned.py --resume
"""

import argparse
import json
import time
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="微调模型推理（支持断点续跑）")
    parser.add_argument("--model-dir", type=str, default="models/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--adapter-dir", type=str, default="saves/qwen2.5_1.5b_qlora_aquaculture")
    parser.add_argument("--test-file", type=str, default="LLaMA-Factory/data/aquaculture_sft_test.json")
    parser.add_argument("--output-file", type=str, default="saves/finetuned_predictions.jsonl")
    parser.add_argument("--start-index", type=int, default=0, help="从第几个样本开始（0-based）")
    parser.add_argument("--max-samples", type=int, default=0, help="最多跑多少条；0 表示全量")
    parser.add_argument("--max-new-tokens", type=int, default=160, help="每条回答最大新 token 数")
    parser.add_argument("--max-prompt-tokens", type=int, default=1536, help="输入提示词最大 token 数")
    parser.add_argument("--log-every", type=int, default=5, help="每多少条打印一次进度")
    parser.add_argument("--resume", action="store_true", help="从已有输出文件断点续跑")
    parser.add_argument("--overwrite", action="store_true", help="覆盖输出文件重新跑")
    return parser.parse_args()


def _resolve_path(base_dir: Path, path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _load_done_indices(output_file: Path, start_index: int) -> set[int]:
    done_indices: set[int] = set()
    if not output_file.exists():
        return done_indices

    legacy_count = 0
    with open(output_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "index" in rec and isinstance(rec["index"], int):
                done_indices.add(rec["index"])
            else:
                legacy_count += 1

    # 兼容旧版输出（没有 index 字段）
    if not done_indices and legacy_count > 0:
        done_indices = set(range(start_index, start_index + legacy_count))
    return done_indices


def _build_prompt(item: dict) -> str:
    prompt = item.get("instruction", "")
    if item.get("input"):
        prompt += "\n" + item["input"]
    return prompt


def main() -> None:
    args = _parse_args()
    base_dir = Path(__file__).parent
    model_dir = _resolve_path(base_dir, args.model_dir)
    adapter_dir = _resolve_path(base_dir, args.adapter_dir)
    test_file = _resolve_path(base_dir, args.test_file)
    output_file = _resolve_path(base_dir, args.output_file)

    for p, name in [(model_dir, "基座模型"), (adapter_dir, "LoRA 适配器"), (test_file, "测试集")]:
        if not p.exists():
            raise FileNotFoundError(f"找不到{name}: {p}")

    with open(test_file, encoding="utf-8") as f:
        test_data = json.load(f)
    total_data = len(test_data)
    if total_data == 0:
        print("测试集为空，退出")
        return

    if args.start_index < 0 or args.start_index >= total_data:
        raise ValueError(f"start-index 越界: {args.start_index}, 数据总量={total_data}")

    end_index = total_data if args.max_samples <= 0 else min(total_data, args.start_index + args.max_samples)
    target_indices = set(range(args.start_index, end_index))

    output_file.parent.mkdir(parents=True, exist_ok=True)

    if args.overwrite and output_file.exists():
        output_file.unlink()

    done_indices = set()
    if args.resume and output_file.exists():
        done_indices = _load_done_indices(output_file, args.start_index)
        done_indices = {i for i in done_indices if i in target_indices}

    pending_indices = [i for i in range(args.start_index, end_index) if i not in done_indices]
    if not pending_indices:
        print(f"无需运行：目标范围 {args.start_index}..{end_index - 1} 已全部完成")
        print(f"输出文件：{output_file}")
        return

    print(f"测试集总量：{total_data} 条")
    print(f"本次目标：{args.start_index}..{end_index - 1}（共 {len(target_indices)} 条）")
    print(f"已完成：{len(done_indices)} 条，待处理：{len(pending_indices)} 条")
    print("加载基座模型 (4-bit)...")

    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    )

    model = AutoModelForCausalLM.from_pretrained(
        str(model_dir),
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), trust_remote_code=True)

    print("加载 LoRA 适配器...")
    model = PeftModel.from_pretrained(model, str(adapter_dir))
    model.eval()

    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    output_mode = "a" if output_file.exists() and not args.overwrite else "w"
    run_start = time.time()
    newly_done = 0
    failed = 0

    print(f"开始推理，输出实时写入：{output_file}")
    with open(output_file, output_mode, encoding="utf-8") as out_f:
        for idx in pending_indices:
            item = test_data[idx]
            prompt = _build_prompt(item)

            try:
                messages = [{"role": "user", "content": prompt}]
                text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                inputs = tokenizer(
                    text,
                    return_tensors="pt",
                    truncation=True,
                    max_length=args.max_prompt_tokens,
                )

                model_device = model.device if hasattr(model, "device") else torch.device("cuda:0")
                inputs = {k: v.to(model_device) for k, v in inputs.items()}

                with torch.no_grad():
                    outputs = model.generate(
                        **inputs,
                        max_new_tokens=args.max_new_tokens,
                        do_sample=False,
                        use_cache=True,
                        pad_token_id=tokenizer.pad_token_id,
                    )

                generated = outputs[0][inputs["input_ids"].shape[1]:]
                prediction = tokenizer.decode(generated, skip_special_tokens=True).strip()
                record = {
                    "index": idx,
                    "predict": prediction,
                    "label": item.get("output", ""),
                    "instruction": item.get("instruction", ""),
                    "template_type": item.get("template_type", "unknown"),
                }
            except Exception as exc:  # noqa: BLE001
                failed += 1
                record = {
                    "index": idx,
                    "predict": "",
                    "label": item.get("output", ""),
                    "instruction": item.get("instruction", ""),
                    "template_type": item.get("template_type", "unknown"),
                    "error": str(exc),
                }

            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()

            newly_done += 1
            if args.log_every > 0 and newly_done % args.log_every == 0:
                elapsed = time.time() - run_start
                speed = newly_done / elapsed if elapsed > 0 else 0.0
                remaining = len(pending_indices) - newly_done
                eta_min = (remaining / speed / 60.0) if speed > 0 else float("inf")
                eta_text = f"{eta_min:.1f} 分钟" if speed > 0 else "未知"
                print(
                    f"  进度 {newly_done}/{len(pending_indices)} | "
                    f"速度 {speed:.2f} 条/秒 | 预计剩余 {eta_text}"
                )

            if torch.cuda.is_available() and newly_done % 20 == 0:
                torch.cuda.empty_cache()

    print("\n✅ 推理完成")
    print(f"新写入：{newly_done} 条，失败：{failed} 条")
    print(f"输出文件：{output_file}")


if __name__ == "__main__":
    main()
