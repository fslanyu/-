-- 在 Supabase SQL Editor 中执行此脚本
-- 路径：Supabase Dashboard → SQL Editor → New Query → 粘贴 → Run

-- 1. 人员表
CREATE TABLE IF NOT EXISTS people (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

-- 2. 考勤数据表
CREATE TABLE IF NOT EXISTS attendance (
  id SERIAL PRIMARY KEY,
  person TEXT NOT NULL,
  year_month TEXT NOT NULL,
  day_key TEXT NOT NULL,
  status_data TEXT DEFAULT '',
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(person, year_month, day_key)
);

-- 3. 备注表
CREATE TABLE IF NOT EXISTS notes (
  id SERIAL PRIMARY KEY,
  person TEXT NOT NULL,
  year_month TEXT NOT NULL,
  day_key TEXT NOT NULL,
  note TEXT DEFAULT '',
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(person, year_month, day_key)
);

-- 4. PIN 锁表
CREATE TABLE IF NOT EXISTS pins (
  person TEXT PRIMARY KEY,
  pin TEXT NOT NULL
);

-- 5. 配置表
CREATE TABLE IF NOT EXISTS config (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- 6. 初始数据
INSERT INTO people (name) VALUES ('本人') ON CONFLICT DO NOTHING;
INSERT INTO people (name) VALUES ('琨') ON CONFLICT DO NOTHING;
INSERT INTO config (key, value) VALUES ('admin_password', 'fszyy8306') ON CONFLICT DO NOTHING;
INSERT INTO config (key, value) VALUES ('admin_users', '["琨","景斌"]') ON CONFLICT DO NOTHING;

-- 7. 禁用 RLS（封闭群组，所有人用同一个 anon key）
ALTER TABLE people DISABLE ROW LEVEL SECURITY;
ALTER TABLE attendance DISABLE ROW LEVEL SECURITY;
ALTER TABLE notes DISABLE ROW LEVEL SECURITY;
ALTER TABLE pins DISABLE ROW LEVEL SECURITY;
ALTER TABLE config DISABLE ROW LEVEL SECURITY;

-- 8. 开启实时同步（考勤数据和备注变更实时推送）
ALTER PUBLICATION supabase_realtime ADD TABLE attendance;
ALTER PUBLICATION supabase_realtime ADD TABLE notes;
ALTER PUBLICATION supabase_realtime ADD TABLE pins;
