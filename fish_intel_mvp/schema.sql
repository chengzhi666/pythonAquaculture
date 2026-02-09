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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS raw_event (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source_name VARCHAR(64) NOT NULL,
  url TEXT NULL,
  title TEXT NULL,
  pub_time VARCHAR(32) NULL,
  fetched_at DATETIME NOT NULL,
  raw_text LONGTEXT NULL,
  raw_json LONGTEXT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS product_snapshot (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  platform VARCHAR(16) NOT NULL,
  keyword VARCHAR(64) NOT NULL,
  title TEXT NOT NULL,
  price DECIMAL(10,2) NULL,
  original_price DECIMAL(10,2) NULL,
  sales_or_commit VARCHAR(64) NULL,
  shop VARCHAR(255) NULL,
  province VARCHAR(64) NULL,
  city VARCHAR(64) NULL,
  detail_url TEXT NOT NULL,
  category VARCHAR(255) NULL,
  snapshot_time DATETIME NOT NULL,
  raw_id BIGINT NULL,
  -- MySQL 5.6 + utf8mb4 has 767-byte index limit; keep prefix short.
  UNIQUE KEY uk_platform_url_time (platform(16), detail_url(150), snapshot_time),
  INDEX idx_keyword_time (keyword, snapshot_time),
  CONSTRAINT fk_product_raw FOREIGN KEY (raw_id) REFERENCES raw_event(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
