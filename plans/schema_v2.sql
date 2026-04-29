-- ============================================================
-- 燃料性能知识库 Schema v2
-- 日期: 2026-04-29
-- 说明: 从知识库 parameters/*.json (6750条) 导入
-- ============================================================

-- 0. 备份现有表（如有数据需要保留）
-- CREATE TABLE IF NOT EXISTS materials_backup AS SELECT * FROM materials;
-- CREATE TABLE IF NOT EXISTS material_properties_backup AS SELECT * FROM material_properties;

-- 1. 清理旧表（ontofuel 时代遗留）
DROP TABLE IF EXISTS irradiation_behavior CASCADE;
DROP TABLE IF EXISTS material_composition CASCADE;
DROP TABLE IF EXISTS material_properties CASCADE;
DROP TABLE IF EXISTS literature_sources CASCADE;
DROP TABLE IF EXISTS materials CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS literature CASCADE;
DROP TABLE IF EXISTS parameters CASCADE;
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS material_aliases CASCADE;

-- ============================================================
-- 2. 材料主表
-- ============================================================
CREATE TABLE IF NOT EXISTS materials (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL,                -- 标准名（如 "U-10Mo"）
    name_zh         text,                         -- 中文名
    chemical_formula text,                        -- 化学式
    material_type   text NOT NULL,                -- FuelMaterial / StructuralMaterial / CoolantMaterial / ...
    alloy_system    text,                         -- 合金体系（U-Mo, U-Zr, U-Pu-Zr, ...）
    structure       text,                         -- 晶体结构（bcc, fcc, α, γ, ...）
    density         numeric(10,4),                -- g/cm³
    melting_point   numeric(10,2),                -- K
    description     text,                         -- 描述
    param_count     integer DEFAULT 0,            -- 关联参数数量
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);

-- 约束
ALTER TABLE materials ADD CONSTRAINT chk_materials_name_not_empty CHECK (name IS NOT NULL AND name <> '');
ALTER TABLE materials ADD CONSTRAINT chk_materials_type CHECK (material_type IN (
    'FuelMaterial', 'StructuralMaterial', 'CoolantMaterial', 'CeramicMaterial',
    'CladdingMaterial', 'BarrierMaterial', 'PureElement', 'FissionProduct',
    'Additive', 'Composite', 'Other'
));

-- 索引
CREATE UNIQUE INDEX IF NOT EXISTS idx_materials_name ON materials (name);
CREATE INDEX IF NOT EXISTS idx_materials_system ON materials (alloy_system);
CREATE INDEX IF NOT EXISTS idx_materials_type ON materials (material_type);

-- RLS（公开读取）
ALTER TABLE materials ENABLE ROW LEVEL SECURITY;
CREATE POLICY "materials_public_read" ON materials FOR SELECT USING (true);

-- ============================================================
-- 3. 材料别名映射表
-- ============================================================
CREATE TABLE IF NOT EXISTS material_aliases (
    id              serial PRIMARY KEY,
    alias           text NOT NULL,                -- 原始名称（如 "U-10wt.%Mo"）
    material_id     uuid NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    UNIQUE (alias)
);

CREATE INDEX IF NOT EXISTS idx_aliases_alias ON material_aliases (alias);
CREATE INDEX IF NOT EXISTS idx_aliases_material ON material_aliases (material_id);

ALTER TABLE material_aliases ENABLE ROW LEVEL SECURITY;
CREATE POLICY "aliases_public_read" ON material_aliases FOR SELECT USING (true);

-- ============================================================
-- 4. 参数分类字典表
-- ============================================================
CREATE TABLE IF NOT EXISTS categories (
    id              serial PRIMARY KEY,
    name            text UNIQUE NOT NULL,         -- 分类名（如 "diffusion"）
    name_zh         text,                         -- 中文名（如 "扩散"）
    description     text,                         -- 描述
    parent          text,                         -- 父分类
    param_count     integer DEFAULT 0             -- 参数数
);

CREATE INDEX IF NOT EXISTS idx_categories_name ON categories (name);

ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
CREATE POLICY "categories_public_read" ON categories FOR SELECT USING (true);

-- ============================================================
-- 5. 文献表
-- ============================================================
CREATE TABLE IF NOT EXISTS literature (
    id              text PRIMARY KEY,             -- slug（如 "Kim_2013_diffusion_U10Mo"）
    title           text,                         -- 标题
    authors         text,                         -- 作者列表
    journal         text,                         -- 期刊
    year            integer,                      -- 年份
    doi             text,                         -- DOI
    file_path       text,                         -- Zotero 本地路径
    parameter_count integer DEFAULT 0,            -- 关联参数数
    created_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_literature_year ON literature (year);
CREATE INDEX IF NOT EXISTS idx_literature_doi ON literature (doi) WHERE doi IS NOT NULL;

ALTER TABLE literature ENABLE ROW LEVEL SECURITY;
CREATE POLICY "literature_public_read" ON literature FOR SELECT USING (true);

-- ============================================================
-- 6. 参数主表（核心）
-- ============================================================
CREATE TABLE IF NOT EXISTS parameters (
    -- 标识
    id              text PRIMARY KEY,             -- 原始 ID（如 "151846_f3c95453_param_001"）
    
    -- 基本信息
    name            text NOT NULL,                -- 参数名
    name_zh         text,                         -- 中文名
    name_en         text,                         -- 英文名
    symbol          text,                         -- 符号（LaTeX，如 "$D_v$"）
    category        text NOT NULL,                -- 分类
    subcategory     text,                         -- 子分类
    
    -- 类型化值（五种 value_type 各占不同列）
    value_type      text NOT NULL,                -- scalar / range / expression / list / text
    value_scalar    numeric(20,10),               -- 标量值
    value_min       numeric(20,10),               -- 范围最小值
    value_max       numeric(20,10),               -- 范围最大值
    value_expr      text,                         -- 表达式/公式
    value_list      jsonb,                        -- 离散值列表 [1.0, 2.0, 3.0]
    value_text      text,                         -- 文本描述
    value_str       text,                         -- 原始字符串表示
    
    -- 物理属性
    unit            text,                         -- 单位
    uncertainty     text,                         -- 不确定度（如 "±50%"）
    
    -- 材料关联
    material_id     uuid REFERENCES materials(id) ON DELETE SET NULL,
    material_raw    text,                         -- 原始材料字符串
    
    -- 条件信息
    temperature_k   numeric(10,2),               -- 温度条件 (K)
    temperature_str text,                         -- 温度原始字符串
    burnup_range    text,                         -- 燃耗范围
    method          text,                         -- 测量/计算方法
    
    -- 质量与溯源
    confidence      text,                         -- high / medium / low
    source_file     text,                         -- 来源 summary 文件
    equation        text,                         -- 关联公式
    notes           text,                         -- 备注
    
    -- 全文搜索（英文）
    ts_vector       tsvector,
    
    -- 时间戳
    created_at      timestamptz DEFAULT now()
);

-- 约束
ALTER TABLE parameters ADD CONSTRAINT chk_params_value_type CHECK (value_type IN (
    'scalar', 'range', 'expression', 'list', 'text'
));
ALTER TABLE parameters ADD CONSTRAINT chk_params_confidence CHECK (confidence IS NULL OR confidence IN (
    'high', 'medium', 'low'
));
-- 类型化值一致性：对应类型的值列应非空
ALTER TABLE parameters ADD CONSTRAINT chk_params_scalar CHECK (
    value_type <> 'scalar' OR value_scalar IS NOT NULL
);
ALTER TABLE parameters ADD CONSTRAINT chk_params_range CHECK (
    value_type <> 'range' OR (value_min IS NOT NULL AND value_max IS NOT NULL)
);
ALTER TABLE parameters ADD CONSTRAINT chk_params_expression CHECK (
    value_type <> 'expression' OR value_expr IS NOT NULL
);
ALTER TABLE parameters ADD CONSTRAINT chk_params_list CHECK (
    value_type <> 'list' OR value_list IS NOT NULL
);
ALTER TABLE parameters ADD CONSTRAINT chk_params_text CHECK (
    value_type <> 'text' OR value_text IS NOT NULL
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_params_category ON parameters (category);
CREATE INDEX IF NOT EXISTS idx_params_subcategory ON parameters (subcategory) WHERE subcategory IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_params_material ON parameters (material_id) WHERE material_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_params_value_type ON parameters (value_type);
CREATE INDEX IF NOT EXISTS idx_params_confidence ON parameters (confidence);
CREATE INDEX IF NOT EXISTS idx_params_source ON parameters (source_file);
CREATE INDEX IF NOT EXISTS idx_params_symbol ON parameters (symbol) WHERE symbol IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_params_material_raw ON parameters (material_raw) WHERE material_raw IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_params_temp ON parameters (temperature_k) WHERE temperature_k IS NOT NULL;

-- 全文搜索 GIN 索引
CREATE INDEX IF NOT EXISTS idx_params_search ON parameters USING GIN (ts_vector);

-- RLS
ALTER TABLE parameters ENABLE ROW LEVEL SECURITY;
CREATE POLICY "parameters_public_read" ON parameters FOR SELECT USING (true);

-- ============================================================
-- 7. 全文搜索触发器
-- ============================================================
-- 自动从 name + name_en + symbol + category + subcategory 生成英文 tsvector
CREATE OR REPLACE FUNCTION parameters_tsvector_update()
RETURNS trigger AS $$
BEGIN
    NEW.ts_vector :=
        to_tsvector('english',
            coalesce(NEW.name, '') || ' ' ||
            coalesce(NEW.name_zh, '') || ' ' ||
            coalesce(NEW.name_en, '') || ' ' ||
            coalesce(NEW.symbol, '') || ' ' ||
            coalesce(NEW.category, '') || ' ' ||
            coalesce(NEW.subcategory, '') || ' ' ||
            coalesce(NEW.material_raw, '') || ' ' ||
            coalesce(NEW.method, '') || ' ' ||
            coalesce(NEW.unit, '')
        );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_params_tsvector
    BEFORE INSERT OR UPDATE ON parameters
    FOR EACH ROW
    EXECUTE FUNCTION parameters_tsvector_update();

-- ============================================================
-- 8. 术语表（中文 → 英文映射，用于搜索转换）
-- ============================================================
CREATE TABLE IF NOT EXISTS terminology (
    id              serial PRIMARY KEY,
    term_zh         text UNIQUE NOT NULL,         -- 中文术语
    term_en         text NOT NULL,                -- 英文对应
    category        text,                         -- 所属分类
    created_at      timestamptz DEFAULT now()
);

-- 预置术语
INSERT INTO terminology (term_zh, term_en, category) VALUES
    -- 基础概念
    ('扩散', 'diffusion', 'general'),
    ('扩散系数', 'diffusion coefficient', 'diffusion'),
    ('肿胀', 'swelling', 'fuel_performance'),
    ('肿胀率', 'swelling rate', 'swelling'),
    ('辐照肿胀', 'irradiation swelling', 'swelling'),
    ('裂变气体释放', 'fission gas release', 'fgr'),
    ('裂变气体', 'fission gas', 'fgr'),
    ('气泡', 'bubble', 'bubble'),
    ('气泡核化', 'bubble nucleation', 'bubble'),
    ('气泡生长', 'bubble growth', 'bubble'),
    ('热导率', 'thermal conductivity', 'thermal'),
    ('热膨胀', 'thermal expansion', 'thermal'),
    ('比热容', 'specific heat capacity', 'thermal'),
    ('弹性模量', 'elastic modulus', 'elastic'),
    ('剪切模量', 'shear modulus', 'elastic'),
    ('泊松比', 'Poisson ratio', 'elastic'),
    ('蠕变', 'creep', 'creep'),
    ('辐照蠕变', 'irradiation creep', 'creep'),
    ('相变', 'phase transformation', 'phase_transformation'),
    ('熔点', 'melting point', 'thermodynamic'),
    ('密度', 'density', 'physical'),
    ('燃耗', 'burnup', 'irradiation'),
    ('快中子注量', 'fast neutron fluence', 'irradiation'),
    ('位移损伤', 'displacement per atom', 'irradiation'),
    ('温度', 'temperature', 'general'),
    ('实验', 'experiment', 'method'),
    ('密度泛函', 'density functional theory', 'simulation'),
    ('分子动力学', 'molecular dynamics', 'simulation'),
    ('相场', 'phase field', 'simulation'),
    ('蒙特卡洛', 'Monte Carlo', 'simulation'),
    -- 材料名
    ('铀', 'uranium', 'material'),
    ('钼', 'molybdenum', 'material'),
    ('锆', 'zirconium', 'material'),
    ('钚', 'plutonium', 'material'),
    ('二氧化铀', 'uranium dioxide', 'material'),
    ('混合氧化物', 'mixed oxide', 'material'),
    ('包壳', 'cladding', 'material'),
    ('燃料', 'fuel', 'material'),
    ('合金', 'alloy', 'material'),
    ('冷却剂', 'coolant', 'material'),
    ('高熵合金', 'high entropy alloy', 'material'),
    -- 物理量
    ('活化能', 'activation energy', 'thermodynamic'),
    ('指前因子', 'pre-exponential factor', 'diffusion'),
    ('表面张力', 'surface tension', 'thermodynamic'),
    ('晶界', 'grain boundary', 'microstructure'),
    ('晶粒', 'grain', 'microstructure'),
    ('位错', 'dislocation', 'microstructure'),
    ('空位', 'vacancy', 'microstructure'),
    ('间隙原子', 'interstitial', 'microstructure'),
    ('裂变产物', 'fission product', 'irradiation'),
    ('氙', 'xenon', 'material'),
    ('氪', 'krypton', 'material'),
    ('燃料包壳化学相互作用', 'fuel cladding chemical interaction', 'fuel_performance'),
    ('重定位', 'redistribution', 'fuel_performance')
ON CONFLICT (term_zh) DO NOTHING;

-- ============================================================
-- 9. 审计日志表
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id              serial PRIMARY KEY,
    action          text NOT NULL,                -- INSERT / UPDATE / DELETE
    table_name      text NOT NULL,
    record_id       text,
    changes         jsonb,                        -- {"field": {"old": ..., "new": ...}}
    operator        text DEFAULT 'system',
    timestamp       timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_table ON audit_log (table_name);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log (timestamp);

-- ============================================================
-- 10. 审计触发器
-- ============================================================
CREATE OR REPLACE FUNCTION audit_trigger_func()
RETURNS trigger AS $$
DECLARE
    diff jsonb;
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (action, table_name, record_id, changes)
        VALUES ('INSERT', TG_TABLE_NAME, NEW.id::text,
            jsonb_build_object('id', NEW.id, 'name', NEW.name, 'value_type', NEW.value_type));
    ELSIF TG_OP = 'UPDATE' THEN
        diff := '{}';
        IF COALESCE(NEW.name, '') <> COALESCE(OLD.name, '') THEN
            diff := diff || jsonb_build_object('name', jsonb_build_object('old', OLD.name, 'new', NEW.name));
        END IF;
        IF COALESCE(NEW.value_scalar::text, '') <> COALESCE(OLD.value_scalar::text, '') THEN
            diff := diff || jsonb_build_object('value_scalar', jsonb_build_object('old', OLD.value_scalar, 'new', NEW.value_scalar));
        END IF;
        IF COALESCE(NEW.confidence, '') <> COALESCE(OLD.confidence, '') THEN
            diff := diff || jsonb_build_object('confidence', jsonb_build_object('old', OLD.confidence, 'new', NEW.confidence));
        END IF;
        IF COALESCE(NEW.notes, '') <> COALESCE(OLD.notes, '') THEN
            diff := diff || jsonb_build_object('notes', jsonb_build_object('old', OLD.notes, 'new', NEW.notes));
        END IF;
        IF COALESCE(NEW.material_raw, '') <> COALESCE(OLD.material_raw, '') THEN
            diff := diff || jsonb_build_object('material_raw', jsonb_build_object('old', OLD.material_raw, 'new', NEW.material_raw));
        END IF;
        IF COALESCE(NEW.unit, '') <> COALESCE(OLD.unit, '') THEN
            diff := diff || jsonb_build_object('unit', jsonb_build_object('old', OLD.unit, 'new', NEW.unit));
        END IF;
        IF diff <> '{}' THEN
            INSERT INTO audit_log (action, table_name, record_id, changes)
            VALUES ('UPDATE', TG_TABLE_NAME, NEW.id::text, diff);
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (action, table_name, record_id, changes)
        VALUES ('DELETE', TG_TABLE_NAME, OLD.id::text,
            jsonb_build_object('id', OLD.id, 'name', OLD.name));
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- 在 parameters 表上启用审计
CREATE TRIGGER trg_params_audit
    AFTER INSERT OR UPDATE OR DELETE ON parameters
    FOR EACH ROW
    EXECUTE FUNCTION audit_trigger_func();

-- ============================================================
-- 11. 有用的视图和 RPC 函数
-- ============================================================

-- 11.1 按材料统计参数
CREATE OR REPLACE VIEW v_params_by_material AS
SELECT
    m.id AS material_id,
    m.name AS material_name,
    m.alloy_system,
    m.material_type,
    COUNT(p.id) AS param_count,
    COUNT(DISTINCT p.category) AS category_count,
    COUNT(DISTINCT p.source_file) AS source_count
FROM materials m
LEFT JOIN parameters p ON p.material_id = m.id
GROUP BY m.id, m.name, m.alloy_system, m.material_type
ORDER BY param_count DESC;

-- 11.2 按分类统计参数
CREATE OR REPLACE VIEW v_params_by_category AS
SELECT
    c.name AS category,
    c.name_zh AS category_zh,
    COUNT(p.id) AS param_count,
    COUNT(DISTINCT p.material_id) AS material_count,
    ROUND(AVG(CASE WHEN p.confidence = 'high' THEN 1.0
                    WHEN p.confidence = 'medium' THEN 0.5
                    ELSE 0.0 END), 2) AS avg_confidence
FROM categories c
LEFT JOIN parameters p ON p.category = c.name
GROUP BY c.name, c.name_zh
ORDER BY param_count DESC;

-- 11.3 中文搜索 RPC：将中文术语转换为英文后全文搜索
CREATE OR REPLACE FUNCTION search_parameters(
    query_text text,
    param_category text DEFAULT NULL,
    param_material text DEFAULT NULL,
    param_confidence text DEFAULT NULL,
    limit_count int DEFAULT 50
)
RETURNS TABLE (
    id text, name text, name_en text, symbol text,
    category text, subcategory text, value_type text,
    value_scalar numeric, value_min numeric, value_max numeric,
    value_expr text, value_str text, unit text,
    material_name text, material_raw text,
    temperature_k numeric, confidence text, source_file text,
    rank real
) AS $$
DECLARE
    translated_query text;
    rec record;
BEGIN
    -- 1. 用术语表将中文查询词替换为英文
    translated_query := query_text;
    
    -- 2. 按术语长度降序替换（长词优先，避免"扩散"先于"扩散系数"被替换）
    FOR rec IN SELECT term_zh, term_en, length(term_zh) AS zl
               FROM terminology ORDER BY length(term_zh) DESC LOOP
        translated_query := replace(translated_query, rec.term_zh, rec.term_en);
    END LOOP;
    
    -- 2. 执行全文搜索 + 可选过滤
    RETURN QUERY
    SELECT
        p.id, p.name, p.name_en, p.symbol,
        p.category, p.subcategory, p.value_type,
        p.value_scalar, p.value_min, p.value_max,
        p.value_expr, p.value_str, p.unit,
        m.name AS material_name, p.material_raw,
        p.temperature_k, p.confidence, p.source_file,
        ts_rank(p.ts_vector, plainto_tsquery('english', translated_query)) AS rank
    FROM parameters p
    LEFT JOIN materials m ON p.material_id = m.id
    WHERE
        p.ts_vector @@ plainto_tsquery('english', translated_query)
        AND (param_category IS NULL OR p.category = param_category)
        AND (param_material IS NULL OR m.name = param_material)
        AND (param_confidence IS NULL OR p.confidence = param_confidence)
    ORDER BY rank DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql STABLE;

-- 11.4 获取总览统计
CREATE OR REPLACE FUNCTION stats_overview()
RETURNS jsonb AS $$
DECLARE
    result jsonb;
BEGIN
    SELECT jsonb_build_object(
        'total_parameters', (SELECT count(*) FROM parameters),
        'total_materials', (SELECT count(*) FROM materials),
        'total_literature', (SELECT count(*) FROM literature),
        'total_categories', (SELECT count(*) FROM categories),
        'params_by_confidence', (
            SELECT jsonb_object_agg(confidence, cnt) FROM (
                SELECT confidence, count(*) AS cnt
                FROM parameters
                GROUP BY confidence
            ) sub
        ),
        'params_by_type', (
            SELECT jsonb_object_agg(value_type, cnt) FROM (
                SELECT value_type, count(*) AS cnt
                FROM parameters
                GROUP BY value_type
            ) sub
        ),
        'top_materials', (
            SELECT jsonb_agg(jsonb_build_object(
                'name', name,
                'count', param_count
            )) FROM (
                SELECT m.name, count(p.id) AS param_count
                FROM materials m
                JOIN parameters p ON p.material_id = m.id
                GROUP BY m.name
                ORDER BY param_count DESC
                LIMIT 10
            ) sub
        )
    ) INTO result;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- 12. 完成
-- ============================================================
-- 验证
SELECT 'Schema v2 created successfully' AS status;
SELECT count(*) AS material_count FROM materials;
SELECT count(*) AS param_count FROM parameters;
SELECT count(*) AS term_count FROM terminology;
