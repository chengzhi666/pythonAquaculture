from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path

import requests

DEFAULT_BASE_URL = "http://10.2.151.198:1998/v1"
DEFAULT_MODEL = "qwen3.6-27b"
DEFAULT_PROMPT = (
    "请对这页学术论文图片进行OCR和版面理解，输出为Markdown。\n"
    "要求：\n"
    "1. 保留标题、正文、表格、图注和公式结构；\n"
    "2. 表格尽量输出为Markdown表格，无法保证时可输出HTML表格；\n"
    "3. 公式尽量保留为LaTeX形式；\n"
    "4. 不要添加解释，不要总结；\n"
    "5. 只输出转换结果本身。"
)


def build_session(use_env_proxy: bool) -> requests.Session:
    session = requests.Session()
    session.trust_env = use_env_proxy
    return session


def make_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def list_models(session: requests.Session, base_url: str, api_key: str, timeout: int) -> None:
    response = session.get(
        f"{base_url.rstrip('/')}/models",
        headers=make_headers(api_key),
        timeout=timeout,
    )
    print(f"[models] status={response.status_code}")
    print(response.text)
    response.raise_for_status()


def make_data_url(image_path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(image_path.name)
    if not mime_type:
        mime_type = "image/png"
    image_bytes = image_path.read_bytes()
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def chat_completion(
    session: requests.Session,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    timeout: int,
    temperature: float,
    top_p: float,
    max_tokens: int,
) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
    }
    response = session.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers=make_headers(api_key),
        data=json.dumps(payload, ensure_ascii=False),
        timeout=timeout,
    )
    print(f"[chat] status={response.status_code}")
    print(response.text[:2000])
    response.raise_for_status()
    return response.json()


def extract_text(response_json: dict) -> str:
    choices = response_json.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(part for part in parts if part)
    return str(content)


def main() -> None:
    parser = argparse.ArgumentParser(description="测试老师提供的 OpenAI 兼容视觉模型接口。")
    parser.add_argument(
        "--base-url",
        default=os.getenv("TEACHER_MODEL_BASE_URL", DEFAULT_BASE_URL),
        help=f"模型服务地址，默认 {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("TEACHER_MODEL_API_KEY", ""),
        help="API Key，也可通过环境变量 TEACHER_MODEL_API_KEY 传入。",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("TEACHER_MODEL_ID", DEFAULT_MODEL),
        help=f"模型 ID，默认 {DEFAULT_MODEL}",
    )
    parser.add_argument("--list-models", action="store_true", help="先请求 /models。")
    parser.add_argument("--text-ping", action="store_true", help="执行一次纯文本连通性测试。")
    parser.add_argument("--image", type=Path, help="传入一张本地图片做 OCR 测试。")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="图片 OCR 时使用的提示词。")
    parser.add_argument("--save-output", type=Path, help="将模型文本输出保存到文件。")
    parser.add_argument("--timeout", type=int, default=60, help="请求超时时间（秒）。")
    parser.add_argument("--temperature", type=float, default=0.1, help="采样温度。")
    parser.add_argument("--top-p", type=float, default=0.1, help="Top P。")
    parser.add_argument("--max-tokens", type=int, default=8192, help="最大输出 token 数。")
    parser.add_argument(
        "--use-env-proxy",
        action="store_true",
        help="默认脚本会绕过系统代理；加上这个参数后改为使用环境变量代理。",
    )
    args = parser.parse_args()

    session = build_session(use_env_proxy=args.use_env_proxy)

    if args.list_models:
        list_models(session, args.base_url, args.api_key, args.timeout)

    response_json: dict | None = None

    if args.text_ping:
        response_json = chat_completion(
            session=session,
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            timeout=args.timeout,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=min(args.max_tokens, 1024),
            messages=[
                {"role": "system", "content": "你是一个擅长OCR和文档解析的助手。"},
                {"role": "user", "content": "请简单介绍你是否支持图像OCR和学术论文文档解析。"},
            ],
        )

    if args.image:
        if not args.image.exists():
            raise FileNotFoundError(f"图片不存在：{args.image}")
        data_url = make_data_url(args.image)
        response_json = chat_completion(
            session=session,
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            timeout=args.timeout,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
            messages=[
                {"role": "system", "content": "你是一个擅长OCR和文档解析的助手。"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": args.prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
        )

    if response_json and args.save_output:
        output_text = extract_text(response_json)
        args.save_output.parent.mkdir(parents=True, exist_ok=True)
        args.save_output.write_text(output_text, encoding="utf-8")
        print(f"[saved] {args.save_output}")


if __name__ == "__main__":
    main()
