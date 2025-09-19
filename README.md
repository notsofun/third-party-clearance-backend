# Siemens Third-Party Clearance 项目设计文档

## 1. 项目目标

本项目旨在实现对第三方开源组件（OSS）合规性自动化分析、风险评估、用户交互确认及报告生成。支持上传 OSS 相关 HTML 文件，自动解析、风险分析、依赖分析、用户交互确认，并最终生成合规报告。前后端分离，支持 Web 聊天交互。

---

## 2. 总体架构

详细架构图及流程图请参照该文档: [架构图+流程图](README_Doc\Architecture_Workflow.md)

- **前端**：React + TypeScript，负责文件上传、组件风险展示、与后端对话交互。
- **后端**：FastAPI（Python），负责文件接收、PocketFlow 工作流调度、对话管理、报告生成。
- **核心流程**：PocketFlow 流程引擎，节点式编排各类自动化与交互任务。
- **AI能力**：集成 Azure OpenAI/LLM，自动化风险评估、合规建议、对话交互。
- **数据存储**：本地 JSON 文件存储中间结果，支持后续扩展数据库。

---

## 3. 主要模块说明

### 3.1 后端目录结构

```
third-party-clearance/
│
├─ back_end/
│   ├─ run_server.py / server.py      # FastAPI 服务入口
│   ├─ services/                      # 聊天/流程服务
│   ├─ items_utils/                   # 组件类型与工具
│   ├─ test_codes/                    # 测试代码
│   └─ uploads/                       # 上传文件存储
│
├─ utils/
│   ├─ LLM_Analyzer.py                # LLM/AI相关分析与对话
│   ├─ tools.py                       # 通用工具
│   ├─ htmlParsing.py                 # HTML解析
│   ├─ itemFilter.py                  # 组件/许可证筛选
│   ├─ database/                      # 各类DB工具
│   └─ PCR_Generation/                # PCR报告相关
│
├─ nodes.py                           # PocketFlow节点定义
├─ flow.py                            # PocketFlow流程编排
├─ main.py                            # 流程运行入口
└─ ...
```

### 3.2 核心流程（PocketFlow）

- **pre_chat_flow**：文件解析、风险分析、依赖分析、初始化会话
- **chat_flow**：与用户交互确认高/中风险组件
- **post_chat_flow**：根据用户确认结果生成最终合规报告

#### 主要节点（nodes.py）

- `ParsingOriginalHtml`：解析上传的 HTML，提取组件、许可证等结构化信息
- `LicenseReviewing`：自动化评估每个许可证的风险等级
- `SpecialLicenseCollecting`：收集特殊类型许可证（如GPL等）
- `RiskCheckingRAG`：结合知识库/向量DB进一步校验风险
- `DependencyCheckingRAG`：分析组件间依赖关系
- `initializeSession`：初始化对话机器人
- `GetUserConfirming`：与用户交互确认高/中风险项
- `itemFiltering`：根据用户确认结果筛选最终合规项
- `getFinalOSS`：生成最终合规报告HTML

### 3.3 AI与知识库

- `LLM_Analyzer.py`：封装了与 Azure OpenAI 的对接，支持风险评估、合规建议、对话交互等。
- `database/vectorDB.py`：向量数据库，用于知识检索和RAG增强。

### 3.4 服务层（back_end/services）

- `chat_service.py`：对话服务，管理会话状态、与前端交互
- `chat_flow.py`：对话流程管理
- `chat_manager.py`：多会话管理
- `state_handlers/`：对话状态机与多种对话场景处理

---

## 4. 数据流与交互流程

1. **文件上传**（前端 -> /analyze）
	- FastAPI 保存文件，调用 pre_chat_flow，完成自动化解析与风险分析，返回 session_id 和待确认组件列表。

2. **用户交互**（前端 -> /chat/{session_id}）
	- 前端逐步与后端对话，确认每个高/中风险组件，后端通过 chat_flow 管理对话状态。

3. **报告生成**（后端自动或前端触发）
	- 用户全部确认后，后端调用 post_chat_flow，生成最终合规报告，前端可下载或查看。

---

## 5. 扩展性与可维护性

- **节点式编排**：所有自动化与交互逻辑都以节点形式实现，易于插拔、扩展和单元测试。
- **多流程分离**：解析/分析、交互、报告生成分为独立流程，便于维护和复用。
- **AI能力可插拔**：LLM相关能力集中在 utils/LLM_Analyzer.py，便于更换模型或API。
- **前后端解耦**：API接口清晰，前端可独立开发和升级。
- **会话与状态管理**：支持多用户并发、会话持久化，便于后续扩展为多租户SaaS。

---

## 6. 典型用例

1. 用户上传 OSS HTML 文件
2. 系统自动解析、风险分析、依赖分析
3. 前端展示待确认组件，用户逐一确认
4. 系统根据用户确认结果生成合规报告
5. 用户下载或查看报告

---

## 7. 如何开始？
*以目前的开发进度（截至2025年9月16日）*

1. 首先安装依赖项

```powershell
pip install -r requirements.txt
```

2. 在 `back_end` 目录下运行：

```powershell
python run_server.py
```

3. 在`front_end`目录下安装`Node`包

```powershell
npm install
```

4. 运行前端

```powershell
npm run dev
```

5. 在前端页面中与**Chatbot**对话，以生成`ReadmeOSS.docx`文档，在对话框中下载
   1. LicenseInfo文件上传需要以`.html`格式
   
6. 对于PCR文件，目前仅支持通过测试文件生成，在`/back_end/test_codes/testing.py`中，修改

在命令行中作为参数传进去

```python
def class_context(request):
    """创建类级别的context，在整个测试类中共享"""
    shared = {
        'html_path': r"C:\Users\z0054unn\Downloads\LicenseInfo-Wireless Room Sensor-2.0-2025-08-22_01_44_49.html",
        'PCR_Path': r'uploads\test\ProjectClearingReport-Wireless Room Sensor-2.0-2025-08-28_03_14_37.docx',
    }
```

7. 构建数据库
将预备检查的`LicenseInfo`列表中的组件对应的`CLIXML`文件统一下载到`data/`文件夹中，并运行`utils/database/buildDB.py`文件

---

## 8. 关键技术点

- **PocketFlow**：轻量级节点式流程引擎，支持灵活的流程编排
- **LangChain/Azure OpenAI**：自动化风险评估、合规建议、对话交互
- **向量数据库**：知识增强与RAG
- **FastAPI**：高性能API服务，易于前后端分离
- **React**：现代化前端，支持文件上传、聊天、进度展示

---

## 9. 未来可扩展方向

- 支持更多文件格式（如 docx、pdf）
- 支持多语言和国际化
- 支持多种 LLM/AI 服务切换
- 支持更细粒度的权限与多用户协作
- 支持云端部署与大规模并发

## 10.开发指南
请参照此[指南](README_Doc\Tutorial.md)