# 调研报告：AI Infrastructure for Materials Discovery 页面资源盘点与 NFMD 适用性评估

- **调研对象**：<https://palarmi.github.io/ai-infrastructure-for-materials-discovery/>
- **调研日期**：2026-09-10
- **更新（2026-09-11）**：文献获取存在网页抓取后备需求——本地 Zotero 库缺失所需文献时需走网页抓取。§4.1.6 网页抓取工具族由「不适用」改判为「有条件引入」，§3 / §5 / §6 联动更新。
- **页面性质**：该页面是论文 *AI-powered open-source infrastructure for accelerating materials discovery and advanced manufacturing*（Salas, M. et al., **Communications Materials**, 2026, <https://www.nature.com/articles/s43246-026-01105-0>）的配套策展资源页，作者来自 CMU Amir Barati Farimani 课题组（页面域名 `palarmi` 即其名）。页面按论文四章结构（物理系统数据采集 → 数据预处理/存储/组织 → 数据与 AI 管线 → 新兴技术）组织资源链接。
- **评估基准**：NFMD 当前栈 = Python 3.10+（uv 管理，运行时依赖仅 fastapi / psycopg / pydantic / uvicorn，见 `pyproject.toml`）+ PostgreSQL 16（RLS、触发器、tsvector）+ 五阶段规则化 ETL（`scripts/etl/`：extract → validate → transform → normalize → load）。知识源侧已有 Zotero + MinerU（PDF 解析）+ llm-wiki + Materials Project（见 `README.md` 架构图）。依赖引入态度受 [ADR-0002](../adr/0002-dependencies-accepted-not-created.md) 约束（依赖经接口注入、模块内不自建），配置受 [ADR-0003](../adr/0003-single-db-url-no-secret-defaults.md) 约束（单一 `NFMD_DB_URL`），包布局受 [ADR-0004](../adr/0004-in-place-package-seam.md) 约束（`scripts/etl` 原地包化）。DB 写操作受 [docs/database-safety-rules.md](../database-safety-rules.md) 约束。

---

## 1. TL;DR

最值得 NFMD 吸收的 5 项（按投入产出比排序）：

| # | 项目 | 一句话理由 | 分级 |
|---|------|-----------|------|
| 1 | **ChatExtract**（Polak et al., Nat Commun 2024） | 与 NFMD extract 阶段痛点完全同构：双通道抽取 + 自审计式 prompt 协议可直接抬升抽取质量并结构化 confidence 元数据；**纯方法论，零新依赖**，与 ADR-0002 无冲突 | 借鉴思路（方法级直接落地） |
| 2 | **pymatgen**（MIT，活跃） | `Composition` 类可承担 normalize 阶段化学式解析/校验（UO2+x、U-10Mo wt.% 一类写法），补 alias map 之外的机械归一；MIT 许可，Materials Project 亲缘项目 | 直接引入（optional extras + 接口注入） |
| 3 | **PIF 数据模型**（Citrine，Apache-2.0 但库已归档） | 其"多来源、多条件、带 provenance 的层级式物性记录"正是 NFMD parameters 表（value_type + temperature_k + uncertainty + literature_id）的上位参照；只借 schema 思想，不引归档代码 | 借鉴思路 |
| 4 | **NEMAD**（Itani et al., Nat Commun 2025） | 与 NFMD 完全同弧线的先例："LLM 文献抽取 → 结构化数据库 → ML 建模"，其记录 schema 与 Zenodo 版本化发布模式值得对标 | 借鉴思路 |
| 5 | **OPTIMADE**（规范 CC-BY-4.0，社区活跃） | 材料数据 API 事实标准；NFMD FastAPI 可中期对齐其 filter 语法以接入生态，不必立即实现 provider | 借鉴思路（中期） |

不建议引入：云厂商服务、区块链/量子板块、商业 GUI 清洗工具、电池/聚合物专用抽取器、停滞的上游小库（CrabNet、BatteryDataExtractor、pypif）。

补充评估（2026-09-11）：文献获取存在网页抓取后备需求（本地库缺文献时），抓取工具栈由「不适用」改判为**有条件引入**——默认方案 httpx + Beautiful Soup（静态页），Scrapy（批量）与 Playwright（JS 站点）按需扩展，抓取器定位为 ETL 之上游的获取层组件并带 SSRF 防护硬约束，详见 §4.1.6 与 §5。

---

## 2. 页面内容概览（项目清单及原页面分类）

计数口径：**去重后共点名 112 个条目**（Materials Project 与 AFLOW 跨节重复罗列，各计 1 次；RDKit、ORCA 亦有跨节重复）。另有若干"范式/概念"条目（SVM/RF/GAN 等模型族、Merkle 树/智能合约等）不计入项目数。清单如下，括号内为原页面所属小节。

### 2.1 第一部分 Physical System: Data Collection（43 项）

- **传统实验数据库（8）**：PubChem、ChEMBL、COD（Crystallography Open Database）、ZINC、ChemSpider、CSD（Cambridge Structural Database）、ICSD、PDB（Protein Data Bank）
- **模拟软件（14）**：LAMMPS、GROMACS、NAMD、AMBER、VASP、Quantum ESPRESSO、ABINIT、WIEN2k、Gaussian、ORCA、Q-Chem、GAMESS、NWChem、CP2K
- **开放材料数据库（4）**：Materials Project（*NFMD 已在用，见 `README.md` 知识源层*）、OQMD、AFLOWlib、NOMAD
- **网页抓取工具（12）**：Beautiful Soup、Scrapy、Selenium、Puppeteer、Octoparse、ParseHub、WebHarvy、Portia、Diffbot、Content Grabber、Helium、MechanicalSoup
- **文献抽取工具（5）**：MaterialsBERT、BatteryDataExtractor、ChatExtract、NEMAD、Polymer Scholar

### 2.2 第二部分 Data Preprocessing, Storage and Organization（22 项新增 + 2 重复）

- **数据预处理工具（10）**：Microsoft Excel、Pandas、NumPy、OpenRefine、dplyr、Apache Spark、Talend、RDKit、KNIME、Alteryx
- **云与边缘平台（8）**：AWS、Microsoft Azure、Google Cloud、Cisco、Intel、NVIDIA、IBM Cloud、Oracle Cloud
- **数据组织与索引（6，含 2 重复）**：EMMO（European Materials Modelling Ontology）、AiiDA、FAIR Principles、Open Materials Database（OMDB）；Materials Project、AFLOW 与前节重复

