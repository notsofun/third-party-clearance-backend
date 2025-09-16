# 用户视角流程图（Roadmap）

```mermaid
flowchart TD
    U1([开始：进入系统])
    U2[上传OSS Readme/合规材料]
    U3[系统自动解析并分析风险]
    U4[展示待确认组件/许可证列表]
    U5{有高/中风险项需人工确认吗?}
    U6[用户与AI/系统对话确认]
    U7[全部确认完成]
    U8[系统自动筛选合规项]
    U9[生成合规报告/清单]
    U10{需要生成PCR文档吗?}
    U11[进入PCR智能对话]
    U12[多轮对话补全PCR内容]
    U13[生成/下载PCR文档]
    U14([结束])

    U1-->U2
    U2-->U3
    U3-->U4
    U4-->U5
    U5--是-->U6
    U6-->U7
    U5--否-->U7
    U7-->U8
    U8-->U9
    U9-->U10
    U10--是-->U11
    U10--否-->U14
    U11-->U12
    U12-->U13
    U13-->U14
```

## 用户旅程说明

1. 用户进入系统，上传OSS Readme或合规材料。
2. 系统自动解析、分析风险，展示待确认项。
3. 若有高/中风险项，用户需与AI/系统对话逐一确认。
4. 全部确认后，系统自动筛选合规项并生成合规报告/清单。
5. 若需要生成PCR文档，用户可进入PCR智能对话，系统引导多轮补全内容，最终生成/下载PCR文档。
6. 用户流程结束。
---
# 软件架构总览（Mermaid）

```mermaid
flowchart TD
    subgraph A["OSS合规分析流程 (PocketFlow)"]
        A1[文件上传/解析_ParsingOriginalHtml]
        A2[风险评估_LicenseReviewing]
        A3[特殊许可证收集_SpecialLicenseCollecting]
        A4[知识库校验_RiskCheckingRAG]
        A5[依赖分析_DependecyCheckingRAG]
        A6[初始化对话_initializeSession]
        A7[用户交互确认_GetUserConfirming]
        A8[合规筛选/报告_itemFiltering/getFinalOSS]
    end

    subgraph B["PCR智能生成流程 (StateHandlers)"]
        B1[ChatManager/ChatService]
        B2[StateHandlerFactory]
        B3[BaseHandler]
        B4[ObligationsHandler]
        B5[ContentHandler]
        B6[SpecialConsiderationHandler]
        B7[SubtaskHandlers]
        B8[PCR结构化生成]
    end

    subgraph C[AI/知识库]
        C1[LLM_Analyzer.py]
        C2[VectorDatabase]
    end

    subgraph D[前端]
        D1[文件上传/合规确认]
        D2[PCR对话页面]
        D3[报告下载]
    end

    D1--上传HTML-->A1
    A1-->A2-->A3-->A4-->A5-->A6-->A7
    A7--用户确认/对话-->D1
    A8--合规报告-->D3

    %% PCR部分
    D2--用户输入/上下文-->B1
    B1--状态切换/内容生成-->B2
    B2--分发到具体Handler-->B3 & B4 & B5 & B6 & B7
    B3--内容片段-->B8
    B4--合规义务-->B8
    B5--特殊说明-->B8
    B6--子任务处理-->B8
	B7--子任务处理-->B8
    B8--PCR结构化内容-->D3

    %% AI/知识库交互
    A7--合规确认结果-->B1
    B1--需要AI/知识库时-->C1
    B1--需要知识检索时-->C2
    C1--AI回复/内容生成-->B1
    C2--知识片段-->B1
```

---

