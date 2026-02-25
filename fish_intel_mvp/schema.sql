CREATE DATABASE IF NOT EXISTS fish_intel DEFAULT CHARSET utf8mb4;
USE fish_intel;
CREATE TABLE IF NOT EXISTS crawl_run (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source_name VARCHAR(64) NOT NULL,
  started_at DATETIME NOT NULL,
  ended_at DATETIME NULL,
  status VARCHAR(16) NOT NULL,
  items INT NOT NULL DEFAULT 0,
  error_text TEXT NULL
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
CREATE TABLE IF NOT EXISTS raw_event (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source_name VARCHAR(64) NOT NULL,
  url TEXT NULL,
  title TEXT NULL,
  pub_time VARCHAR(32) NULL,
  fetched_at DATETIME NOT NULL,
  raw_text LONGTEXT NULL,
  raw_json LONGTEXT NULL
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
CREATE TABLE IF NOT EXISTS product_snapshot (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  platform VARCHAR(16) NOT NULL,
  keyword VARCHAR(64) NOT NULL,
  title TEXT NOT NULL,
  price DECIMAL(10, 2) NULL,
  original_price DECIMAL(10, 2) NULL,
  price_unit VARCHAR(16) NOT NULL DEFAULT 'CNY',
  currency VARCHAR(8) NOT NULL DEFAULT 'CNY',
  price_per_kg DECIMAL(10, 2) NULL,
  price_change_7d DECIMAL(10, 4) NULL,
  price_change_30d DECIMAL(10, 4) NULL,
  sales_or_commit VARCHAR(64) NULL,
  shop VARCHAR(255) NOT NULL DEFAULT '',
  shop_type VARCHAR(32) NULL,
  brand VARCHAR(128) NULL,
  sku VARCHAR(128) NULL,
  province VARCHAR(64) NULL,
  city VARCHAR(64) NULL,
  detail_url TEXT NOT NULL,
  category VARCHAR(255) NULL,
  product_type VARCHAR(64) NOT NULL DEFAULT '',
  product_type_confidence DECIMAL(5, 4) NULL,
  product_type_rule_id BIGINT NULL,
  spec_raw VARCHAR(255) NULL,
  spec_weight_value DECIMAL(10, 3) NULL,
  spec_weight_unit VARCHAR(16) NULL,
  spec_weight_grams DECIMAL(10, 3) NULL,
  spec_pack_count INT NULL,
  spec_unit VARCHAR(32) NULL,
  spec_total_weight_grams DECIMAL(10, 3) NULL,
  spec_weight_normalized VARCHAR(32) NOT NULL DEFAULT '',
  origin_raw VARCHAR(128) NULL,
  origin_country VARCHAR(64) NULL,
  origin_province VARCHAR(64) NULL,
  origin_city VARCHAR(64) NULL,
  origin_standardized VARCHAR(128) NULL,
  origin_rule_id BIGINT NULL,
  storage_method VARCHAR(32) NULL,
  is_wild TINYINT(1) NULL,
  is_fresh TINYINT(1) NULL,
  nutrition_protein_g_per_100g DECIMAL(6, 2) NULL,
  nutrition_fat_g_per_100g DECIMAL(6, 2) NULL,
  nutrition_omega3_g_per_100g DECIMAL(6, 2) NULL,
  cert_organic TINYINT(1) NULL,
  cert_green_food TINYINT(1) NULL,
  cert_asc TINYINT(1) NULL,
  cert_msc TINYINT(1) NULL,
  cert_bap TINYINT(1) NULL,
  cert_haccp TINYINT(1) NULL,
  cert_halal TINYINT(1) NULL,
  cert_qs TINYINT(1) NULL,
  extra_json LONGTEXT NULL,
  snapshot_time DATETIME NOT NULL,
  raw_id BIGINT NULL,
  UNIQUE KEY uk_product_dedup (
    platform(16),
    product_type(32),
    spec_weight_normalized(16),
    shop(48),
    snapshot_time
  ),
  INDEX idx_keyword_time (keyword, snapshot_time),
  INDEX idx_platform_time (platform, snapshot_time),
  INDEX idx_type_spec_time (
    product_type,
    spec_weight_normalized,
    snapshot_time
  ),
  INDEX idx_detail_url (detail_url(150)),
  CONSTRAINT fk_product_raw FOREIGN KEY (raw_id) REFERENCES raw_event(id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
CREATE TABLE IF NOT EXISTS product_type_dict (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  product_type VARCHAR(64) NOT NULL,
  pattern VARCHAR(255) NOT NULL,
  keyword_hint VARCHAR(64) NULL,
  priority INT NOT NULL DEFAULT 100,
  confidence DECIMAL(5, 4) NOT NULL DEFAULT 0.9000,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  note VARCHAR(255) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_product_type_pattern (product_type, pattern(120)),
  INDEX idx_product_type_priority (is_active, priority)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
CREATE TABLE IF NOT EXISTS spec_dict (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  pattern VARCHAR(128) NOT NULL,
  normalized_unit VARCHAR(16) NOT NULL,
  gram_factor DECIMAL(12, 6) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  note VARCHAR(255) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_spec_pattern (pattern(64)),
  INDEX idx_spec_active_priority (is_active, priority)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
CREATE TABLE IF NOT EXISTS origin_dict (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  pattern VARCHAR(255) NOT NULL,
  normalized_country VARCHAR(64) NULL,
  normalized_province VARCHAR(64) NULL,
  normalized_city VARCHAR(64) NULL,
  normalized_origin VARCHAR(128) NOT NULL,
  priority INT NOT NULL DEFAULT 100,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  note VARCHAR(255) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_origin_pattern (pattern(120)),
  INDEX idx_origin_active_priority (is_active, priority)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
CREATE TABLE IF NOT EXISTS price_history_agg (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  agg_date DATE NOT NULL,
  agg_grain ENUM('day', 'week', 'month') NOT NULL,
  platform VARCHAR(16) NOT NULL,
  product_type VARCHAR(64) NOT NULL,
  spec_weight_normalized VARCHAR(32) NOT NULL DEFAULT '',
  shop VARCHAR(255) NOT NULL DEFAULT '',
  currency VARCHAR(8) NOT NULL DEFAULT 'CNY',
  sample_size INT NOT NULL DEFAULT 0,
  min_price DECIMAL(10, 2) NULL,
  max_price DECIMAL(10, 2) NULL,
  avg_price DECIMAL(10, 2) NULL,
  p50_price DECIMAL(10, 2) NULL,
  last_price DECIMAL(10, 2) NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_price_history_agg (
    agg_date,
    agg_grain,
    platform(16),
    product_type(32),
    spec_weight_normalized(16),
    shop(48)
  ),
  INDEX idx_price_history_lookup (platform, product_type, agg_grain, agg_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
INSERT INTO product_type_dict(
    product_type,
    pattern,
    keyword_hint,
    priority,
    confidence,
    is_active,
    note
  )
VALUES (
    'king_salmon',
    '(帝王鲑|帝王三文鱼|king\\s*salmon|chinook)',
    '帝王鲑',
    10,
    0.9800,
    1,
    '帝王鲑核心词'
  ),
  (
    'king_salmon',
    '(帝王鲑|king\\s*salmon)',
    'king salmon',
    15,
    0.9600,
    1,
    '英文关键词'
  ),
  (
    'rainbow_trout',
    '(虹鳟|rainbow\\s*trout)',
    '虹鳟',
    20,
    0.9800,
    1,
    '虹鳟核心词'
  ),
  (
    'rainbow_trout',
    '(虹鳟|rainbow\\s*trout)',
    'rainbow',
    25,
    0.9400,
    1,
    '虹鳟英文简称'
  ),
  (
    'salmon_generic',
    '(三文鱼|salmon)',
    NULL,
    90,
    0.7000,
    1,
    '通用三文鱼'
  ) ON DUPLICATE KEY
UPDATE keyword_hint =
VALUES(keyword_hint),
  priority =
VALUES(priority),
  confidence =
VALUES(confidence),
  is_active =
VALUES(is_active),
  note =
VALUES(note);
INSERT INTO spec_dict(
    pattern,
    normalized_unit,
    gram_factor,
    priority,
    is_active,
    note
  )
VALUES ('^(kg|千克|公斤)$', 'kg', 1000.000000, 10, 1, '千克'),
  ('^(g|克)$', 'g', 1.000000, 20, 1, '克'),
  ('^(斤)$', 'jin', 500.000000, 30, 1, '斤'),
  ('^(两)$', 'liang', 50.000000, 40, 1, '两'),
  ('^(lb|lbs|磅)$', 'lb', 453.592370, 50, 1, '磅'),
  ('^(oz|盎司)$', 'oz', 28.349523, 60, 1, '盎司') ON DUPLICATE KEY
UPDATE normalized_unit =
VALUES(normalized_unit),
  gram_factor =
VALUES(gram_factor),
  priority =
VALUES(priority),
  is_active =
VALUES(is_active),
  note =
VALUES(note);
INSERT INTO origin_dict(
    pattern,
    normalized_country,
    normalized_province,
    normalized_city,
    normalized_origin,
    priority,
    is_active,
    note
  )
VALUES ('智利', '智利', NULL, NULL, '智利', 10, 1, '进口产地'),
  ('挪威', '挪威', NULL, NULL, '挪威', 20, 1, '进口产地'),
  ('法罗', '法罗群岛', NULL, NULL, '法罗群岛', 30, 1, '进口产地'),
  ('青海', '中国', '青海', NULL, '中国-青海', 40, 1, '国内主产地'),
  ('新疆', '中国', '新疆', NULL, '中国-新疆', 50, 1, '国内主产地'),
  ('西藏', '中国', '西藏', NULL, '中国-西藏', 60, 1, '国内冷水产地') ON DUPLICATE KEY
UPDATE normalized_country =
VALUES(normalized_country),
  normalized_province =
VALUES(normalized_province),
  normalized_city =
VALUES(normalized_city),
  normalized_origin =
VALUES(normalized_origin),
  priority =
VALUES(priority),
  is_active =
VALUES(is_active),
  note =
VALUES(note);
CREATE TABLE IF NOT EXISTS intel_item (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source_type VARCHAR(64) NOT NULL,
  title TEXT NOT NULL,
  pub_time VARCHAR(32) NULL,
  org VARCHAR(255) NULL,
  region VARCHAR(64) NULL,
  content LONGTEXT NULL,
  source_url TEXT NOT NULL,
  tags_json TEXT NULL,
  extra_json TEXT NULL,
  fetched_at DATETIME NOT NULL,
  raw_id BIGINT NULL,
  UNIQUE KEY uk_source_url (source_url(150)),
  CONSTRAINT fk_intel_raw FOREIGN KEY (raw_id) REFERENCES raw_event(id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
CREATE TABLE IF NOT EXISTS paper_meta (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  theme VARCHAR(255) NULL,
  title TEXT NOT NULL,
  authors TEXT NULL,
  institute TEXT NULL,
  source TEXT NULL,
  pub_date VARCHAR(32) NULL,
  database_name VARCHAR(64) NULL,
  abstract LONGTEXT NULL,
  keywords_json TEXT NULL,
  url TEXT NOT NULL,
  fetched_at DATETIME NOT NULL,
  raw_id BIGINT NULL,
  UNIQUE KEY uk_paper_url (url(150)),
  CONSTRAINT fk_paper_raw FOREIGN KEY (raw_id) REFERENCES raw_event(id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
-- ============================================================
-- 线下价格快照 (第二阶段: 农业农村部批发市场价格等)
-- ============================================================
CREATE TABLE IF NOT EXISTS offline_price_snapshot (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source_name VARCHAR(64) NOT NULL COMMENT '数据来源标识, 如 moa_wholesale_price',
  market_name VARCHAR(128) NOT NULL DEFAULT '' COMMENT '批发市场名称',
  region VARCHAR(64) NOT NULL DEFAULT '' COMMENT '地区',
  product_type VARCHAR(64) NOT NULL DEFAULT '' COMMENT '品种标识: king_salmon / rainbow_trout / salmon_generic ...',
  product_name_raw VARCHAR(255) NULL COMMENT '原始品名 (未标准化)',
  spec VARCHAR(128) NULL COMMENT '规格描述',
  min_price DECIMAL(10, 2) NULL COMMENT '最低价',
  max_price DECIMAL(10, 2) NULL COMMENT '最高价',
  price DECIMAL(10, 2) NULL COMMENT '均价',
  unit VARCHAR(32) NOT NULL DEFAULT '元/公斤' COMMENT '价格单位',
  storage_method VARCHAR(32) NULL COMMENT 'frozen / ice_fresh / fresh / ...',
  date_str VARCHAR(32) NULL COMMENT '原始日期字符串 (方便溯源)',
  remark TEXT NULL COMMENT '备注',
  snapshot_time DATETIME NOT NULL COMMENT '采集时间',
  raw_id BIGINT NULL COMMENT '关联 raw_event.id',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_offline_dedup (
    source_name(32),
    market_name(48),
    product_type(32),
    snapshot_time
  ),
  INDEX idx_offline_product_time (product_type, snapshot_time),
  INDEX idx_offline_source_time (source_name, snapshot_time),
  INDEX idx_offline_market (market_name),
  CONSTRAINT fk_offline_raw FOREIGN KEY (raw_id) REFERENCES raw_event(id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
