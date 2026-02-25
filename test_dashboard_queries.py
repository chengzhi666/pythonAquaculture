"""测试 dashboard_queries 模块的所有函数。"""

import sys
from pathlib import Path

# 确保能导入项目模块
sys.path.insert(0, str(Path(__file__).parent))

from query import dashboard_queries as dq


def test_all():
    """测试所有查询函数。"""
    print("=" * 80)
    print("开始测试 dashboard_queries 模块")
    print("=" * 80)

    # 1. 总量统计
    print("\n[1] 测试 get_total_counts()")
    try:
        counts = dq.get_total_counts()
        print(f"✓ 成功：{counts}")
    except Exception as e:
        print(f"✗ 失败：{e}")

    # 2. 来源分布
    print("\n[2] 测试 get_source_stats()")
    try:
        stats = dq.get_source_stats()
        print(f"✓ 成功：查询到 {len(stats)} 种来源")
        for row in stats[:3]:
            print(f"   - {row}")
    except Exception as e:
        print(f"✗ 失败：{e}")

    # 3. 商品统计
    print("\n[3] 测试 get_product_stats()")
    try:
        stats = dq.get_product_stats()
        print(f"✓ 成功：查询到 {len(stats)} 种平台-品种组合")
        for row in stats[:3]:
            print(f"   - {row}")
    except Exception as e:
        print(f"✗ 失败：{e}")

    # 4. 每日趋势
    print("\n[4] 测试 get_daily_trend(days=7)")
    try:
        trend = dq.get_daily_trend(days=7)
        print(f"✓ 成功：查询到 {len(trend)} 天数据")
        for row in trend[:3]:
            print(f"   - {row}")
    except Exception as e:
        print(f"✗ 失败：{e}")

    # 5. 采集运行记录
    print("\n[5] 测试 get_recent_crawl_runs(limit=5)")
    try:
        runs = dq.get_recent_crawl_runs(limit=5)
        print(f"✓ 成功：查询到 {len(runs)} 条运行记录")
        for row in runs[:3]:
            print(f"   - {row.get('source_name')} | {row.get('status')} | {row.get('items')} 条")
    except Exception as e:
        print(f"✗ 失败：{e}")

    # 6. 商品快照
    print("\n[6] 测试 get_product_snapshots(limit=5)")
    try:
        products = dq.get_product_snapshots(limit=5)
        print(f"✓ 成功：查询到 {len(products)} 条商品")
        for row in products[:2]:
            print(f"   - {row.get('title')[:40]}... | ¥{row.get('price')}")
    except Exception as e:
        print(f"✗ 失败：{e}")

    # 7. 价格趋势（单品种）
    print("\n[7] 测试 get_price_trend(product_type='虹鳟', days=30)")
    try:
        trend = dq.get_price_trend("虹鳟", days=30)
        print(f"✓ 成功：查询到 {len(trend)} 天价格数据")
        for row in trend[:3]:
            print(f"   - {row}")
    except Exception as e:
        print(f"✗ 失败：{e}")

    # 8. 价格趋势（多品种）
    print("\n[8] 测试 get_price_trend_by_species(days=30)")
    try:
        trend = dq.get_price_trend_by_species(days=30)
        print(f"✓ 成功：查询到 {len(trend)} 条品种-日期价格数据")
        for row in trend[:3]:
            print(f"   - {row}")
    except Exception as e:
        print(f"✗ 失败：{e}")

    # 9. 品种-产地价格
    print("\n[9] 测试 get_price_by_species_origin(days=30)")
    try:
        prices = dq.get_price_by_species_origin(days=30)
        print(f"✓ 成功：查询到 {len(prices)} 种品种-产地组合")
        for row in prices[:3]:
            print(f"   - {row}")
    except Exception as e:
        print(f"✗ 失败：{e}")

    # 10. 价格排行
    print("\n[10] 测试 get_recent_products_by_price(limit=5)")
    try:
        products = dq.get_recent_products_by_price(limit=5)
        print(f"✓ 成功：查询到 {len(products)} 条商品")
        for row in products[:3]:
            print(f"   - {row.get('title')[:40]}... | ¥{row.get('price')}")
    except Exception as e:
        print(f"✗ 失败：{e}")

    # 11. 论文检索
    print("\n[11] 测试 get_papers(keyword='', limit=5)")
    try:
        papers = dq.get_papers(keyword="", limit=5)
        print(f"✓ 成功：查询到 {len(papers)} 篇论文")
        for row in papers[:2]:
            print(f"   - {row.get('title')[:50]}...")
    except Exception as e:
        print(f"✗ 失败：{e}")

    # 12. 获取筛选选项
    print("\n[12] 测试 get_distinct_platforms()")
    try:
        platforms = dq.get_distinct_platforms()
        print(f"✓ 成功：{platforms}")
    except Exception as e:
        print(f"✗ 失败：{e}")

    print("\n[13] 测试 get_distinct_species()")
    try:
        species = dq.get_distinct_species()
        print(f"✓ 成功：{species}")
    except Exception as e:
        print(f"✗ 失败：{e}")

    print("\n[14] 测试 get_distinct_source_types()")
    try:
        types = dq.get_distinct_source_types()
        print(f"✓ 成功：{types}")
    except Exception as e:
        print(f"✗ 失败：{e}")

    # 15. 增强版情报查询
    print("\n[15] 测试 query_intel_enhanced(keyword='', limit=5)")
    try:
        items = dq.query_intel_enhanced(keyword="", limit=5)
        print(f"✓ 成功：查询到 {len(items)} 条情报")
        for row in items[:2]:
            print(f"   - {row.get('title')[:50]}... | {row.get('source_type')}")
    except Exception as e:
        print(f"✗ 失败：{e}")

    print("\n" + "=" * 80)
    print("所有测试完成")
    print("=" * 80)


if __name__ == "__main__":
    test_all()
