"""
CNKI 全文采集可行性测试脚本 v3
================================
极简版：所有阻塞点都改为 input() 手动推进，不会自动超时卡死。
流程：首页登录 → 搜索 → 打开详情页 → 点"HTML阅读" → 提取全文

运行：python test_cnki_fulltext.py
"""

import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

THEME = os.getenv("CNKI_THEME", "三文鱼")
DEBUG_DIR = Path("cnki_debug")
DEBUG_DIR.mkdir(exist_ok=True)


def screenshot(page, name):
    try:
        page.screenshot(path=str(DEBUG_DIR / f"{name}.png"), full_page=False)
    except Exception:
        pass


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="msedge")
        context = browser.new_context(
            viewport={"width": 1600, "height": 1000},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        try:
            # ══════ Step 0: 登录 ══════
            print(f"\n{'='*60}")
            print("Step 0: 请在浏览器中登录知网")
            print(f"{'='*60}")

            login_page = context.new_page()
            login_page.goto("https://www.cnki.net/", wait_until="domcontentloaded")
            time.sleep(2)
            print("  浏览器已打开知网首页")
            print("  >>> 请在浏览器中完成机构登录 <<<")
            print("  >>> 登录完成后（或不需要登录），回到终端按 Enter <<<")
            input("  按 Enter 继续...")
            screenshot(login_page, "step0_after_login")
            login_page.close()

            # ══════ Step 1: 搜索 ══════
            print(f"\n{'='*60}")
            print(f"Step 1: 搜索 [{THEME}]")
            print(f"{'='*60}")

            page = context.new_page()
            page.set_default_timeout(15000)
            page.goto("https://kns.cnki.net/kns8/AdvSearch", wait_until="domcontentloaded")
            time.sleep(2)

            # 如果遇到滑块验证或登录页
            url = page.url or ""
            if "/verify/" in url or "captchaType" in url or "passport.cnki.net" in url:
                print("  遇到验证/登录，请在浏览器中处理")
                input("  处理完后按 Enter...")
                page.goto("https://kns.cnki.net/kns8/AdvSearch", wait_until="domcontentloaded")
                time.sleep(2)

            topic_xpath = (
                "//div[@class='gradeSearch']//dl[@id='gradetxt']"
                "/dd[1]//input[@type='text' and @maxlength='120']"
            )
            page.locator(f"xpath={topic_xpath}").fill(THEME)
            try:
                page.evaluate("document.querySelector('.search-sidebar-b')?.remove()")
            except Exception:
                pass

            page.locator(
                "xpath=//div[@class='search-buttons']/input[@class='btn-search']"
            ).click(force=True)
            time.sleep(4)

            # 等结果（简单轮询，遇阻塞则手动推进）
            rows = page.locator("table.result-table-list tbody tr")
            attempts = 0
            while rows.count() == 0 and attempts < 10:
                url = page.url or ""
                if "/verify/" in url or "passport.cnki.net" in url:
                    print("  遇到验证/登录，请在浏览器中处理")
                    input("  处理完后按 Enter...")
                time.sleep(1)
                rows = page.locator("table.result-table-list tbody tr")
                attempts += 1

            row_count = rows.count()
            if row_count == 0:
                print("  没有搜索结果，请检查浏览器")
                input("  按 Enter 退出...")
                return

            print(f"  找到 {row_count} 条结果")
            screenshot(page, "step1_results")

            # ══════ Step 2: 打开详情页 ══════
            print(f"\n{'='*60}")
            print("Step 2: 选择论文并打开详情页")
            print(f"{'='*60}")

            # 列出前几条
            chosen = 0
            for i in range(min(5, row_count)):
                row = rows.nth(i)
                try:
                    t = row.locator("a.fz14").first.inner_text(timeout=3000).strip()
                except Exception:
                    t = "?"
                try:
                    db = row.locator("td.data").inner_text(timeout=1000).strip()
                except Exception:
                    db = "?"
                is_chosen = " ← 选这篇" if i == chosen else ""
                print(f"  [{i+1}] {t[:50]}  ({db}){is_chosen}")
                # 跳过报纸
                if i == chosen and "报纸" in db and i + 1 < row_count:
                    chosen = i + 1

            target = rows.nth(chosen)
            title_link = target.locator("a.fz14").first
            list_title = title_link.inner_text(timeout=3000).strip()
            print(f"\n  打开第 {chosen+1} 篇: {list_title}")

            href = title_link.get_attribute("href") or ""
            if href.startswith("//"):
                href = "https:" + href
            elif href and not href.startswith("http"):
                href = "https://kns.cnki.net" + href

            detail = context.new_page()
            detail.set_default_timeout(15000)
            try:
                detail.goto(href, wait_until="domcontentloaded", timeout=20000)
            except PwTimeout:
                print("  加载超时（可能部分加载了）")
            time.sleep(3)

            # 处理验证/登录
            durl = detail.url or ""
            if "/verify/" in durl or "passport.cnki.net" in durl:
                print("  详情页遇到验证/登录，请在浏览器中处理")
                input("  处理完后按 Enter...")
                try:
                    detail.goto(href, wait_until="domcontentloaded", timeout=20000)
                except PwTimeout:
                    pass
                time.sleep(3)

            screenshot(detail, "step2_detail")

            # 提取元数据（短超时）
            title = list_title
            try:
                t = detail.locator("h1").first.inner_text(timeout=5000).strip()
                if len(t) > 3:
                    title = t
            except Exception:
                pass

            authors = ""
            try:
                h3s = detail.locator("h3")
                if h3s.count() > 0:
                    authors = h3s.first.inner_text(timeout=2000).strip()
            except Exception:
                pass

            abstract = ""
            try:
                abstract = detail.locator("span#ChDivSummary").inner_text(timeout=2000).strip()
            except Exception:
                pass

            keywords = ""
            try:
                keywords = detail.locator("p.keywords").inner_text(timeout=2000).strip()
            except Exception:
                pass

            print(f"\n  标题: {title}")
            print(f"  作者: {authors or '未获取'}")
            print(f"  关键词: {keywords or '未获取'}")
            print(f"  摘要: {(abstract or '未获取')[:100]}...")

            # ══════ Step 3: 找 HTML阅读 按钮 ══════
            print(f"\n{'='*60}")
            print("Step 3: 查找全文入口按钮")
            print(f"{'='*60}")

            all_a = detail.locator("a")
            a_count = all_a.count()
            print(f"  扫描 {a_count} 个链接...")

            found_links = []
            html_href = None

            for i in range(min(a_count, 200)):
                try:
                    a = all_a.nth(i)
                    txt = a.inner_text(timeout=300).strip()
                    h = (a.get_attribute("href") or "").strip()

                    # 跳过无关链接
                    if not h or any(bad in h.lower() for bad in [
                        "manual.html", "newhelper", "help", "javascript:void",
                        "passport.cnki.net", "mailto:", "weibo",
                    ]):
                        continue

                    lower = (txt + h).lower()
                    if any(kw in lower for kw in [
                        "html", "pdf", "caj", "全文", "阅读", "下载",
                    ]):
                        found_links.append((txt, h))
                        star = " ★★★" if "html" in lower and "阅读" in txt else ""
                        print(f"    \"{txt}\"  →  {h}{star}")
                        if "html" in lower and "阅读" in txt and not html_href:
                            html_href = h
                except Exception:
                    pass

            if not found_links:
                print("\n  未找到全文按钮！")
                # 保存HTML供分析
                try:
                    (DEBUG_DIR / "detail_page.html").write_text(
                        detail.content(), encoding="utf-8"
                    )
                    print(f"  已保存HTML到 {DEBUG_DIR}/detail_page.html")
                except Exception:
                    pass
                print("  请检查浏览器中详情页是否有全文按钮")
                input("  按 Enter 退出...")
                return

            if not html_href:
                print("\n  没找到「HTML阅读」但有其他链接")
                # 尝试选一个含 html 的
                for txt, h in found_links:
                    if "html" in (txt + h).lower():
                        html_href = h
                        break
                if not html_href:
                    html_href = found_links[0][1]

            # ══════ Step 4: 打开全文页 ══════
            print(f"\n{'='*60}")
            print("Step 4: 打开全文页")
            print(f"{'='*60}")

            if html_href.startswith("//"):
                html_href = "https:" + html_href
            elif not html_href.startswith("http"):
                html_href = "https://kns.cnki.net" + html_href

            print(f"  URL: {html_href}")

            ft = context.new_page()
            ft.set_default_timeout(20000)
            try:
                ft.goto(html_href, wait_until="domcontentloaded", timeout=25000)
            except PwTimeout:
                print("  加载超时（可能部分加载）")

            time.sleep(5)

            furl = ft.url or ""
            if "/verify/" in furl or "passport.cnki.net" in furl:
                print("  遇到验证/登录，请处理")
                input("  处理完后按 Enter...")
                time.sleep(2)

            # 检查是否跳到无关页面
            if any(b in ft.url for b in ["manual.html", "newhelper"]):
                print(f"  被重定向到无关页面: {ft.url}")
                print("  这个链接不对，尝试下一个...")
                ft.close()
                # 试其他链接
                for txt, h in found_links:
                    if h == html_href:
                        continue
                    if h.startswith("//"):
                        h = "https:" + h
                    elif not h.startswith("http"):
                        h = "https://kns.cnki.net" + h
                    if "manual" in h or "newhelper" in h:
                        continue
                    print(f"  尝试: \"{txt}\" → {h}")
                    ft = context.new_page()
                    try:
                        ft.goto(h, wait_until="domcontentloaded", timeout=25000)
                    except PwTimeout:
                        pass
                    time.sleep(4)
                    if "manual" not in ft.url and "newhelper" not in ft.url:
                        break
                    ft.close()
                else:
                    print("  所有链接都指向无关页面")
                    input("  按 Enter 退出...")
                    return

            screenshot(ft, "step4_fulltext")
            print(f"  落地URL: {ft.url}")

            # ══════ Step 5: 提取全文 ══════
            print(f"\n{'='*60}")
            print("Step 5: 提取全文")
            print(f"{'='*60}")

            full_text = ""
            matched_sel = ""

            selectors = [
                "div.doc",
                "div#mainArea",
                "div.article-body",
                "div.w-main",
                "div.main",
                "div.p-main",
                "article",
                "div.content",
                "div[class*='article']",
                "div[class*='content']",
                "div[class*='body']",
            ]

            for sel in selectors:
                try:
                    loc = ft.locator(sel)
                    if loc.count() == 0:
                        continue
                    txt = loc.first.inner_text(timeout=8000).strip()
                    chars = len(txt)
                    if chars > 50:
                        print(f"  {sel}: {chars} 字符")
                    if chars > len(full_text):
                        full_text = txt
                        matched_sel = sel
                except Exception:
                    pass

            # 兜底
            if len(full_text) < 500:
                try:
                    body = ft.locator("body").inner_text(timeout=8000).strip()
                    print(f"  body: {len(body)} 字符")
                    if len(body) > len(full_text):
                        full_text = body
                        matched_sel = "body"
                except Exception:
                    pass

            # 保存原始HTML
            try:
                (DEBUG_DIR / "fulltext_page.html").write_text(
                    ft.content(), encoding="utf-8"
                )
            except Exception:
                pass

            # ══════ 结果 ══════
            print(f"\n{'='*60}")
            print("测试结果")
            print(f"{'='*60}")
            print(f"  标题:     {title}")
            print(f"  作者:     {authors or '未获取'}")
            print(f"  关键词:   {keywords or '未获取'}")
            print(f"  摘要:     {'✓ ' + str(len(abstract)) + '字' if abstract else '✗'}")
            print(f"  选择器:   {matched_sel}")
            print(f"  全文长度: {len(full_text)} 字符")

            if len(full_text) > 200:
                print(f"\n  ✓ 全文采集成功！共 {len(full_text)} 字符")

                out = f"CNKI_fulltext_test_{THEME}.txt"
                with open(out, "w", encoding="utf-8") as f:
                    f.write(f"标题: {title}\n")
                    f.write(f"作者: {authors}\n")
                    f.write(f"关键词: {keywords}\n")
                    f.write(f"摘要: {abstract}\n")
                    f.write(f"详情页: {detail.url}\n")
                    f.write(f"全文页: {ft.url}\n")
                    f.write(f"选择器: {matched_sel}\n")
                    f.write(f"全文字符: {len(full_text)}\n")
                    f.write(f"{'='*60}\n\n")
                    f.write(full_text)
                print(f"  保存到: {out}")

                print(f"\n{'='*60}")
                print("全文预览（前 2000 字）")
                print(f"{'='*60}")
                print(full_text[:2000])
                if len(full_text) > 2000:
                    print(f"\n... 共 {len(full_text)} 字符")
            else:
                print(f"\n  ✗ 全文提取失败或内容太短")
                print(f"  调试文件在 {DEBUG_DIR}/ 目录")

            print(f"\n  >>> 按 Enter 关闭浏览器退出 <<<")
            input()

            ft.close()
            detail.close()
            page.close()

        finally:
            browser.close()


if __name__ == "__main__":
    main()
