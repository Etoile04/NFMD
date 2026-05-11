-- ============================================================
-- NFMD 数据质量修复脚本
-- 日期: 2026-05-11
-- 前提: 先备份数据库！
-- 用法: psql -U postgres -d postgres -f repair_quality.sql
-- ============================================================

BEGIN;

-- ============ Phase 1: 去重 ============

-- 删除真重复（排除泛化名称组 >20条，保留 id 最小的记录）
DELETE FROM parameters
WHERE id IN (
  SELECT id FROM (
    SELECT id,
      ROW_NUMBER() OVER (
        PARTITION BY name, material_id, category, value_type, value_scalar, unit
        ORDER BY id ASC
      ) as rn
    FROM parameters p
    WHERE NOT EXISTS (
      SELECT 1 FROM (
        SELECT name, category FROM parameters
        GROUP BY name, category HAVING COUNT(*) > 20
      ) gn WHERE gn.name = p.name AND gn.category = p.category
    )
  ) ranked WHERE rn > 1
);

-- ============ Phase 2: value_type 修复 ============

-- scalar 有 value_str 但无 value_scalar → 改为 text
UPDATE parameters SET value_type = 'text'
WHERE value_type = 'scalar' AND value_scalar IS NULL AND value_str IS NOT NULL;

-- range 的 value_min > value_max → 交换
UPDATE parameters SET value_min = value_max, value_max = value_min
WHERE value_type = 'range' AND value_min > value_max;

-- 同名统一
UPDATE parameters SET name = '玻尔兹曼常数' WHERE name = 'Boltzmann常数';

-- expression 有 equation 但无 value_expr → 补全
UPDATE parameters SET value_expr = equation
WHERE value_type = 'expression' AND value_expr IS NULL AND equation IS NOT NULL AND equation != '';

-- ============ Phase 3: 泛化名称重命名 ============

-- 气泡参数 → 按 unit 区分
UPDATE parameters SET name = '气泡直径' WHERE name = '气泡参数' AND unit IN ('μm', 'µm', 'nm');
UPDATE parameters SET name = '气泡等效直径(像素)' WHERE name = '气泡参数' AND unit = 'px';
UPDATE parameters SET name = '气泡数密度' WHERE name = '气泡参数' AND unit IN ('/m³', '1/m³', 'bubbles/m³', 'm^-3');
UPDATE parameters SET name = '气泡截面积' WHERE name = '气泡参数' AND unit = 'μm²';
UPDATE parameters SET name = '气泡成核参数' WHERE name = '气泡参数' AND unit LIKE '%bub%';
UPDATE parameters SET name = '气泡体积' WHERE name = '气泡参数' AND unit = 'm';
UPDATE parameters SET name = '气泡数量' WHERE name = '气泡参数' AND unit = 'bubbles';
UPDATE parameters SET name = '平衡气态浓度' WHERE name = '气泡参数' AND unit = 'mole fraction';
UPDATE parameters SET name = '气泡体积分数' WHERE name = '气泡参数' AND unit IN ('dimensionless', '无量纲') AND value_scalar IS NOT NULL AND value_scalar < 1;

-- 肿胀参数 → 按 unit 区分
UPDATE parameters SET name = '肿胀量' WHERE name = '肿胀参数' AND unit = '%';
UPDATE parameters SET name = '肿胀率系数' WHERE name = '肿胀参数' AND unit LIKE '%fissions%';
UPDATE parameters SET name = '合金成分阈值' WHERE name = '肿胀参数' AND unit = 'at.%';

-- 扩散参数 → 按 unit 区分
UPDATE parameters SET name = '裂变气体扩散系数' WHERE name = '扩散参数' AND unit = 'm²/s';
UPDATE parameters SET name = '扩散激活能' WHERE name = '扩散参数' AND unit LIKE '%cal%';
UPDATE parameters SET name = '燃料箔厚度' WHERE name = '扩散参数' AND unit IN ('μm', 'µm');
UPDATE parameters SET name = '体积扩散系数' WHERE name = '扩散参数' AND unit = 'm³/s';
UPDATE parameters SET name = '扩散增强因子' WHERE name = '扩散参数' AND unit = '1';
UPDATE parameters SET name = '晶界扩散参数' WHERE name = '扩散参数' AND unit LIKE '%m5%';

-- elastic parameter
UPDATE parameters SET name = '屈服强度' WHERE name = 'elastic parameter' AND unit = 'MPa';
UPDATE parameters SET name = '泊松比' WHERE name = 'elastic parameter' AND unit IN ('dimensionless', '无量纲');

