(function () {
  const DEMO_DATA = {
    currentDate: '2026-04-15',
    lineage: '多源异构自动化采集模块',
    dashboard: {
      stats: {
        paper_meta: 1482,
        product_snapshot: 5824,
        offline_price_snapshot: 1462,
        intel_item: 933,
        raw_event: 10417,
      },
      overview: {
        counts: {
          papers: 1482,
          products: 5824,
          intel_items: 933,
          crawl_runs: 128,
        },
        source_stats: [
          {source_type: 'CNKI论文', count: 1482},
          {source_type: '京东商品', count: 2210},
          {source_type: '淘宝商品', count: 1884},
          {source_type: 'MOA政策', count: 933},
          {source_type: 'MOA线下价格', count: 1462},
        ],
        product_stats: [
          {platform: 'jd', product_type: '三文鱼', count: 762},
          {platform: 'taobao', product_type: '三文鱼', count: 621},
          {platform: 'jd', product_type: '虹鳟', count: 402},
          {platform: 'taobao', product_type: '大黄鱼', count: 517},
        ],
        kpis: {
          window_days: 30,
          monitor_avg_price: 118.6,
          online_offline_spread: 54.2,
          sample_count_30d: 8214,
        },
      },
      dailyTrend: [
        {date: '2026-03-17', intel_items: 18, products: 126},
        {date: '2026-03-20', intel_items: 21, products: 148},
        {date: '2026-03-23', intel_items: 19, products: 163},
        {date: '2026-03-26', intel_items: 24, products: 172},
        {date: '2026-03-29', intel_items: 26, products: 188},
        {date: '2026-04-01', intel_items: 28, products: 214},
        {date: '2026-04-04', intel_items: 25, products: 236},
        {date: '2026-04-07', intel_items: 31, products: 251},
        {date: '2026-04-10', intel_items: 34, products: 269},
        {date: '2026-04-13', intel_items: 36, products: 284},
      ],
      priceTrend: [
        {date: '2026-03-17', product_type: '三文鱼', avg_price: 126.2},
        {date: '2026-03-20', product_type: '三文鱼', avg_price: 124.8},
        {date: '2026-03-23', product_type: '三文鱼', avg_price: 123.6},
        {date: '2026-03-26', product_type: '三文鱼', avg_price: 122.9},
        {date: '2026-03-29', product_type: '三文鱼', avg_price: 121.7},
        {date: '2026-04-01', product_type: '三文鱼', avg_price: 120.8},
        {date: '2026-04-04', product_type: '三文鱼', avg_price: 119.6},
        {date: '2026-04-07', product_type: '三文鱼', avg_price: 118.5},
        {date: '2026-04-10', product_type: '三文鱼', avg_price: 117.8},
        {date: '2026-04-13', product_type: '三文鱼', avg_price: 116.9},
        {date: '2026-03-17', product_type: '虹鳟', avg_price: 91.4},
        {date: '2026-03-20', product_type: '虹鳟', avg_price: 90.8},
        {date: '2026-03-23', product_type: '虹鳟', avg_price: 90.1},
        {date: '2026-03-26', product_type: '虹鳟', avg_price: 89.6},
        {date: '2026-03-29', product_type: '虹鳟', avg_price: 88.7},
        {date: '2026-04-01', product_type: '虹鳟', avg_price: 88.1},
        {date: '2026-04-04', product_type: '虹鳟', avg_price: 87.6},
        {date: '2026-04-07', product_type: '虹鳟', avg_price: 87.1},
        {date: '2026-04-10', product_type: '虹鳟', avg_price: 86.8},
        {date: '2026-04-13', product_type: '虹鳟', avg_price: 86.0},
        {date: '2026-03-17', product_type: '大黄鱼', avg_price: 78.8},
        {date: '2026-03-20', product_type: '大黄鱼', avg_price: 79.1},
        {date: '2026-03-23', product_type: '大黄鱼', avg_price: 79.4},
        {date: '2026-03-26', product_type: '大黄鱼', avg_price: 80.2},
        {date: '2026-03-29', product_type: '大黄鱼', avg_price: 81.0},
        {date: '2026-04-01', product_type: '大黄鱼', avg_price: 81.8},
        {date: '2026-04-04', product_type: '大黄鱼', avg_price: 82.6},
        {date: '2026-04-07', product_type: '大黄鱼', avg_price: 83.1},
        {date: '2026-04-10', product_type: '大黄鱼', avg_price: 83.9},
        {date: '2026-04-13', product_type: '大黄鱼', avg_price: 84.4},
        {date: '2026-03-17', product_type: '罗非鱼', avg_price: 56.5},
        {date: '2026-03-20', product_type: '罗非鱼', avg_price: 56.2},
        {date: '2026-03-23', product_type: '罗非鱼', avg_price: 55.8},
        {date: '2026-03-26', product_type: '罗非鱼', avg_price: 55.6},
        {date: '2026-03-29', product_type: '罗非鱼', avg_price: 55.2},
        {date: '2026-04-01', product_type: '罗非鱼', avg_price: 55.0},
        {date: '2026-04-04', product_type: '罗非鱼', avg_price: 54.8},
        {date: '2026-04-07', product_type: '罗非鱼', avg_price: 54.4},
        {date: '2026-04-10', product_type: '罗非鱼', avg_price: 54.1},
        {date: '2026-04-13', product_type: '罗非鱼', avg_price: 53.8},
      ],
      speciesOrigin: [
        {product_type: '三文鱼', origin: '挪威', avg_price: 132.8, count: 218},
        {product_type: '三文鱼', origin: '智利', avg_price: 118.4, count: 174},
        {product_type: '虹鳟', origin: '青海', avg_price: 88.6, count: 132},
        {product_type: '虹鳟', origin: '甘肃', avg_price: 92.1, count: 108},
        {product_type: '大黄鱼', origin: '福建', avg_price: 82.7, count: 156},
        {product_type: '大黄鱼', origin: '浙江', avg_price: 79.5, count: 121},
        {product_type: '罗非鱼', origin: '广东', avg_price: 55.1, count: 192},
        {product_type: '罗非鱼', origin: '海南', avg_price: 57.6, count: 128},
      ],
      priceRanking: [
        {title: '挪威冰鲜三文鱼整鱼 4kg 级', platform: 'jd', price: 168.0, origin_standardized: '挪威', snapshot_time: '2026-04-13 09:12:00'},
        {title: '智利帝王鲑刺身中段礼盒装', platform: 'taobao', price: 156.0, origin_standardized: '智利', snapshot_time: '2026-04-13 08:42:00'},
        {title: '日本料理级三文鱼菲力整条', platform: 'jd', price: 149.0, origin_standardized: '挪威', snapshot_time: '2026-04-12 18:20:00'},
        {title: '挪威三文鱼冷熏切片家庭装', platform: 'taobao', price: 144.0, origin_standardized: '挪威', snapshot_time: '2026-04-12 16:31:00'},
        {title: '冰鲜帝王鲑排酸即食套装', platform: 'jd', price: 141.0, origin_standardized: '冰岛', snapshot_time: '2026-04-12 10:45:00'},
        {title: '深海大黄鱼礼盒装', platform: 'taobao', price: 118.0, origin_standardized: '福建', snapshot_time: '2026-04-11 20:10:00'},
        {title: '精品虹鳟冷鲜整条 2.5kg', platform: 'jd', price: 96.0, origin_standardized: '青海', snapshot_time: '2026-04-11 19:02:00'},
        {title: '淡水罗非鱼净膛免杀套装', platform: 'taobao', price: 61.0, origin_standardized: '广东', snapshot_time: '2026-04-11 11:18:00'},
        {title: '青海高原虹鳟鱼柳装', platform: 'jd', price: 89.0, origin_standardized: '青海', snapshot_time: '2026-04-10 14:26:00'},
        {title: '家庭装罗非鱼柳 1kg', platform: 'jd', price: 56.0, origin_standardized: '海南', snapshot_time: '2026-04-10 09:41:00'},
      ],
      crawlRuns: [
        {source_name: 'jd', status: 'OK', items: 286, started_at: '2026-04-13 08:00:00', ended_at: '2026-04-13 08:18:00', error_text: ''},
        {source_name: 'taobao', status: 'OK', items: 248, started_at: '2026-04-13 08:20:00', ended_at: '2026-04-13 08:39:00', error_text: ''},
        {source_name: 'moa_prices', status: 'OK', items: 112, started_at: '2026-04-13 07:40:00', ended_at: '2026-04-13 07:49:00', error_text: ''},
        {source_name: 'moa', status: 'OK', items: 39, started_at: '2026-04-12 23:10:00', ended_at: '2026-04-12 23:15:00', error_text: ''},
        {source_name: 'cnki', status: 'RUNNING', items: 0, started_at: '2026-04-15 09:20:00', ended_at: '', error_text: ''},
        {source_name: 'taobao', status: 'ERROR', items: 0, started_at: '2026-04-12 21:00:00', ended_at: '2026-04-12 21:03:00', error_text: 'Cookie 已失效，已在演示数据中模拟异常闭环。'},
      ],
      papers: [
        {id: 1, theme: '三文鱼产业链', title: '多源异构数据驱动下的三文鱼价格监测框架研究', authors: '陈志, 刘洋', source: '农业工程学报', pub_date: '2025-10-12', abstract: '围绕价格采集、平台对比与趋势分析构建监测体系。', keywords_json: '["三文鱼","价格监测","多源采集"]', url: 'https://example.com/paper/1', fetched_at: '2026-04-13 09:18:00'},
        {id: 2, theme: '水产情报', title: '渔业政策文本与市场行情融合分析方法', authors: '王晨, 李睿', source: '中国渔业经济', pub_date: '2025-08-09', abstract: '提出政策信号与价格趋势联动建模思路。', keywords_json: '["渔业政策","行情分析"]', url: 'https://example.com/paper/2', fetched_at: '2026-04-13 09:12:00'},
        {id: 3, theme: '虹鳟识别', title: '面向电商标题的虹鳟与帝王鲑规则抽取', authors: '周敏', source: '计算机工程应用', pub_date: '2025-05-21', abstract: '利用规则与词典识别品种、规格和产地信息。', keywords_json: '["虹鳟","帝王鲑","规则抽取"]', url: 'https://example.com/paper/3', fetched_at: '2026-04-11 14:06:00'},
        {id: 4, theme: '价格预测', title: '基于时间序列的冷链水产品价格波动预测', authors: '赵晴, 孙伟', source: '系统工程理论与实践', pub_date: '2025-11-03', abstract: '构建近实时价格波动监测和短期预测模型。', keywords_json: '["时间序列","价格预测"]', url: 'https://example.com/paper/4', fetched_at: '2026-04-10 18:30:00'},
        {id: 5, theme: '采集系统', title: '面向农业垂直领域的多源自动化采集链路设计', authors: '许哲', source: '软件导刊', pub_date: '2025-07-18', abstract: '讨论从调度、证据入库到可视化的全链路实现。', keywords_json: '["自动化采集","系统设计"]', url: 'https://example.com/paper/5', fetched_at: '2026-04-08 10:21:00'},
      ],
      products: [
        {id: 101, platform: 'jd', keyword: '三文鱼', title: '挪威冰鲜三文鱼刺身中段 500g', price: 138.0, original_price: 149.0, sales_or_commit: '月销 1.2万+', shop: '京海生鲜旗舰店', province: '北京', city: '北京', detail_url: 'https://example.com/product/101', snapshot_time: '2026-04-13 09:22:00'},
        {id: 102, platform: 'taobao', keyword: '三文鱼', title: '智利三文鱼切片家庭装 1kg', price: 116.0, original_price: 126.0, sales_or_commit: '已售 8600+', shop: '蓝港海鲜', province: '上海', city: '上海', detail_url: 'https://example.com/product/102', snapshot_time: '2026-04-13 08:54:00'},
        {id: 103, platform: 'jd', keyword: '虹鳟', title: '高原虹鳟鱼柳礼盒装', price: 92.0, original_price: 99.0, sales_or_commit: '月销 3200+', shop: '青海优品', province: '青海', city: '西宁', detail_url: 'https://example.com/product/103', snapshot_time: '2026-04-12 16:10:00'},
        {id: 104, platform: 'taobao', keyword: '帝王鲑', title: '帝王鲑中段料理级 400g', price: 152.0, original_price: 168.0, sales_or_commit: '已售 2200+', shop: '海境优选', province: '浙江', city: '宁波', detail_url: 'https://example.com/product/104', snapshot_time: '2026-04-12 13:42:00'},
        {id: 105, platform: 'jd', keyword: '大黄鱼', title: '福建深海大黄鱼礼盒', price: 84.0, original_price: 89.0, sales_or_commit: '月销 5400+', shop: '闽海鲜仓', province: '福建', city: '福州', detail_url: 'https://example.com/product/105', snapshot_time: '2026-04-11 10:16:00'},
      ],
      offlinePrices: [
        {id: 201, source_name: '农业农村部', market_name: '北京新发地', region: '北京', product_type: '三文鱼', product_name_raw: '三文鱼（冰鲜）', min_price: 86.0, max_price: 94.0, price: 90.2, unit: '元/公斤', storage_method: '冷鲜', snapshot_time: '2026-04-13 07:36:00'},
        {id: 202, source_name: '农业农村部', market_name: '上海江桥', region: '上海', product_type: '虹鳟', product_name_raw: '虹鳟鱼', min_price: 68.0, max_price: 74.0, price: 71.0, unit: '元/公斤', storage_method: '冷鲜', snapshot_time: '2026-04-12 07:28:00'},
        {id: 203, source_name: '农业农村部', market_name: '广州江南', region: '广东', product_type: '罗非鱼', product_name_raw: '罗非鱼', min_price: 26.0, max_price: 33.0, price: 29.4, unit: '元/公斤', storage_method: '鲜活', snapshot_time: '2026-04-11 06:58:00'},
        {id: 204, source_name: '农业农村部', market_name: '福州海峡', region: '福建', product_type: '大黄鱼', product_name_raw: '大黄鱼', min_price: 54.0, max_price: 62.0, price: 58.3, unit: '元/公斤', storage_method: '冷鲜', snapshot_time: '2026-04-10 08:10:00'},
      ],
      intel: [
        {id: 301, source_type: 'MOA政策', title: '关于推进现代渔业高质量发展的指导意见', pub_time: '2026-04-08', org: '农业农村部', region: '全国', content: '强调智慧渔业、冷链物流与质量安全追溯体系建设。', source_url: 'https://example.com/intel/301', fetched_at: '2026-04-08 09:20:00'},
        {id: 302, source_type: 'MOA政策', title: '2026年重点水产品稳产保供工作提示', pub_time: '2026-03-29', org: '农业农村部渔业渔政管理局', region: '全国', content: '提出重点监测大宗与高价值水产品价格波动。', source_url: 'https://example.com/intel/302', fetched_at: '2026-03-29 15:18:00'},
        {id: 303, source_type: '地方政策', title: '青海省虹鳟产业提质增效实施方案', pub_time: '2026-03-20', org: '青海省农业农村厅', region: '青海', content: '聚焦品牌化和标准化，推动高原冷水鱼价格提升。', source_url: 'https://example.com/intel/303', fetched_at: '2026-03-20 10:42:00'},
      ],
    },
    salmon: {
      trend: [
        {date: '2026-03-17', platform: 'jd', avg_price: 142.2, count: 84},
        {date: '2026-03-20', platform: 'jd', avg_price: 140.8, count: 86},
        {date: '2026-03-23', platform: 'jd', avg_price: 139.4, count: 88},
        {date: '2026-03-26', platform: 'jd', avg_price: 138.7, count: 92},
        {date: '2026-03-29', platform: 'jd', avg_price: 136.9, count: 95},
        {date: '2026-04-01', platform: 'jd', avg_price: 135.8, count: 94},
        {date: '2026-04-04', platform: 'jd', avg_price: 134.6, count: 91},
        {date: '2026-04-07', platform: 'jd', avg_price: 133.4, count: 89},
        {date: '2026-04-10', platform: 'jd', avg_price: 131.8, count: 87},
        {date: '2026-04-13', platform: 'jd', avg_price: 130.4, count: 86},
        {date: '2026-03-17', platform: 'taobao', avg_price: 122.6, count: 72},
        {date: '2026-03-20', platform: 'taobao', avg_price: 121.9, count: 73},
        {date: '2026-03-23', platform: 'taobao', avg_price: 120.8, count: 75},
        {date: '2026-03-26', platform: 'taobao', avg_price: 119.6, count: 74},
        {date: '2026-03-29', platform: 'taobao', avg_price: 118.7, count: 76},
        {date: '2026-04-01', platform: 'taobao', avg_price: 117.5, count: 78},
        {date: '2026-04-04', platform: 'taobao', avg_price: 116.8, count: 77},
        {date: '2026-04-07', platform: 'taobao', avg_price: 115.9, count: 75},
        {date: '2026-04-10', platform: 'taobao', avg_price: 114.8, count: 73},
        {date: '2026-04-13', platform: 'taobao', avg_price: 113.8, count: 72},
      ],
      species: [
        {platform: 'all', species: '三文鱼', count: 952},
        {platform: 'all', species: '帝王鲑', count: 411},
        {platform: 'all', species: '虹鳟', count: 238},
        {platform: 'jd', species: '三文鱼', count: 512},
        {platform: 'jd', species: '帝王鲑', count: 228},
        {platform: 'jd', species: '虹鳟', count: 102},
        {platform: 'taobao', species: '三文鱼', count: 440},
        {platform: 'taobao', species: '帝王鲑', count: 183},
        {platform: 'taobao', species: '虹鳟', count: 136},
      ],
      origins: [
        {platform: 'all', origin: '挪威', count: 612},
        {platform: 'all', origin: '智利', count: 428},
        {platform: 'all', origin: '青海', count: 216},
        {platform: 'all', origin: '冰岛', count: 145},
        {platform: 'all', origin: '甘肃', count: 118},
        {platform: 'all', origin: '丹麦', count: 82},
        {platform: 'jd', origin: '挪威', count: 352},
        {platform: 'jd', origin: '智利', count: 196},
        {platform: 'jd', origin: '冰岛', count: 104},
        {platform: 'jd', origin: '青海', count: 88},
        {platform: 'jd', origin: '甘肃', count: 54},
        {platform: 'taobao', origin: '挪威', count: 260},
        {platform: 'taobao', origin: '智利', count: 232},
        {platform: 'taobao', origin: '青海', count: 128},
        {platform: 'taobao', origin: '甘肃', count: 64},
        {platform: 'taobao', origin: '丹麦', count: 82},
      ],
      compare: [
        {platform: 'jd', channel: '京东线上', avg_price: 130.4, count: 842},
        {platform: 'taobao', channel: '淘宝线上', avg_price: 113.8, count: 691},
        {platform: 'offline', channel: '线下批发(MOA)', avg_price: 89.7, count: 309},
      ],
    },
  };

  const demoTasks = {};
  let taskSeed = 1;

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function parseDate(value) {
    const text = String(value || '').slice(0, 10);
    return new Date(`${text}T00:00:00`);
  }

  function cutoffByDays(days) {
    const date = parseDate(DEMO_DATA.currentDate);
    date.setDate(date.getDate() - Math.max(Number(days) || 0, 1) + 1);
    return date;
  }

  function filterRecent(rows, days, field) {
    const cutoff = cutoffByDays(days);
    return rows.filter(row => parseDate(row[field]) >= cutoff);
  }

  function includesKeyword(row, fields, keyword) {
    const normalized = String(keyword || '').trim().toLowerCase();
    if (!normalized) return true;
    return fields.some(field => String(row[field] || '').toLowerCase().includes(normalized));
  }

  function limitRows(rows, limit) {
    return rows.slice(0, Math.max(Number(limit) || rows.length, 0));
  }

  function resolveDashboardResponse(pathname, searchParams, options) {
    const data = DEMO_DATA.dashboard;
    if (pathname === '/api/stats') return clone(data.stats);
    if (pathname === '/api/dashboard/overview') return clone(data.overview);
    if (pathname === '/api/dashboard/daily_trend') {
      const days = Number(searchParams.get('days') || 30);
      return {days, data: clone(filterRecent(data.dailyTrend, days, 'date'))};
    }
    if (pathname === '/api/dashboard/price_trend') {
      const days = Number(searchParams.get('days') || 90);
      return {days, platform: searchParams.get('platform') || 'all', data: clone(filterRecent(data.priceTrend, days, 'date'))};
    }
    if (pathname === '/api/dashboard/species_origin') {
      const days = Number(searchParams.get('days') || 30);
      return {days, platform: searchParams.get('platform') || 'all', data: clone(data.speciesOrigin)};
    }
    if (pathname === '/api/dashboard/price_ranking') {
      const order = searchParams.get('order') || 'price_desc';
      const limit = Number(searchParams.get('limit') || 10);
      const rows = [...data.priceRanking].sort((a, b) => order === 'price_asc' ? a.price - b.price : b.price - a.price);
      return {order, data: clone(limitRows(rows, limit))};
    }
    if (pathname === '/api/dashboard/crawl_runs') {
      const limit = Number(searchParams.get('limit') || 15);
      return {data: clone(limitRows(data.crawlRuns, limit))};
    }
    if (pathname === '/api/query/papers') {
      const keyword = searchParams.get('keyword') || '';
      const limit = Number(searchParams.get('limit') || 50);
      const rows = data.papers.filter(row => includesKeyword(row, ['theme', 'title', 'abstract', 'keywords_json'], keyword));
      return {count: rows.length, data: clone(limitRows(rows, limit))};
    }
    if (pathname === '/api/query/products') {
      const keyword = searchParams.get('keyword') || '';
      const platform = searchParams.get('platform') || '';
      const limit = Number(searchParams.get('limit') || 50);
      let rows = data.products.filter(row => includesKeyword(row, ['keyword', 'title'], keyword));
      if (platform) rows = rows.filter(row => row.platform === platform);
      return {count: rows.length, data: clone(limitRows(rows, limit))};
    }
    if (pathname === '/api/query/intel') {
      const keyword = searchParams.get('keyword') || '';
      const limit = Number(searchParams.get('limit') || 50);
      const rows = data.intel.filter(row => includesKeyword(row, ['title', 'content', 'org'], keyword));
      return {count: rows.length, data: clone(limitRows(rows, limit))};
    }
    if (pathname === '/api/query/offline_prices') {
      const keyword = searchParams.get('keyword') || '';
      const limit = Number(searchParams.get('limit') || 50);
      const rows = data.offlinePrices.filter(row => includesKeyword(row, ['product_name_raw', 'product_type', 'market_name'], keyword));
      return {count: rows.length, data: clone(limitRows(rows, limit))};
    }
    if (pathname === '/api/import/csv') {
      return {message: '导入完成', inserted: 128, skipped: 4, errors: 0};
    }
    if (pathname === '/api/crawl') {
      const body = JSON.parse(options.body || '{}');
      const taskId = `demo${String(taskSeed).padStart(3, '0')}`;
      taskSeed += 1;
      demoTasks[taskId] = {
        id: taskId,
        crawler: body.crawler || 'demo',
        keyword: body.keyword || '',
        pages: body.pages || 1,
        status: 'pending',
        result: '演示模式：任务已排队，正在准备采集上下文。',
        started_at: DEMO_DATA.currentDate + ' 09:30:00',
        finished_at: null,
      };
      setTimeout(() => {
        if (!demoTasks[taskId]) return;
        demoTasks[taskId].status = 'running';
        demoTasks[taskId].result = '演示模式：正在模拟多源异构采集链路。';
      }, 450);
      setTimeout(() => {
        if (!demoTasks[taskId]) return;
        demoTasks[taskId].status = 'done';
        demoTasks[taskId].result = '演示模式：采集完成，共汇聚 186 条样本。';
        demoTasks[taskId].finished_at = DEMO_DATA.currentDate + ' 09:30:03';
      }, 1800);
      return {task_id: taskId, message: '演示任务已启动'};
    }
    if (pathname.startsWith('/api/task/')) {
      const taskId = pathname.split('/').pop();
      if (!demoTasks[taskId]) {
        return {error: '任务不存在'};
      }
      return clone(demoTasks[taskId]);
    }
    return null;
  }

  function buildSalmonCompare(platform) {
    const rows = DEMO_DATA.salmon.compare.filter(row => row.platform === 'offline' || !platform || row.platform === platform);
    return clone(rows);
  }

  function buildSalmonKpis(platform, days) {
    const rows = buildSalmonCompare(platform);
    const totalCount = rows.reduce((sum, row) => sum + Number(row.count || 0), 0);
    const weightedAvg = totalCount
      ? Number((rows.reduce((sum, row) => sum + Number(row.avg_price) * Number(row.count || 0), 0) / totalCount).toFixed(2))
      : null;
    const numeric = rows.map(row => Number(row.avg_price));
    return {
      window_days: days || 30,
      platform: platform || 'all',
      monitor_avg_price: weightedAvg,
      online_offline_spread: numeric.length > 1 ? Number((Math.max(...numeric) - Math.min(...numeric)).toFixed(2)) : null,
      sample_count_30d: totalCount,
    };
  }

  function resolveSalmonResponse(pathname, searchParams) {
    const platform = searchParams.get('platform') || '';
    const days = Number(searchParams.get('days') || 60);
    if (pathname === '/api/analysis/salmon/trend') {
      let rows = filterRecent(DEMO_DATA.salmon.trend, days, 'date');
      if (platform) rows = rows.filter(row => row.platform === platform);
      return {days, platform: platform || 'all', data: clone(rows)};
    }
    if (pathname === '/api/analysis/salmon/distribution') {
      const originLimit = Number(searchParams.get('origin_limit') || 6);
      const species = DEMO_DATA.salmon.species.filter(row => row.platform === (platform || 'all'));
      const origins = DEMO_DATA.salmon.origins
        .filter(row => row.platform === (platform || 'all'))
        .slice(0, originLimit);
      return {days, origin_limit: originLimit, platform: platform || 'all', species: clone(species), origins: clone(origins)};
    }
    if (pathname === '/api/analysis/salmon/online-offline') {
      return {days, platform: platform || 'all', data: buildSalmonCompare(platform)};
    }
    if (pathname === '/api/analysis/salmon/kpis') {
      return buildSalmonKpis(platform, days);
    }
    return null;
  }

  async function respond(url, options = {}) {
    await sleep(140);
    const parsed = new URL(url, window.location.origin);
    const pathname = parsed.pathname;
    const dashboardResponse = resolveDashboardResponse(pathname, parsed.searchParams, options);
    if (dashboardResponse) return clone(dashboardResponse);
    const salmonResponse = resolveSalmonResponse(pathname, parsed.searchParams);
    if (salmonResponse) return clone(salmonResponse);
    throw new Error(`Demo data 未覆盖接口: ${pathname}`);
  }

  window.AQUA_DEMO_DATA = DEMO_DATA;
  window.AQUA_DEMO_API = {respond, data: DEMO_DATA};
})();