## `chat_service`类的流程详细示意
该流程图以双层嵌套的状态管理器为例。
```mermaid
flowchart TD
    A[用户输入] --> B[Chat_Service.process_user_input]
    B --> C[get_strict_json解析用户意图]
    C --> D[获取当前状态Handler]
    D --> E{状态是否变化?}
    
    E -->|是| F[_process_status_change]
    E -->|否| G{Handler类型判断}
    
    F --> F1[更新processing_type]
    F --> F2[获取新状态指导语]
    F --> F3{需要嵌套项指导语?}
    F3 -->|是| F4[ChatManager.handle_item_action]
    F3 -->|否| F5[返回基础指导语]
    
    G -->|ChapterGeneration| H[_handle_chapter_generation]
    G -->|SubTaskStateHandler| I[_handle_nested_logic]
    G -->|ContentGenerationHandler| J[_handle_content_generation]
    G -->|其他| K[返回原始回复]
    
    H --> H1[构建Context上下文]
    H1 --> H2[ChapterGeneration.handle]
    H2 --> H3[初始化嵌套字典结构]
    H3 --> H4{是否已初始化?}
    H4 -->|否| H5[initialize_subtasks]
    H4 -->|是| H6[执行状态流转]
    
    H5 --> H5a[遍历item_list获取项目]
    H5a --> H5b[为每个项目创建子标题处理器列表]
    H5b --> H5c[nested_handlers字典初始化完成]
    H5c --> H6
    
    H6 --> H7[_state_transition]
    H7 --> H8{当前项目索引检查}
    H8 -->|超出范围| H9[返回COMPLETED]
    H8 -->|在范围内| H10[获取当前项目的子标题列表]
    
    H10 --> H11{查找未确认的子标题}
    H11 -->|找到| H12[标记content_confirmed=true]
    H11 -->|未找到| H13[检查当前项目是否全部完成]
    
    H12 --> H13
    H13 --> H14{所有子标题都已确认?}
    H14 -->|是| H15[current_item_index++]
    H14 -->|否| H16[返回IN_PROGRESS]
    
    H15 --> H17{所有项目都已完成?}
    H17 -->|是| H18[返回COMPLETED]
    H17 -->|否| H16
    
    H18 --> H19[_aggregate_content内容聚合]
    H19 --> H20[MarkdownDocumentBuilder构建]
    H20 --> H21[遍历所有项目和子标题]
    H21 --> H22[组合markdown格式内容]
    H22 --> H23[存储到shared字典]
    H23 --> H24[返回最终状态]
    
    H16 --> H25[_content_generation内容生成]
    H25 --> H26[获取当前项目信息]
    H26 --> H27[查找当前需要处理的子标题]
    H27 --> H28{找到未处理的子标题?}
    H28 -->|是| H29[调用子标题内容生成器]
    H28 -->|否| H30[当前项目所有子标题已完成]
    
    H29 --> H31[生成具体内容]
    H31 --> H32[存储到shared字典]
    H32 --> H33[返回生成的内容]
    
    H33 --> H34{ChapterGeneration结果检查}
    H34 -->|COMPLETED| H35[重新检查大状态转换]
    H34 -->|IN_PROGRESS| H36[获取当前指导语]
    
    H35 --> H37{状态是否变化?}
    H37 -->|是| H38[处理状态变化]
    H37 -->|否| H39[返回完成消息]
    
    H36 --> H40{是否有新生成内容?}
    H40 -->|是| H41[显示生成内容+指导语]
    H40 -->|否| H42{用户输入是继续指令?}
    H42 -->|是| H43[显示进度信息+指导语]
    H42 -->|否| H44[返回当前指导语]
    
    style A fill:#e1f5fe
    style H fill:#fff3e0
    style H2 fill:#fff3e0
    style H5 fill:#fff3e0
    style H7 fill:#fff3e0
    style H19 fill:#fff3e0
    style H25 fill:#fff3e0
    style I fill:#f3e5f5
    style J fill:#e8f5e8

```
---

## 架构分层与交互详细说明

### 1. OSS合规分析主流程（PocketFlow）
- 负责自动化解析、风险评估、依赖分析、用户交互确认、合规筛选和报告生成。
- 每个Node负责一个环节，数据通过shared字典流转。
- 用户交互节点（GetUserConfirming）可与AI对话，确认高/中风险项。
- 该流程的输出（合规清单、用户确认结果）可作为PCR生成的输入。

### 2. PCR智能生成流程（StateHandlers）
- 由ChatManager/ChatService统一管理会话和上下文。
- StateHandlerFactory根据当前状态和用户输入，分发到不同的Handler（如ObligationsHandler、ContentHandler等）。
- 每个Handler负责生成/补全PCR文档的某一部分内容，支持多轮追问、确认。
- 支持AI内容生成、知识库检索、子任务分解等。
- 最终由PCR结构化生成模块汇总所有片段，输出完整的PCR文档。

### 3. AI与知识库
- LLM_Analyzer.py统一AI调用入口，支持风险评估、内容生成、合规建议等。
- VectorDatabase为RAG和内容检索提供知识增强。
- 两大流程均可调用AI/知识库，提升自动化和智能化水平。

### 4. 前端
- 合规分析页面：文件上传、风险展示、合规确认。
- PCR生成页面：多轮对话，逐步完善PCR内容，支持保存/下载。
- 报告下载页面：统一展示合规报告和PCR文档。

---

## 两大流程的边界与衔接

- **PocketFlow主流程** 负责自动化与交互式的OSS合规分析，生成合规清单和报告。
- **StateHandlers流程** 负责根据用户输入和AI能力，驱动多轮对话，逐步生成结构化PCR文档。
- 两部分通过shared/session等机制可无缝衔接，既支持自动化，也支持灵活的人工/AI协作。
- 合规分析的结果（如高风险组件、用户确认内容）可作为PCR生成的输入，驱动后续多轮内容补全。