-- fuel_performance parameter → 按 unit/notes 区分
UPDATE parameters SET name = '百分比阈值' WHERE name = 'fuel_performance parameter' AND unit = '%';
UPDATE parameters SET name = '晶格常数' WHERE name = 'fuel_performance parameter' AND unit = 'Å';
UPDATE parameters SET name = '钼浓度' WHERE name = 'fuel_performance parameter' AND unit = 'at%';
UPDATE parameters SET name = '退火时间' WHERE name = 'fuel_performance parameter' AND unit IN ('h', 'min');
UPDATE parameters SET name = '燃料尺寸' WHERE name = 'fuel_performance parameter' AND unit = 'mm';
UPDATE parameters SET name = '压力' WHERE name = 'fuel_performance parameter' AND unit = 'Pa';
UPDATE parameters SET name = '截面积' WHERE name = 'fuel_performance parameter' AND unit = 'μm²';
UPDATE parameters SET name = '晶粒结构参数' WHERE name = 'fuel_performance parameter' AND notes LIKE '%Grain structure%';
UPDATE parameters SET name = '无量纲参数' WHERE name = 'fuel_performance parameter' AND unit IN ('无量纲', 'dimensionless');
UPDATE parameters SET name = '未提取参数(PDF图片)' WHERE name = 'fuel_performance parameter' AND notes LIKE '%image-based%';

-- Unnamed parameter
UPDATE parameters SET name = '未知参数' WHERE name = 'Unnamed parameter';

-- ============ Phase 4: 去重（重命名后再去重一次）============

DELETE FROM parameters WHERE id IN (
  SELECT id FROM (
    SELECT id,
      ROW_NUMBER() OVER (
        PARTITION BY name, material_id, category, value_type, value_scalar, unit
        ORDER BY id ASC
      ) as rn
    FROM parameters p
    WHERE NOT EXISTS (
      SELECT 1 FROM (
        SELECT name, category FROM parameters GROUP BY name, category HAVING COUNT(*) > 20
      ) gn WHERE gn.name = p.name AND gn.category = p.category
    )
  ) ranked WHERE rn > 1
);

-- ============ Phase 5: 空值标记 ============

UPDATE parameters SET notes = CONCAT(COALESCE(notes, ''), ' [待人工确认]')
WHERE value_type = 'scalar' AND value_scalar IS NULL AND value_str IS NULL
AND COALESCE(notes, '') NOT LIKE '%待人工确认%';

UPDATE parameters SET notes = CONCAT(COALESCE(notes, ''), ' [待重新提取]')
WHERE value_type = 'range' AND value_min IS NULL AND value_max IS NULL
AND COALESCE(notes, '') NOT LIKE '%待重新提取%';

UPDATE parameters SET notes = CONCAT(COALESCE(notes, ''), ' [待人工确认]')
WHERE value_type = 'expression' AND value_expr IS NULL
AND COALESCE(notes, '') NOT LIKE '%待人工确认%';

UPDATE parameters SET notes = CONCAT(COALESCE(notes, ''), ' [待人工确认]')
WHERE value_type = 'list' AND value_list IS NULL
AND COALESCE(notes, '') NOT LIKE '%待人工确认%';

-- ============ Phase 6: 计数修复 ============

UPDATE categories c SET param_count = sub.actual_count
FROM (SELECT category, COUNT(*) AS actual_count FROM parameters GROUP BY category) sub
WHERE c.name = sub.category AND c.param_count != sub.actual_count;

UPDATE literature l SET parameter_count = sub.cnt
FROM (
  SELECT l2.id AS lit_id, COUNT(*) AS cnt
  FROM parameters p
  JOIN literature l2 ON (
    p.source_file = l2.id
    OR REPLACE(p.source_file, '.md', '') = l2.id
    OR REPLACE(p.source_file, '.json', '') = l2.id
    OR REPLACE(REPLACE(p.source_file, 'summaries/', ''), '.md', '') = l2.id
    OR REPLACE(REPLACE(p.source_file, 'summaries/', ''), '.txt.md', '') = l2.id
    OR split_part(REPLACE(p.source_file, 'raw/mineru/', ''), '/', 1) = l2.id
    OR REPLACE(p.source_file, 'raw/papers/', '') = l2.id
  )
  GROUP BY l2.id
) sub
WHERE l.id = sub.lit_id;

-- ============ Phase 7: 文献清理 ============

DELETE FROM literature WHERE id IN ('_summary', 'paper');
DELETE FROM literature WHERE id LIKE '%gas-bubble-gas-bubble%';
DELETE FROM literature WHERE id LIKE '%2022025%';
DELETE FROM literature WHERE id LIKE 'mllett_et_al%';

COMMIT;
