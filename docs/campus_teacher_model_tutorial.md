# 校园网接入老师模型教程

这份教程给在学校的同学使用，目标是完成 3 件事：

1. 确认电脑能访问老师提供的模型服务
2. 用脚本或图形客户端连上模型
3. 拿同一份图片 / PDF 页面和 `MinerU` 做对比

老师当前给的配置如下：

- 服务地址：`http://10.2.151.198:1998/v1`
- 模型 ID：`qwen3.6-27b`
- 模型类型：视觉模型
- API Key：老师单独提供

## 0. 先说最重要的

如果你不在校园网里，这个地址大概率连不上。

所以开始前先确认：

- 电脑已经连上学校 Wi-Fi 或有线校园网
- 没有被代理软件错误转发内网流量

如果你平时开着 Clash、v2ray、代理加速器，先把 `10.2.151.198` 设为直连。

## 1. 在 Windows 里先测连通性

打开 PowerShell，先运行：

```powershell
Test-NetConnection 10.2.151.198 -Port 1998
```

看输出里这行：

```text
TcpTestSucceeded : True
```

如果是 `True`，说明端口通了，可以继续。

如果是 `False`，优先检查：

- 是否真的在校园网
- 是否开了代理
- 是否输错了 IP 或端口

## 2. 检查代理环境变量

在 PowerShell 里运行：

```powershell
Get-ChildItem Env: | Where-Object { $_.Name -match 'proxy|PROXY' } | Format-Table -AutoSize
```

如果看到类似：

```text
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
ALL_PROXY=http://127.0.0.1:7890
```

说明电脑正在走代理。

这时建议临时执行：

```powershell
$env:NO_PROXY="localhost,127.0.0.1,::1,10.2.151.198"
```

如果代理软件支持规则配置，也建议把下面任一规则加进直连：

- `10.2.151.198`
- `10.0.0.0/8`

## 3. 测 OpenAI 兼容接口是否可用

先测模型列表接口：

```powershell
curl.exe --noproxy 10.2.151.198 -i http://10.2.151.198:1998/v1/models --max-time 10
```

可能出现几种情况：

- 返回 `200`：服务已通
- 返回 `401` / `403`：服务已通，但需要 API Key
- 返回 `timeout`：大概率没进校园网，或代理没绕过
- 返回 `502`：多半是代理干扰，不是模型本身一定挂了

## 4. 用本项目自带脚本测试模型

仓库里已经准备了测试脚本：

- [scripts/test_teacher_model.py](/C:/Users/qiaoruo/PycharmProjects/pythonAquaculture/scripts/test_teacher_model.py)

### 4.1 先设置 API Key

在 PowerShell 里执行：

```powershell
$env:TEACHER_MODEL_API_KEY="老师给你的API Key"
```

如果老师后面改了地址，也可以一起设置：

```powershell
$env:TEACHER_MODEL_BASE_URL="http://10.2.151.198:1998/v1"
$env:TEACHER_MODEL_ID="qwen3.6-27b"
```

### 4.2 先做文本连通性测试

```powershell
.\.venv\Scripts\python scripts\test_teacher_model.py --list-models
```

如果模型列表正常返回，再跑文本冒烟测试：

```powershell
.\.venv\Scripts\python scripts\test_teacher_model.py --text-ping
```

如果这一步成功，说明接口、密钥、模型 ID 基本都没问题。

### 4.3 跑一张图片做 OCR 测试

先准备一张论文页面截图或 PDF 转出来的图片，比如：

`demo_pdfs\page1.png`

然后运行：

```powershell
.\.venv\Scripts\python scripts\test_teacher_model.py --image demo_pdfs\page1.png --save-output tmp\teacher_model_page1.md
```

这会把模型输出保存到：

- `tmp\teacher_model_page1.md`

## 5. 如果你用图形客户端接入

如果你用的是支持 OpenAI 兼容接口的图形客户端，按下面填：

- Provider / 提供商：`Local` 或 `Custom OpenAI Compatible`
- Base URL：`http://10.2.151.198:1998/v1`
- API Key：老师给的 Key
- Model ID：`qwen3.6-27b`
- Model Name：`qwen3.6-27b`
- Model Type / 标签：`视觉模型`

建议参数：

- Temperature：`0.1`
- Top P：`0.1`
- Max Tokens：先用 `8192` 或 `16384`

如果老师那个客户端里已经显示 `131072`，也不用一开始就拉满，先小一点，排查更方便。

## 6. 建议统一的 OCR Prompt

为了和 `MinerU` 做公平对比，大家都用同一段提示词：

```text
请对这页学术论文图片进行OCR和版面理解，输出为Markdown。
要求：
1. 保留标题、正文、表格、图注和公式结构；
2. 表格尽量输出为Markdown表格，无法保证时可输出HTML表格；
3. 公式尽量保留为LaTeX形式；
4. 不要添加解释，不要总结；
5. 只输出转换结果本身。
```

## 7. 怎么和 MinerU 对比

老师的要求不是只看“能不能识别”，而是要看“总体效果谁更好”。

所以建议用同一批样本，统一比较下面几项：

- 正文完整性
- 跨页表格还原效果
- 公式识别效果
- 生僻字 / 行业术语识别效果
- 标点符号正确率

### 7.1 先跑 MinerU

如果样本已经在项目里，可以继续用：

```powershell
.\.venv\Scripts\python run_mineru_comparison.py --pdf-dir .\dist\ubuntu24-teacher-demo\test_pdfs --output .\results\demo_live
```

重点看：

- `results\demo_live\summary.json`
- `results\demo_live\comparison_table.csv`
- `results\demo_live\markdown\`

### 7.2 再跑老师的模型

把同一篇 PDF 的关键页面转成图片，喂给老师的视觉模型，输出 Markdown。

最后人工对照：

- 哪个模型正文更顺
- 哪个模型表格更完整
- 哪个模型公式更稳定
- 哪个模型对生僻字和行业术语更准

## 8. 常见故障排查

### 8.1 `timeout`

优先检查：

- 是否真的在校园网
- 是否开着代理
- 代理有没有给 `10.2.151.198` 走直连

### 8.2 `401 Unauthorized`

说明服务是通的，但 API Key 不对，重新找老师确认。

### 8.3 `404`

检查 Base URL 是否填成了：

```text
http://10.2.151.198:1998/v1
```

不要漏掉最后的 `/v1`。

### 8.4 文本测试通了，但图片 OCR 不通

说明接口本身没问题，重点检查：

- 模型是不是视觉模型
- 图片路径是否正确
- 图片是不是太大
- 客户端 / 脚本是不是按 OpenAI 兼容格式传了图片

## 9. 最后建议

第一次测试时，不要直接上整篇 PDF。

最稳的顺序是：

1. 先测 `models`
2. 再测文本对话
3. 再测单张图片 OCR
4. 最后再做正式对比

这样最容易定位问题，不会一上来就卡死在大任务上。
