-- ============================================================
-- NFMD Schema v2 补丁 — 数据质量防护
-- 日期: 2026-05-11
-- 说明: 基于 2026-05-11 数据质量事故复盘的防护措施
-- ============================================================

-- ============ 1. categories.param_count 自动维护触发器 ============
-- 问题: ETL 增量导入后 param_count 不更新，导致全部失准
-- 方案: 每次 parameters 表变更时自动刷新对应 category 的计数

CREATE OR REPLACE FUNCTION refresh_category_param_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE categories SET param_count = param_count + 1 WHERE name = NEW.category;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE categories SET param_count = GREATEST(param_count - 1, 0) WHERE name = OLD.category;
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.category IS DISTINCT FROM NEW.category THEN
            UPDATE categories SET param_count = GREATEST(param_count - 1, 0) WHERE name = OLD.category;
            UPDATE categories SET param_count = param_count + 1 WHERE name = NEW.category;
        END IF;
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_category_param_count ON parameters;
CREATE TRIGGER trg_category_param_count
AFTER INSERT OR UPDATE OF category OR DELETE ON parameters
FOR EACH ROW EXECUTE FUNCTION refresh_category_param_count();


-- ============ 2. value_type ↔ 值字段一致性校验 ============
-- 问题: scalar 缺 value_scalar, range 缺 value_min/max 等
-- 方案: 添加 CHECK 约束确保类型与值匹配

-- 先清理历史问题（注释掉，仅参考）
-- UPDATE parameters SET value_type = 'text' WHERE value_type = 'scalar' AND value_scalar IS NULL AND value_str IS NOT NULL;

-- 添加约束（注意：需先清理现有不一致数据才能启用）
-- ALTER TABLE parameters ADD CONSTRAINT chk_scalar_has_value
--   CHECK (value_type != 'scalar' OR value_scalar IS NOT NULL OR value_str IS NOT NULL);
-- ALTER TABLE parameters ADD CONSTRAINT chk_range_has_bounds
--   CHECK (value_type != 'range' OR (value_min IS NOT NULL AND value_max IS NOT NULL));
-- ALTER TABLE parameters ADD CONSTRAINT chk_expression_has_expr
--   CHECK (value_type != 'expression' OR value_expr IS NOT NULL OR equation IS NOT NULL);
-- ALTER TABLE parameters ADD CONSTRAINT chk_list_has_list
--   CHECK (value_type != 'list' OR value_list IS NOT NULL);
-- ALTER TABLE parameters ADD CONSTRAINT chk_range_min_lte_max
--   CHECK (value_type != 'range' OR value_min <= value_max);

-- ============ 3. source_file 格式标准化视图 ============
-- 问题: source_file 有 summaries/xxx.md, raw/mineru/xxx/paper.md 等多种格式
-- 方案: 创建标准化视图，统一映射到 literature.id

CREATE OR REPLACE VIEW v_source_file_normalized AS
SELECT
    id,
    source_file,
    CASE
        WHEN source_file LIKE 'summaries/%.md' THEN
            REPLACE(REPLACE(source_file, 'summaries/', ''), '.md', '')
        WHEN source_file LIKE 'summaries/%.txt.md' THEN
            REPLACE(REPLACE(source_file, 'summaries/', ''), '.txt.md', '')
        WHEN source_file LIKE 'raw/mineru/%' THEN
            split_part(REPLACE(source_file, 'raw/mineru/', ''), '/', 1)
        WHEN source_file LIKE 'raw/papers/%' THEN
            REPLACE(source_file, 'raw/papers/', '')
        WHEN source_file LIKE '%.md' THEN REPLACE(source_file, '.md', '')
        WHEN source_file LIKE '%.json' THEN REPLACE(source_file, '.json', '')
        ELSE source_file
    END AS literature_id_normalized
FROM parameters
WHERE source_file IS NOT NULL;
