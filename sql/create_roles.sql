-- ============================================================
-- NFMD 受限角色与权限配置
-- 日期: 2026-05-12
-- 说明: 创建 nfmd_reader (只读) 和 nfmd_writer (写入) 角色
--       非 superuser → RLS 强制生效
-- ============================================================

-- 0. 清理（幂等，角色不存在时忽略错误）
DO $$
BEGIN
    DROP ROLE IF EXISTS nfmd_reader;
    DROP ROLE IF EXISTS nfmd_writer;
EXCEPTION WHEN OTHERS THEN
    NULL;
END $$;

-- ============================================================
-- 1. 只读角色 — API 层 / 外部工具查询
-- ============================================================
CREATE ROLE nfmd_reader WITH LOGIN PASSWORD 'nfmd_read_2026';

-- 基础权限：只能连接 nfmd 数据库
GRANT CONNECT ON DATABASE nfmd TO nfmd_reader;
REVOKE CONNECT ON DATABASE postgres FROM nfmd_reader;
REVOKE CONNECT ON DATABASE template1 FROM nfmd_reader;

-- Schema 使用权限
GRANT USAGE ON SCHEMA public TO nfmd_reader;

-- 所有表只读
GRANT SELECT ON ALL TABLES IN SCHEMA public TO nfmd_reader;

-- 序列不需要
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM nfmd_reader;

-- 函数可执行（search_parameters, stats_overview 等）
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO nfmd_reader;

-- 默认权限：未来新建的表也自动赋予读取
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO nfmd_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO nfmd_reader;

-- ============================================================
-- 2. 写入角色 — ETL / Agent 数据导入
-- ============================================================
CREATE ROLE nfmd_writer WITH LOGIN PASSWORD 'nfmd_write_2026';

-- 基础权限
GRANT CONNECT ON DATABASE nfmd TO nfmd_writer;
REVOKE CONNECT ON DATABASE postgres FROM nfmd_writer;
REVOKE CONNECT ON DATABASE template1 FROM nfmd_writer;

GRANT USAGE ON SCHEMA public TO nfmd_writer;

-- 读取 + 插入 + 更新（不能删除、不能 DDL）
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO nfmd_writer;

-- 序列使用权限（INSERT 需要自增 ID）
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nfmd_writer;

-- 函数可执行
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO nfmd_writer;

-- 默认权限
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE ON TABLES TO nfmd_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO nfmd_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO nfmd_writer;

-- ============================================================
-- 3. 强化 RLS 策略
-- ============================================================

-- 3.1 为写入角色添加 INSERT/UPDATE 策略（目前只有 public_read）
--     reader: 只能 SELECT（已有 public_read policy）
--     writer: 可以 SELECT + INSERT + UPDATE

-- materials
CREATE POLICY "materials_writer_insert" ON materials FOR INSERT TO nfmd_writer WITH CHECK (true);
CREATE POLICY "materials_writer_update" ON materials FOR UPDATE TO nfmd_writer USING (true) WITH CHECK (true);

-- material_aliases
CREATE POLICY "aliases_writer_insert" ON material_aliases FOR INSERT TO nfmd_writer WITH CHECK (true);
CREATE POLICY "aliases_writer_update" ON material_aliases FOR UPDATE TO nfmd_writer USING (true) WITH CHECK (true);

-- categories
CREATE POLICY "categories_writer_insert" ON categories FOR INSERT TO nfmd_writer WITH CHECK (true);
CREATE POLICY "categories_writer_update" ON categories FOR UPDATE TO nfmd_writer USING (true) WITH CHECK (true);

-- literature
CREATE POLICY "literature_writer_insert" ON literature FOR INSERT TO nfmd_writer WITH CHECK (true);
CREATE POLICY "literature_writer_update" ON literature FOR UPDATE TO nfmd_writer USING (true) WITH CHECK (true);

-- parameters
CREATE POLICY "parameters_writer_insert" ON parameters FOR INSERT TO nfmd_writer WITH CHECK (true);
CREATE POLICY "parameters_writer_update" ON parameters FOR UPDATE TO nfmd_writer USING (true) WITH CHECK (true);

-- 3.2 审计日志：reader 不可读，writer 只能 INSERT（不能改/删）
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "audit_log_writer_insert" ON audit_log FOR INSERT TO nfmd_writer WITH CHECK (true);
-- 不给 reader 任何策略 → reader 默认被 RLS 阻止读取

-- 3.3 terminology：reader 可读，writer 可写
ALTER TABLE terminology ENABLE ROW LEVEL SECURITY;
CREATE POLICY "terminology_public_read" ON terminology FOR SELECT USING (true);
CREATE POLICY "terminology_writer_insert" ON terminology FOR INSERT TO nfmd_writer WITH CHECK (true);
CREATE POLICY "terminology_writer_update" ON terminology FOR UPDATE TO nfmd_writer USING (true) WITH CHECK (true);

-- ============================================================
-- 4. 禁止危险操作（安全规则硬化）
-- ============================================================

-- 4.1 确保非 superuser 不能 DROP/TRUNCATE
--     (PostgreSQL 中 DDL 权限通过 ownership 控制，非 owner 无法 DROP)
--     确认所有表 owner 是 postgres
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I OWNER TO postgres', r.tablename);
    END LOOP;
END $$;

-- 验证
SELECT 'Roles created successfully' AS status;
SELECT rolname, rolcanlogin FROM pg_roles WHERE rolname IN ('nfmd_reader', 'nfmd_writer');