### 2.3 第三部分 Data and AI Pipeline（34 项新增 + 2 重复）

- **数据处理（6）**：pymatgen、matminer、scikit-learn、ASE、TensorFlow、PyTorch（RDKit 重复）
- **AI 建模——范式描述（不计项目数）**：SVM/随机森林/决策树/ANN/贝叶斯优化；GNN/多模态深度学习/CNN；ML 原子间势（MLIP，页面点名 MACE、CHGNet）；变分自编码器/GAN/扩散模型；联邦学习
- **可解释 AI（6）**：SHAP、LIME、Captum、Score-CAM、Grad-CAM、CrabNet（注意力归因范式点名 "CrabNet-style"）
- **LLM → Agentic AI（4）**：MOFGen（[arXiv:2504.14110](https://arxiv.org/abs/2504.14110)）、MAPPS（[arXiv:2506.05616](https://arxiv.org/abs/2506.05616)）、MatAgent（<https://github.com/adibgpt/MatAgent>）、MOFGPT（[JCIM 2025](https://pubs.acs.org/doi/10.1021/acs.jcim.5c01625)，本页作者所在组的工作）
- **云上 AI 基础设施（4）**：SageMaker、Google Cloud AI、Azure ML、IBM Watson
- **开源部署（6）**：GitHub、OpenKIM、GitHub Pages、Docker、Flask、Streamlit（Materials Project、pymatgen 重复）
- **开放模型与数据（6）**：BLOOM、Common Crawl、The Pile、LLaMA、Gemini、GPT 系

### 2.4 第四部分 Emerging Technologies（13 项新增）

- **量子计算（5 个平台 + 算法概念）**：Qiskit Nature、PennyLane、TensorFlow Quantum、PySCF、D-Wave Ocean SDK（ORCA 重复）；算法为 VQE、Qubit-ADAPT-VQE、QPE、Grover 等范式描述
- **区块链与溯源（8）**：IPFS、PIF（Physical Information Files）、Hyperledger Fabric、OPTIMADE、MatSwarm、Makerchain、MDCS、NMRR（Merkle 树/智能合约为概念条目）

---

## 3. 分级推荐表

分级含义：**直接引入** = 作为 uv 依赖或数据资产进入仓库；**借鉴思路** = 不引代码/依赖，吸收其方法、schema 或流程设计；**不适用** = 与 NFMD 域、栈或约束不匹配。

| 项目 | 维度 | 分级 | 关键理由（详见 §4） |
|------|------|------|---------------------|
| ChatExtract | 提取 | **借鉴思路（方法级直接落地）** | prompt 协议零依赖，双通道+自审计直接适配 extract 阶段 |
| MaterialsBERT | 提取 | 借鉴思路 | 域内 BERT NER 可作预标注，但 license 未标注、需 ML 基建，中期试点 |
| BatteryDataExtractor | 提取 | 借鉴思路 | 管线结构（domain BERT→NER→属性关联→结构化输出）是教科书式参考；MIT 但 2023 年起停滞、20 stars，域不符（电池电化学） |
| NEMAD | 提取/建模 | 借鉴思路 | 文献→DB→ML 完整先例，schema 与发布模式可对标 |
| Polymer Scholar | 提取 | 借鉴思路 | 闭源在线平台，不可引入；"按属性/材料检索"门户交互可参考 |
| 网页抓取工具族（BS4/httpx/Scrapy/Playwright 等） | 提取（获取层） | **有条件引入** | 本地文献缺失时的后备获取路径：开放 API 优先，HTML 抓取最后手段；httpx+BS4 默认，Scrapy/Playwright 按需；带 SSRF 防护与 allowlist（详见 §4.1.6） |
| pymatgen | 分析/提取 | **直接引入** | MIT、极活跃；normalize 阶段化学式解析校验；经 optional extras + 注入控制依赖面 |
| matminer | 分析/建模 | 中期可选 | BSD 类（LBNL），活跃；特征工程与基准数据集在建模侧有价值，依赖链重 |
| OpenRefine | 分析 | 借鉴思路（工具级） | alias map 人工策展可用其聚类辅助，一次性使用、不进依赖 |
| RDKit | 分析 | 不适用 | 小分子化学信息学，不适合锕系陶瓷/合金体系 |
| Excel/KNIME/Alteryx/Talend/Spark/dplyr | 分析 | 不适用 | 商业 GUI 或重型分布式栈，违背可重复 ETL 与最小依赖现状 |
| AiiDA | 存储 | 借鉴思路 | provenance 图数据模型（MIT、活跃）可启发 audit_log 之外的溯源设计 |
| FAIR Principles | 存储 | 借鉴思路 | literature 表补 DOI/license 字段、数据发布规范的方向性指导 |
| PIF（pypif） | 存储 | 借鉴思路 | 层级式物性记录 schema 是 parameters 表上位参照；库已归档（2022），只借思想 |
| OPTIMADE | 存储 | 借鉴思路（中期） | API 标准（规范 CC-BY-4.0，活跃）；NFMD 可对齐 filter 语法 |
| EMMO | 存储 | 借鉴思路（长期） | 形式本体（CC-BY-4.0，极活跃）；categories 表的本体映射远期目标 |
| MDCS / NMRR | 存储 | 借鉴思路 | NIST 模板驱动式数据策展（活跃），启发 schema 版本化策展 |
| NOMAD | 存储 | 借鉴思路 | 开放数据平台的 metainfo 与溯源设计；远期数据发布渠道候选 |
| COD / ICSD / CSD 等 | 存储/建模 | 不适用（中期再看 COD） | COD 为 CC0 可作晶体结构参考源；CSD/ICSD 商业授权 |
| Materials Project / OQMD / AFLOWlib | 建模 | 借鉴思路 | DFT 计算库可作 NFMD 实验参数的交叉验证参照（MP 已是 NFMD 知识源） |
| OpenKIM | 建模 | 借鉴思路 | 势函数知识库 + 标准化性质测试体系（kim-api LGPL-2.1+），NFMD 数据可作其测试参照值 |
| MACE | 建模 | 不适用（合作方向） | MIT、极活跃的 MLIP 训练框架，但 GPU 训练管线超出 NFMD 仓库范围 |
| CHGNet | 建模 | 不适用（参考） | 修改版 BSD（LBNL，须署名条款）、活跃；同上，作为下游消费者记录 |
| CrabNet | 建模 | 中期可选（注意停更） | MIT；"成分→性质"+注意力可解释，形状契合 NFMD 数据；2023-04 后未更新，若用须冻结版本 |
| scikit-learn / SHAP / LIME / Captum | 建模 | 直接引入（建模侧脚本） | 宽松许可、事实标准；进独立分析入口，不污染五阶段管线 |
| MatAgent | 建模/提取 | 借鉴思路 | MIT；human-in-the-loop 多 agent 工作流 ↔ NFMD review_* 审查表；25 stars、2025-02 停更，只借架构 |
| MOFGen / MAPPS / MOFGPT | 建模 | 不适用 | MOF 生成式设计，域不符；MOFGPT 无 license 文件 |
| 云平台（AWS/Azure/GCP/IBM 等）、SageMaker 等 | 存储/建模 | 不适用 | 与单 PostgreSQL + RLS 架构及 ADR-0003 相悖 |
| 区块链板块（IPFS/Hyperledger/MatSwarm/Makerchain） | 存储 | 不适用 | NFMD 已有 audit_log 轻量溯源，无需分布式账本 |
| 量子板块（Qiskit Nature 等） | 建模 | 不适用 | 与 NFMD 当前目标无关 |
| PubChem/ChEMBL/ZINC/ChemSpider/PDB | 存储 | 不适用 | 分子/药物/蛋白域，与核燃料材料参数无关 |
| LAMMPS/GROMACS 等 14 款模拟软件 | 建模 | 不适用（文档级参考） | 仿真输入参数未来是 NFMD 潜在消费方，但软件本身不进仓库 |
| GitHub Pages/Docker/Flask/Streamlit | 存储 | 不适用（Streamlit 可选） | 部署细节；Streamlit 可作 review 工作台原型备选（Apache-2.0） |
| BLOOM/Common Crawl/The Pile/LLaMA/Gemini/GPT | 提取 | 不适用（作为 llm-wiki 的底座记录） | 通用 LLM/语料；NFMD 已通过 llm-wiki 使用商用 LLM 能力 |

---

## 4. 四个维度的详细分析

### 4.1 数据提取

NFMD 现状：PDF → MinerU 结构化 → llm-wiki 抽取 → JSON/text → `etl.extract` 产出 `ExtractedRecord` → `etl.validate` 九条规则校验。痛点在于抽取质量不可控、confidence 靠人工标注、缺结构化抽取协议。

#### 4.1.1 ChatExtract —— 借鉴思路（本报告最推荐，方法级直接落地）

- **一手来源**：论文 *Extracting accurate materials data from research papers with conversational language models and prompt engineering*，Polak, M.P. et al., **Nature Communications** 15, 2024，<https://pmc.ncbi.nlm.nih.gov/articles/PMC10882009/>；预印本 <https://arxiv.org/abs/2303.05352>。方法开放（论文附录给出完整 prompt），无正式软件依赖。
- **是什么**：用对话式 LLM 做材料数值抽取的 prompt 工程协议，核心是三步：① 把原文句子与抽取问题分离（防止模型被上下文带偏）；② **双通道独立抽取**（同一数据点问两次，答案不一致即丢弃）；③ **自审计追问**（要求模型对每个抽取给出 yes/no 级验证）。在固态电解质数据上 precision/recall 均达 ~90%+。
- **对 NFMD 的价值**：这正是 NFMD extract 阶段缺的"结构化抽取协议"。nfmd 的 confidence（high/medium/low）目前缺少客观判据，ChatExtract 的双通道一致性 + 自审计结果可以直接定义为 confidence 的生成规则：双通道一致且自审计通过 → high；一致但自审计存疑 → medium；不一致 → low 或拒收。落地成本为零：改 `scripts/etl/extract.py` 上游的 llm-wiki prompt 模板即可，不新增任何依赖，完全符合 ADR-0002 精神。
- **引入方式**：文档参考 + prompt 模板进仓库（如 `plans/` 或 llm-wiki 侧）；confidence 判据写入 validate 规则文档。
- **风险**：LLM 输出仍必须走 NFMD 全量规则校验（business key 去重、value_type 一致性），不能因"模型说了"而跳过 validate——这与 DB 安全红线的"入库前校验"精神一致。

#### 4.1.2 BatteryDataExtractor —— 借鉴思路

- **一手来源**：<https://github.com/ShuHuang/batterydataextractor>（**MIT**，Python，最后 push 2023-04，20 stars，**维护停滞**）；论文 Huang & Cole, *BatteryDataExtractor: battery-aware text-mining software…*, 2022，<https://pmc.ncbi.nlm.nih.gov/articles/PMC9627715/>；文档 <https://batterydataextractor.readthedocs.io/>。
- **是什么**：内嵌 BatteryBERT 的电池文献抽取管线：句子切分 → 化学实体 NER → 属性-值关联 → 结构化（CSV/tokenizer 可配置）。
- **对 NFMD 的价值**：它是"域内 BERT + 属性抽取 → 数据库"的成熟管线范例，其阶段划分与 NFMD 五阶段一一对应，可对照检视自身 extract→validate 衔接是否遗漏"属性-条件关联"环节（NFMD 的 temperature_k/burnup_range 字段对应它的 device/condition 关联）。但域不符（电池电化学 vs 核燃料）且已停滞，**不建议作为依赖引入**。

#### 4.1.3 MaterialsBERT —— 借鉴思路（中期试点）

- **一手来源**：模型权重 <https://huggingface.co/pranav-s/MaterialsBERT>（**模型卡片未标注 license，商用/再分发前须向作者确认**）；论文 Shetty, P. et al., *A general-purpose material property data extraction pipeline from large polymer corpora using natural language processing*, **npj Computational Materials** 9, 2023。相关同族：MatSciBERT（<https://github.com/m3rg-iitd/matscibert>，Gupta et al., npj Comput Mater 2022）、LBNL MatBERT（<https://lbnlp.github.io>）。
- **是什么**：在 240 万条材料学摘要上从 PubMedBERT 继续预训练的域内语言模型，微调后做性质实体 NER/关系抽取，产出 ~30 万条聚合物性质记录。
- **对 NFMD 的价值**：中期可为核燃料实体（UO₂、MOX、Zircaloy、燃耗、热导率等中英混合术语）训练轻量 NER 预标注器，降低 llm-wiki 抽取漏检率；亦可对历史已入库参数做回扫补标。但需要 GPU 推理与训练数据标注，超出当前规则化管线的维护成本预算，建议只做评估试点。

#### 4.1.4 NEMAD —— 借鉴思路（全流程对标对象）

- **一手来源**：Itani, S. et al., *The northeast materials database for magnetic materials*, **Nature Communications** (2025)，<https://www.nature.com/articles/s41467-025-64458-z>；预印本 <https://arxiv.org/abs/2409.15675>；数据集 NEMAD-MagneticML 发布于 Zenodo。
- **是什么**：用 NLP/LLM 从文献抽取 ~67,500 条磁性材料条目（成分、相变温度、结构、来源），再训练分类/回归模型预测居里/奈尔温度——"文献 → 结构化库 → ML"与 NFMD 的目标弧线完全一致（NFMD 面向核燃料参数）。
- **对 NFMD 的价值**：① 记录 schema（成分 + 温度条件 + 方法 + 来源引用的平铺结构）可直接与 NFMD parameters 表对照查缺；② 发布模式值得照抄：**数据集版本化 + 持久标识（Zenodo DOI）+ 伴随 ML 基线**，这是 NFMD 未来对外发布参数库（比如 API 快照导出）的模板。

#### 4.1.5 Polymer Scholar —— 借鉴思路（不可引入）

- **一手来源**：Gupta, S. et al., *Data extraction from polymer literature using large language models*, **Communications Materials** 5 (2024)，<https://www.nature.com/articles/s43246-024-00708-9>；平台 <https://polymerscholar.org/>（Georgia Tech，Ramprasad 组）。
- **是什么/价值**：LLM 从期刊摘要规模化抽取聚合物性质并公开检索门户（按聚合物名或属性查询）。闭源平台，不可引入；但其"按 property / 按 material 两个入口检索"的交互恰与 NFMD API 的 `/search?q=…&material=…` 设计互相印证。

#### 4.1.6 网页抓取工具族（12 项）—— 有条件引入（文献获取后备路径，2026-09-11 修正）

- **需求定位**：NFMD 文献获取是 local-first——Zotero 本地库 + MinerU 解析为主路径；当本地库覆盖不到所需文献时，走网页抓取/在线获取作为**后备路径**。因此本组工具改判为「有条件引入」，其定位是**获取层（acquisition）组件，不是五阶段 ETL 的一部分**。
- **优先级原则（抓取是最后手段）**：① 本地 Zotero 库 → ② 开放元数据/全文 API（Crossref、OpenAlex、Unpaywall、Europe PMC、arXiv——解决 DOI 元数据、OA 副本定位、预印本获取，占「本地没有」场景的大多数，且无 ToS/robots 风险）→ ③ 结构化开放数据库直下（如 Materials Project API，NFMD 已在用）→ ④ 目标站点官方 API → ⑤ 最后才是 HTML 抓取（先静态页，后动态页）。
- **分层推荐**（license 与活跃度经 GitHub API 核实，2026-09-11）：
  - **静态 HTML（默认方案）**：**httpx**（BSD-3，活跃，~15.5k stars）+ **Beautiful Soup**（MIT）。Beautiful Soup 只负责解析，需配 HTTP 客户端；原页面 12 项清单未含此搭配项，httpx 系按场景补充（不在原清单，下同）。
  - **批量/多源爬取（按需扩展）**：**Scrapy**（BSD-3，活跃）——自带 robots.txt 遵循（ROBOTSTXT_OBEY）、自动限速（AUTOTHROTTLE）、重试与去重，适合目标源增多后统一管理。单源偶发抓取用 httpx + BS4 更轻，不必先上框架。
  - **表单/登录型站点（备选）**：**MechanicalSoup**（MIT，活跃，~4.9k stars）——requests + BS4 的表单自动提交，适合机构订阅页表单跳转类场景。
  - **JS 重度站点（最后手段）**：**Playwright**（playwright-python，Apache-2.0，极活跃，~15k stars）优于 **Selenium**（Apache-2.0）——自动等待机制、现代 API、多浏览器；二者选一即取 Playwright，Selenium 及其封装 Helium 不单独引入。
  - **不引入**：**Puppeteer**（Apache-2.0 但 Node.js 生态，与 Python 栈不符）；**Octoparse / ParseHub / WebHarvy / Diffbot / Content Grabber**（商业 SaaS：许可成本、闭源、抓取数据经第三方服务器）；**Portia**（BSD-3，~9.5k stars，Scrapinghub 可视化爬取，**仓库已归档**、最后 push 2024-06，停止维护）。
- **抓取组件的架构与安全约束（硬性要求）**：
  1. **架构定位**：抓取器位于五阶段 ETL 之外、extract 之上游。产物是**落盘的文献文件**（PDF/HTML），进入与 Zotero 相同的资料入口（MinerU → llm-wiki → `etl.extract`）；抓取内容**不得**直接生成 ExtractedRecord，更不得绕过 validate 写库。
  2. **SSRF 防护**：仅允许 http/https；发起请求前校验 host 并解析 DNS，拒绝 localhost、环回、私有（RFC 1918）与保留地址段；跟随重定向后须复检目标。
  3. **域名 allowlist 配置化**：允许抓取的域名白名单进 Settings 冻结快照（沿 ADR-0003 精神：环境变量只在入口读一次），allowlist 外域名一律拒绝。
  4. **抓取礼仪**：遵守 robots.txt、限速、带联系方式的 UA 标识；有官方/开放 API 的源一律走 API。
  5. **依赖形态**：独立 optional dependency-group（如 `acquire`）+ 独立入口（etl 包外，处置方式同 §4.4.4 分析侧脚本），不进 etl 包默认依赖（符合 ADR-0002/0004）。
- **结论**：httpx + Beautiful Soup 作为默认组合直接引入（extras）；Scrapy、Playwright 记为按需扩展（先不装，需求出现再评估）；Puppeteer、商业 SaaS、Portia 不引入。

### 4.2 分析（校验 / 单位归一 / 别名归一 / confidence）

NFMD 现状：`etl.validate`（9 条规则 + fatal/error/warn 三级 severity）、`etl.normalize`（`MaterialNormalizer` + `plans/material-alias-map.json`，单位与材料名归一）、confidence 三级人工/抽取侧标注。

#### 4.2.1 pymatgen —— 直接引入（本报告中唯一推荐进入 `uv.lock` 的新依赖）

- **一手来源**：<https://github.com/materialsproject/pymatgen>（**MIT**（仓库 LICENSE 为 MIT 文本），~1960 stars，最后 push 2026-08，极活跃，Materials Project 官方分析库）；官网 <https://pymatgen.org/>。
- **是什么**：Python Materials Genomics——材料结构/成分/热力学分析的事实标准库，`Composition`、`Element`、结构匹配等类是生态通用语汇。
- **对 NFMD 的价值**：normalize 阶段目前靠 alias map 做名称归一，对**化学式形态**的输入（`UO2+x`、`U-10wt.%Mo`、`(U,Pu)O2`、上下标变体）缺少机械校验与规范化。pymatgen 的 `Composition` 可以：① 校验化学式合法性（元素符号、计量比）；② 生成规范化成分串作为 business key 的稳定成分表示；③ 为 alias map 提供成分等价判据（UO2 与 UO₂.00 归并）。这能显著减少 alias map 的手工维护面。
- **引入方式**：`uv add --optional chem pymatgen`（extras 隔离，不进默认依赖集）；在 `etl.normalize` 定义 `FormulaNormalizer` 接口，pymatgen 实现经构造参数注入（ADR-0002：依赖只接受、不创建）；未安装 pymatgen 时降级为现有 alias-map 路径，测试用桩实现。**依赖体量提示**：pymatgen 传递依赖较多（numpy、scipy、monty 等），这是它进 extras 而非核心依赖的原因。
- **风险**：依赖树膨胀（uv.lock 变大、CI 变慢）；RLS/DB 侧零影响（纯分析库不触库）。schema 无改动，不触发 🟡 审批线。

#### 4.2.2 matminer —— 中期可选

- **一手来源**：<https://github.com/hackingmaterials/matminer>（LBNL 出品，BSD 类版权声明（GitHub 无法自动识别，引入前核对 LICENSE），616 stars，最后 push 2026-09，活跃）。
- **是什么**：材料数据挖掘工具箱：特征化器（featurizers）、数据集加载、ML 前处理。
- **对 NFMD 的价值**：分析侧——用特征器对已入库参数做异常值检测（如同一材料同一属性数值离群），反哺 validate 规则；建模侧——成分特征是下游性质预测的标准输入。依赖链重（依赖 pymatgen + sklearn），放建模/分析子项目，不进 etl 包。

#### 4.2.3 OpenRefine —— 借鉴思路（工具级辅助）

- **一手来源**：<https://github.com/OpenRefine/OpenRefine>（**BSD-3-Clause**，12k stars，最后 push 2026-09，活跃）。
- **价值**：其文本聚类（key collision / nearest neighbor）方法对 alias map 策展很有用：导入 parameters 的 `material_raw` 原始字符串列，聚类发现"U-10Mo / U–10 wt% Mo / U10Mo"一类的变体，人工确认后回写 `plans/material-alias-map.json`。作为一次性桌面工具使用，**不作为仓库依赖**。

#### 4.2.4 AiiDA —— 借鉴思路

- **一手来源**：<https://github.com/aiidateam/aiida-core>（**MIT**（LICENSE.txt 为 MIT 文本），583 stars，最后 push 2026-09（当日仍有提交），活跃）；官网 <https://www.aiida.net/>。
- **是什么**：带**自动完整 provenance** 的计算工作流管理器：每次计算/数据生成都记录为有向无环图节点（输入→过程→输出），可重放、可追溯。
- **对 NFMD 的价值**：不引入运行时，但 provenance 数据模型值得吸收——NFMD 的 audit_log 只记录参数变更前后值，缺"来源链"：`literature → extract 运行(Run) → validate 判定 → 参数版本`。若未来参数被下游（燃料性能程序）质疑，需要能回答"这条值从哪篇文献的哪次抽取来"。参考 AiiDA 的实体-链接设计，在 schema 演进时考虑 provenance 字段（**schema 变更属 🟡 需审批**）。

#### 4.2.5 数据预处理杂项 —— 不适用/已具备

Pandas/NumPy（NFMD 运行时依赖刻意最小化，二者均未引入；如引入走同 pymatgen 的 extras 模式）；Excel/KNIME/Alteryx/Talend（商业或 GUI，违背可重复性）；Apache Spark/dplyr（规模不符/语言不符）；RDKit（小分子域，锕系氧化物/合金不适用）。

### 4.3 存储（schema / 标准 / 溯源 / PostgreSQL 相容性）

NFMD 现状：PostgreSQL 16 单库，8 表 + 3 视图 + 触发器/函数；RLS 双角色；audit_log 追加式审计；business key 唯一约束去重；load mode 三态。

#### 4.3.1 PIF（Physical Information Files，Citrine）—— 借鉴思路

- **一手来源**：Citrine 开放数据格式文档与工具包 <https://github.com/CitrineInformatics/pypif>（**Apache-2.0，但仓库已于 2022 年归档**）；格式说明 <https://citrineinformatics.github.io/pif-documentation/>。
- **是什么**：材料信息学史上最有影响力的层级式数据记录格式之一：一条物性记录内嵌**多来源、多条件分支**（同一性质在不同温度/批次下的值以树状结构共存），每支带 provenance 与引用。
- **对 NFMD 的价值**：NFMD parameters 表把 value_type 摊平成五列（scalar/range/expression/list/text）+ 条件列（temperature_k 等），本质是 PIF 的一层简化版。当出现"同一参数多温度点（value_list）+ 多文献分歧值"时，NFMD 目前的表达会吃紧。PIF 的条件树思想提示一个不破坏现有 schema 的演进路径：**新增"条件组"概念或以 value_list 承载 (条件, 值) 对**——任何落地都属 schema 变更，须走 🟡 审批 + 备份 + 事务（DB 安全红线）。

#### 4.3.2 OPTIMADE —— 借鉴思路（中期 API 对齐）

- **一手来源**：规范 <https://github.com/Materials-Consortia/OPTIMADE>（**CC-BY-4.0**，108 stars，最后 push 2026-08，活跃）；官网 <https://www.optimade.org/>；参考实现 <https://github.com/Materials-Consortia/optimade-python-tools>。
- **是什么**：材料数据库联合体（Materials Consortia）制定的 REST API 标准：统一 filter 查询语法、资源类型（structures/reference 等）、分页与字段命名，让 LAMMPS/ASE 等客户端一份代码查询所有 provider。
- **对 NFMD 的价值**：NFMD 是参数库而非结构库，做完整 OPTIMADE provider 收益有限；但**filter 语法对齐**（`material_id="UO2" AND category="thermal"` 式查询）与错误码/分页约定值得在 FastAPI 层采纳，为未来接入生态客户端铺路。中期评估 optimade-python-tools（可挂 FastAPI）成本后再定。

#### 4.3.3 MDCS / NMRR（NIST）—— 借鉴思路

- **一手来源**：MDCS（Materials Data Curation System）<https://github.com/usnistgov/MDCS>（活跃，最后 push 2026-08；美国政府作品，多为公有领域性质许可）；NIST Materials Repository <https://materialsdata.nist.gov/>。
- **价值**：MDCS 的"**模板（XSD schema）驱动录入 + 逐条策展 + 版本化发布**"模式与 NFMD"extract→validate→load + review_* 审查"同构，其公开的核材料相关策展模板可作 categories/schema 设计参照。Java/XSD 技术栈不同，不引入代码。

#### 4.3.4 NOMAD —— 借鉴思路

- **一手来源**：<https://nomad-lab.eu/>（开放材料科学数据平台，源码开源于 MPCDF GitLab nomad-lab 组）；论文《NOMAD: The distributed repository…》系列。
- **价值**：其 metainfo 数据模型（材料 + 计算 + 条件 + 溯源的统一本体）与"上传即解析"的自动化策展流程值得参照；远期 NFMD 若对外发布数据集，NOMAD 是与 Zenodo 并列的候选渠道。

#### 4.3.5 EMMO —— 借鉴思路（长期）

- **一手来源**：<https://github.com/emmo-repo/EMMO>（**CC-BY-4.0**，94 stars，最后 push 2026-09（当日仍有提交），极活跃）；官网 <https://emmo-repo.github.io/>。
- **是什么/价值**：欧洲材料建模理事会（EMMC）维护的形式材料本体，覆盖材料→性质→过程→尺度。NFMD 的 47 个 categories 目前是平铺字典（`categories.parent` 已预留层级），长期可向 EMMO 类做映射表（放 `plans/`，数据驱动，无 schema 改动），提高与欧洲材料数据生态的互操作性。现在动手收益低，仅记录方向。

#### 4.3.6 FAIR Principles —— 借鉴思路

- **一手来源**：<https://www.go-fair.org/fair-principles/>。
- **价值**：对照检查 NFMD：Findable（tsvector 全文检索 ✅，但缺数据集级 DOI 发布）、Accessible（REST API ✅ + RLS ✅）、Interoperable（OPTIMADE/EMMO 对齐为改进方向）、Reusable（MIT 仓库 ✅，literature 表 license 字段可补）。literature 表补 `license` 字段属 schema 变更（🟡）。

#### 4.3.7 传统材料数据库与 DFT 库 —— 借鉴/不适用

Materials Project（<https://materialsproject.org/>，**NFMD 已用作知识源**）、OQMD（<https://oqmd.org/>）、AFLOWlib（<https://aflowlib.org/>）：作为 NFMD 实验参数的**交叉验证参照系**（实验值 vs DFT 值分歧可作为 confidence 降级信号）。COD（<https://www.crystallography.net/>，CC0）中期可作晶体结构参考源；CSD/ICSD 商业授权，不引入。PubChem/ChEMBL/ZINC/ChemSpider/PDB 与核燃料域无关，不适用。

#### 4.3.8 云/边缘平台与区块链板块 —— 不适用

AWS/Azure/GCP/IBM Cloud/SageMaker 等云服务与 NFMD"单 PostgreSQL + Docker + RLS"的自托管架构相悖（ADR-0003 的单库单 URL 精神也不允许多套存储后端配置）。区块链板块（IPFS、Hyperledger Fabric、MatSwarm <https://pmc.ncbi.nlm.nih.gov/articles/PMC11519480/>、Makerchain — Leng et al. 2019, J. Cleaner Production）解决的分布式信任问题在 NFMD 单组织场景不存在；audit_log + review_audit_log 已是恰当规模的溯源。均不适用。

### 4.4 建模（下游：燃料性能程序输入 / ML 势函数与性质预测训练集）

#### 4.4.1 OpenKIM —— 借鉴思路

- **一手来源**：<https://openkim.org/>（ curated 势函数知识库，与 NIST Interatomic Potentials Repository 合作；kim-api 以 **LGPL-2.1-or-later** 许可，<https://github.com/openkim/kim-api>；许可政策 <https://openkim.org/kim-licensing/>）。
- **是什么/价值**：标准化"性质测试"（property tests）体系——任何势函数跑同一套测试得同一口径的弹性常数/热导率/缺陷形成能。对 NFMD 的意义是双向的：① NFMD 的实验参数可作为 OpenKIM 测试结果的**参照真值**参与势函数验证；② NFMD 可引用 OpenKIM 的测试命名法来给 categories 增补"可供势函数验证的属性"类别。不引入代码。

#### 4.4.2 MACE / CHGNet —— 不适用（记录为下游合作方向）

- **一手来源**：MACE <https://github.com/ACEsuit/mace>（**MIT**，1345 stars，最后 push 2026-09，极活跃）；CHGNet <https://github.com/CederGroupHub/chgnet>（**LBNL 修改版 BSD，含署名条款**（GitHub 无法自动识别），406 stars，最后 push 2026-02，活跃）。
- **是什么**：当前主流 ML 原子间势（MLIP）训练/推理框架（MACE 等变级别等变消息传递；CHGNet 电荷知情通用势）。核燃料氧化物（UO₂ 等）MLIP 是活跃方向。
- **对 NFMD 的价值**：NFMD 是数据供给方而非训练方——NFMD 文献参数可为 MLIP 提供实测参照（DFT 训练集外验证）。训练框架、GPU 栈与 3000+ 传递依赖显然不进 NFMD 仓库。结论：不适用（引入层面），在 README/路线图中记录为下游消费场景即可。

#### 4.4.3 CrabNet —— 中期可选（注意停更）

- **一手来源**：<https://github.com/anthony-wang/CrabNet>（**MIT**，132 stars，**最后 push 2023-04，实质停更**）；论文 Wang, A.Y.-T. et al., *CrabNet*, npj Comput Mater 2021。
- **是什么/价值**：仅凭化学成分预测材料性质 + attention 权重可视化（"这个性质主要由成分中哪个元素主导"）。与 NFMD 数据形状（material → parameter 值）天然契合，可作下游性质预测基线；注意力图还可反哺人工审核（发现可疑参数）。停更风险：若引入须版本冻结在 `uv.lock` 并预期无上游修复。

#### 4.4.4 scikit-learn 与可解释 AI（SHAP/LIME/Captum）—— 直接引入（建模侧）

- **一手来源**：scikit-learn <https://github.com/scikit-learn/scikit-learn>（BSD-3）；SHAP <https://github.com/shap/shap>（MIT）；LIME（BSD-2）；Captum <https://github.com/pytorch/captum>（BSD-3）。
- **价值**：NFMD 参数库规模（~17k 参数）下，成分→性质回归 + SHAP 归因是低成本高价值的首个下游用例，也为数据质量提供旁证（某类别参数若在模型中表现异常，常提示抽取错误）。**引入方式**：不进 etl 包；作为独立分析入口（如 `scripts/analysis/` 或 notebook + 独立 dependency-group），经 `NFMD_DB_URL` 只读连接（nfmd_reader 角色），遵守 ADR-0003/0004。

#### 4.4.5 Agentic 框架（MatAgent / MOFGen / MAPPS / MOFGPT）—— 借鉴思路

- **一手来源**：MatAgent <https://github.com/adibgpt/MatAgent>（**MIT**，25 stars，最后 push 2025-02，低活跃；OpenReview 论文 <https://openreview.net/forum?id=2Nm6Ef4tZD>）；MOFGen（CuspAI）<https://arxiv.org/abs/2504.14110>；MAPPS <https://arxiv.org/abs/2506.05616>；MOFGPT（CMU Barati Farimani 组，即本页面作者所在组）<https://pubs.acs.org/doi/10.1021/acs.jcim.5c01625>，代码 <https://github.com/srivathsanb14/MOFGPT>（**无 license 文件，默认版权保留，不可复用代码**）。
- **是什么/价值**：多 agent LLM 材料发现系统。对 NFMD 的启发是**工作流形态**而非代码：MatAgent 的"human-in-the-loop 审查环"与 NFMD `review_*` 审查表 + warn 级 ValidationIssue 人工复核是同一设计；"planner→extractor→validator" 分工对应 NFMD 五阶段。MOFGen/MAPPS/MOFGPT 面向 MOF 生成式设计，域不符，不适用。

#### 4.4.6 模拟软件（14 款）与量子板块 —— 不适用

LAMMPS（<https://github.com/lammps/lammps>，GPL-2.0，活跃）等开源模拟器、VASP/Gaussian/WIEN2k/Q-Chem（商业）、NAMD/AMBER/GAMESS/ORCA（学术免费但闭源）是未来燃料性能/原子尺度仿真的输入消费方，软件本身不进 NFMD。量子板块（Qiskit Nature 等，Apache-2.0 系）与 NFMD 当前目标无关。

---

## 5. 引入路线建议

### 短期（0–1 个月，零 schema 改动、零新依赖）

1. **ChatExtract 协议落进 extract 阶段**：将双通道抽取 + 自审计 prompt 模板固化到 llm-wiki 抽取流程；抽取一致性结果映射为 `confidence` 生成规则（双通道一致+自审通过→high，一致+存疑→medium，不一致→low/拒收）。产物仍是 ExtractedRecord，validate 全量规则不豁免。*与 ADR-0002/0003 无冲突（无依赖、无配置）；不触 DB 红线。*
2. **NEMAD/PIF 对标走查**：拿 NEMAD 条目 schema 与 PIF 条件树对照 `plans/schema_v2.sql` 的 parameters 表做一次 gap 走查，输出差距清单（如 uncertainty 结构化、条件组表达、来源链），为中期 schema 演进立项。*纯文档工作。*
3. **OpenRefine 辅助 alias map 策展**（一次性，人工操作）：聚类 `parameters.material_raw` 高频变体，回写 `plans/material-alias-map.json`。*不进依赖。*

### 中期（1–3 个月，新依赖均走 extras/独立 group + 可能的 schema 演进）

4. **pymatgen 进 extras，FormulaNormalizer 进 normalize**：`uv add --optional chem pymatgen`；`FormulaNormalizer` 以接口注入（ADR-0002），缺省降级 alias-map 路径；补 normalize 测试。风险：依赖树膨胀、ruff/CI 时长；规避：extras 隔离 + lazy import。
5. **抓取后备路径脚手架**：独立 `acquire` optional dependency-group + etl 包外独立入口；实现「URL 校验（仅 http/https、拒绝私有/保留地址、重定向复检）→ 域名 allowlist（进 Settings）→ 抓取 → 落盘到文献资料入口」的最小闭环；先接开放 API（Crossref/OpenAlex/Unpaywall），HTML 抓取（httpx + BS4）只对 allowlist 内无 API 的源启用。产物只是文献文件，仍走既有管线。*不触 DB 红线。*
6. **schema 演进立项**（如采纳走查结论）：uncertainty 结构化（numeric + 单位列）、provenance 来源链、literature 补 license/DOI 字段。**全部属 🟡 需人工批准项**：按 docs/database-safety-rules.md 执行（COUNT 先行、备份、`BEGIN…COMMIT` 包裹、报告影响行数），且新列一律可空以保 append-safe 兼容。
7. **scikit-learn + SHAP 建模侧试点**：独立 dependency-group + `scripts/analysis/`（etl 包外），只读 nfmd_reader 连接。产出"成分→热导率"基线与 SHAP 报告，反哺数据质量。
8. **OPTIMADE filter 语法评估**：评估 optimade-python-tools 挂 FastAPI 的成本；若做，API 层配置仍只读 `NFMD_DB_URL`（ADR-0003），不得新增第二套 DB 配置。
9. **（可选）CrabNet 基线**：版本冻结引入，仅限分析侧；预期无上游维护。

### 长期（3 个月+，方向性）

10. **EMMO categories 映射表**（`plans/` 下 JSON，数据驱动）；**Zenodo/NOMAD 数据集发布**（对标 NEMAD 的版本化发布）；**MaterialsBERT 核燃料 NER 试点**（license 与算力确认后）；**OpenKIM 参照值合作**。
11. 明确不做：云平台迁移、区块链、量子、商业 GUI 工具、MOF 生成式框架、模拟器引入。

### 与 ADR / DB 安全红线的关系速查

| 引入动作 | ADR-0002（依赖只接受不创建） | ADR-0003（单 DB URL） | ADR-0004（etl 包） | DB 红线 |
|---------|------|------|------|---------|
| ChatExtract prompt 协议 | ✅ 无依赖 | ✅ 无配置 | ✅ 仅改 extract 上游模板 | ✅ 不触库 |
| pymatgen extras | ⚠️ 须接口注入 + 可选化 | ✅ | ✅ 只在 normalize 内 | ✅ 不触库 |
| 抓取后备路径（httpx+BS4，acquire extras） | ⚠️ 独立 group + 独立入口，不进 etl | ⚠️ allowlist 走 Settings 单次读取 | ✅ etl 包外 | ✅ 只落盘文献文件，不触库 |
| scikit-learn/SHAP 分析脚本 | ⚠️ 独立 group，不进 etl | ⚠️ 复用 NFMD_DB_URL（reader） | ✅ etl 包外 | ✅ 只读 |
| schema 演进（provenance/uncertainty/license） | ✅ | ✅ | ✅ | 🔴→🟡 **须审批：备份+事务+行数报告** |
| OPTIMADE 层 | ⚠️ 新依赖走 extras | ⚠️ 不得引入第二套 DB 配置 | ✅ API 层 | ✅ 只读 |

---

## 6. 参考来源列表

**页面与其源论文**
- 资源页：<https://palarmi.github.io/ai-infrastructure-for-materials-discovery/>
- 配套论文：Salas, M. et al., *AI-powered open-source infrastructure for accelerating materials discovery and advanced manufacturing*, Communications Materials (2026): <https://www.nature.com/articles/s43246-026-01105-0>

**文献抽取类（§4.1）**
- ChatExtract：Polak et al., Nat Commun (2024) <https://pmc.ncbi.nlm.nih.gov/articles/PMC10882009/>；arXiv:2303.05352 <https://arxiv.org/abs/2303.05352>
- BatteryDataExtractor：<https://github.com/ShuHuang/batterydataextractor>；<https://pmc.ncbi.nlm.nih.gov/articles/PMC9627715/>；<https://batterydataextractor.readthedocs.io/>
- MaterialsBERT：<https://huggingface.co/pranav-s/MaterialsBERT>；Shetty et al., npj Comput Mater (2023)；MatSciBERT：<https://github.com/m3rg-iitd/matscibert>；MatBERT：<https://lbnlp.github.io>
- NEMAD：Itani et al., Nat Commun (2025) <https://www.nature.com/articles/s41467-025-64458-z>；arXiv:2409.15675 <https://arxiv.org/abs/2409.15675>
- Polymer Scholar：Gupta et al., Commun Mater (2024) <https://www.nature.com/articles/s43246-024-00708-9>；<https://polymerscholar.org/>

**网页抓取类（§4.1.6，2026-09-11 补充核实）**
- httpx：<https://github.com/encode/httpx>（BSD-3，活跃）
- Beautiful Soup：<https://www.crummy.com/software/BeautifulSoup/bs4/doc/>（MIT）
- Scrapy：<https://github.com/scrapy/scrapy>（BSD-3，活跃）；文档 <https://docs.scrapy.org/>
- MechanicalSoup：<https://github.com/MechanicalSoup/MechanicalSoup>（MIT，活跃）
- Playwright（Python）：<https://github.com/microsoft/playwright-python>（Apache-2.0，极活跃）
- Selenium：<https://github.com/SeleniumHQ/selenium>（Apache-2.0）
- Portia：<https://github.com/scrapinghub/portia>（BSD-3，仓库已归档）
- Puppeteer：<https://github.com/puppeteer/puppeteer>（Apache-2.0，Node.js）
- 开放 API：Crossref <https://api.crossref.org/>；OpenAlex <https://docs.openalex.org/>；Unpaywall <https://unpaywall.org/products/api>；Europe PMC <https://europepmc.org/RestfulWebService>；arXiv API <https://info.arxiv.org/help/api/>

**分析类（§4.2）**
- pymatgen：<https://github.com/materialsproject/pymatgen>（MIT）；<https://pymatgen.org/>
- matminer：<https://github.com/hackingmaterials/matminer>
- OpenRefine：<https://github.com/OpenRefine/OpenRefine>（BSD-3）
- AiiDA：<https://github.com/aiidateam/aiida-core>（MIT）；<https://www.aiida.net/>

**存储类（§4.3）**
- PIF/pypif：<https://github.com/CitrineInformatics/pypif>（Apache-2.0，已归档）；<https://citrineinformatics.github.io/pif-documentation/>
- OPTIMADE：<https://www.optimade.org/>；规范 <https://github.com/Materials-Consortia/OPTIMADE>（CC-BY-4.0）；实现 <https://github.com/Materials-Consortia/optimade-python-tools>
- MDCS：<https://github.com/usnistgov/MDCS>；NMRR：<https://materialsdata.nist.gov/>
- NOMAD：<https://nomad-lab.eu/>
- EMMO：<https://github.com/emmo-repo/EMMO>（CC-BY-4.0）
- FAIR：<https://www.go-fair.org/fair-principles/>
- Materials Project <https://materialsproject.org/>；OQMD <https://oqmd.org/>；AFLOWlib <https://aflowlib.org/>；COD <https://www.crystallography.net/>

**建模类（§4.4）**
- OpenKIM：<https://openkim.org/>；kim-api <https://github.com/openkim/kim-api>（LGPL-2.1+）；许可政策 <https://openkim.org/kim-licensing/>
- MACE：<https://github.com/ACEsuit/mace>（MIT）
- CHGNet：<https://github.com/CederGroupHub/chgnet>（LBNL 修改版 BSD）
- CrabNet：<https://github.com/anthony-wang/CrabNet>（MIT，停更）
- scikit-learn <https://github.com/scikit-learn/scikit-learn>；SHAP <https://github.com/shap/shap>；Captum <https://github.com/pytorch/captum>
- MatAgent：<https://github.com/adibgpt/MatAgent>（MIT）；<https://openreview.net/forum?id=2Nm6Ef4tZD>
- MOFGen：<https://arxiv.org/abs/2504.14110>；MAPPS：<https://arxiv.org/abs/2506.05616>；MOFGPT：<https://pubs.acs.org/doi/10.1021/acs.jcim.5c01625>；<https://github.com/srivathsanb14/MOFGPT>（无 license）
- MatSwarm：Wang et al., Nat Commun (2024) <https://pmc.ncbi.nlm.nih.gov/articles/PMC11519480/>；Makerchain：Leng et al., J. Cleaner Production (2019)
- LAMMPS：<https://github.com/lammps/lammps>（GPL-2.0）

**NFMD 内部参照**
- `CONTEXT.md`、`README.md`、`pyproject.toml`、`plans/schema_v2.sql`、`docs/adr/0001–0004`、`docs/database-safety-rules.md`（均在仓库内）

---

*报告完。本报告仅新增 `docs/research/ai-infrastructure-for-materials-discovery-survey.md` 一个文件，未改动仓库其他文件。*
