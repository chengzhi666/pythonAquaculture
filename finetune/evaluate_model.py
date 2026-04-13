"""
第五步：ROUGE + BERTScore 评测脚本
对比基座模型和微调模型的预测结果，输出论文可用的评测表格
支持**按模板类型分组**输出指标（对应论文表 5-5 / 表 5-6）

使用方法：
  cd finetune
  python evaluate_model.py

依赖安装：
  pip install rouge-chinese bert-score jieba
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

TEMPLATE_LABELS = {
    "definition": "定义型",
    "reasoning": "推理型",
    "comparison": "对比型",
    "summary": "摘要型",
    "application": "应用型",
    "unknown": "未知",
}


def load_predictions(filepath: Path) -> list[dict]:
    """读取预测结果文件，返回包含 predict/label/template_type 的字典列表。"""
    rows: list[dict] = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            rows.append({
                "predict": data.get("predict", ""),
                "label": data.get("label", ""),
                "template_type": data.get("template_type", "unknown"),
            })
    return rows


def compute_rouge(predictions: list[str], references: list[str]) -> dict:
    """计算中文 ROUGE 分数"""
    import jieba
    from rouge_chinese import Rouge

    rouge = Rouge()

    # 结巴分词
    preds_seg = [" ".join(jieba.cut(p)) if p.strip() else "空" for p in predictions]
    refs_seg = [" ".join(jieba.cut(r)) if r.strip() else "空" for r in references]

    scores = rouge.get_scores(preds_seg, refs_seg, avg=True)
    return {
        "ROUGE-1 F1": round(scores["rouge-1"]["f"], 4),
        "ROUGE-2 F1": round(scores["rouge-2"]["f"], 4),
        "ROUGE-L F1": round(scores["rouge-l"]["f"], 4),
    }


def compute_bertscore(predictions: list[str], references: list[str]) -> dict:
    """计算 BERTScore"""
    from bert_score import score

    P, R, F1 = score(predictions, references, lang="zh", verbose=True)
    return {
        "BERTScore Precision": round(P.mean().item(), 4),
        "BERTScore Recall": round(R.mean().item(), 4),
        "BERTScore F1": round(F1.mean().item(), 4),
    }


def print_comparison_table(baseline_metrics: dict, finetuned_metrics: dict):
    """输出论文可用的对比表格（全量指标）。"""
    print("\n" + "=" * 65)
    print("表 5-X  基座模型与微调模型评测对比（全量）")
    print("=" * 65)
    print(f"{'指标':<22} {'基座模型':>12} {'微调模型':>12} {'提升':>10}")
    print("-" * 65)

    all_keys = list(baseline_metrics.keys())
    for key in all_keys:
        base_val = baseline_metrics.get(key, 0)
        ft_val = finetuned_metrics.get(key, 0)
        diff = ft_val - base_val
        sign = "+" if diff >= 0 else ""
        print(f"{key:<22} {base_val:>12.4f} {ft_val:>12.4f} {sign}{diff:>9.4f}")

    print("=" * 65)


def print_per_template_table(per_template: dict[str, dict], label: str):
    """输出按模板类型分组的指标表格（对应论文表 5-5）。"""
    if not per_template:
        return

    print(f"\n{'=' * 80}")
    print(f"表 5-X  {label} — 按模板类型分组评测结果")
    print(f"{'=' * 80}")
    header = f"{'模板类型':<10} {'样本数':>6} {'ROUGE-1':>9} {'ROUGE-2':>9} {'ROUGE-L':>9} {'BERTScore F1':>13}"
    print(header)
    print("-" * 80)

    # 按固定顺序输出
    order = ["definition", "reasoning", "comparison", "summary", "application", "unknown"]
    total_n = 0
    for ttype in order:
        m = per_template.get(ttype)
        if not m:
            continue
        zh_label = TEMPLATE_LABELS.get(ttype, ttype)
        n = m.get("sample_count", 0)
        total_n += n
        print(
            f"{zh_label:<10} {n:>6} "
            f"{m.get('ROUGE-1 F1', 0):>9.4f} "
            f"{m.get('ROUGE-2 F1', 0):>9.4f} "
            f"{m.get('ROUGE-L F1', 0):>9.4f} "
            f"{m.get('BERTScore F1', 0):>13.4f}"
        )

    print("-" * 80)
    print(f"{'合计':<10} {total_n:>6}")
    print("=" * 80)


def evaluate_single(filepath: Path, label: str) -> dict:
    """评测单个结果文件，返回全量指标 + 按模板分组指标。"""
    print(f"\n{'=' * 50}")
    print(f"评测：{label}")
    print(f"文件：{filepath}")
    print(f"{'=' * 50}")

    rows = load_predictions(filepath)
    preds = [r["predict"] for r in rows]
    refs = [r["label"] for r in rows]
    print(f"样本数：{len(preds)}")

    # 全量 ROUGE
    print("\n--- ROUGE ---")
    rouge_scores = compute_rouge(preds, refs)
    for k, v in rouge_scores.items():
        print(f"  {k}: {v}")

    # 全量 BERTScore
    print("\n--- BERTScore ---")
    bert_scores = compute_bertscore(preds, refs)
    for k, v in bert_scores.items():
        print(f"  {k}: {v}")

    all_metrics = {**rouge_scores, **bert_scores}

    # ── 按模板类型分组计算 ────────────────────────
    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        grouped[r["template_type"]].append(r)

    per_template: dict[str, dict] = {}
    for ttype, group_rows in sorted(grouped.items()):
        g_preds = [r["predict"] for r in group_rows]
        g_refs = [r["label"] for r in group_rows]
        try:
            g_rouge = compute_rouge(g_preds, g_refs)
        except Exception:
            g_rouge = {"ROUGE-1 F1": 0, "ROUGE-2 F1": 0, "ROUGE-L F1": 0}
        try:
            g_bert = compute_bertscore(g_preds, g_refs)
        except Exception:
            g_bert = {"BERTScore Precision": 0, "BERTScore Recall": 0, "BERTScore F1": 0}
        per_template[ttype] = {
            "sample_count": len(group_rows),
            **g_rouge,
            **g_bert,
        }

    print_per_template_table(per_template, label)

    return {"overall": all_metrics, "per_template": per_template}


def main():
    saves_dir = Path(__file__).parent / "saves"

    # LLaMA-Factory 预测输出的路径
    finetuned_pred = saves_dir / "finetuned_predictions.jsonl"
    # 备选：LLaMA-Factory predict 输出路径
    finetuned_pred_alt = saves_dir / "qwen2.5_1.5b_qlora_aquaculture" / "predict" / "generated_predictions.jsonl"
    if not finetuned_pred.exists() and finetuned_pred_alt.exists():
        finetuned_pred = finetuned_pred_alt
    baseline_pred = saves_dir / "baseline_predictions.jsonl"

    # 检查哪些文件存在
    has_finetuned = finetuned_pred.exists()
    has_baseline = baseline_pred.exists()

    if not has_finetuned and not has_baseline:
        print("错误：没有找到任何预测结果文件。")
        print(f"  微调模型预测：{finetuned_pred}")
        print(f"  基座模型预测：{baseline_pred}")
        print("\n请先完成以下步骤：")
        print("  1. 训练：cd LLaMA-Factory && llamafactory-cli train ../configs/qwen_qlora_sft.yaml")
        print("  2. 微调模型预测：llamafactory-cli train ../configs/qwen_qlora_predict.yaml")
        print("  3. 基座模型预测：python predict_baseline.py")
        return

    results = {}

    if has_baseline:
        results["baseline"] = evaluate_single(baseline_pred, "基座模型 (Qwen2.5-1.5B-Instruct)")

    if has_finetuned:
        results["finetuned"] = evaluate_single(finetuned_pred, "微调模型 (QLoRA)")

    # 如果两个都有，输出对比表
    if has_baseline and has_finetuned:
        print_comparison_table(results["baseline"]["overall"], results["finetuned"]["overall"])

    # 保存结果到 JSON
    output_json = saves_dir / "evaluation_results.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n评测结果已保存到：{output_json}")


if __name__ == "__main__":
    main()
