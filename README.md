# 合规性风险评估系统（Compliance Risk Assessment System）

本项目基于大型语言模型（LLM）与向量检索技术，结合人工确认环节，实现软件依赖包的合规性风险自动分析与智能评估。核心由LangChain框架驱动，调用Azure OpenAI完成文本分析，结合PocketFlow实现任务节点编排，最终生成结构化合规报告。

---

## 项目背景与目标

随着软件依赖包的数量和复杂度激增，传统人工审核流程效率低、误判率高。本系统旨在：

- 利用LLM自动理解依赖包文本内容及许可协议
- 结合向量数据库实现历史案例快速检索
- 通过多阶段状态机管理合规评估流程（OEM、依赖、合规等）
- 结合人工确认节点保证结果准确可靠
- 最终生成可供法律与开发团队参考的合规报告

---

## 系统架构

```mermaid
flowchart TD
    A[用户上传依赖包清单] --> B[LLM分析模块<br>（LangChain + Azure OpenAI）]
    B --> C[向量数据库检索历史分析]
    C -->|无匹配或需更新| D[风险评估节点<br>（LLM + Prompt模板）]
    C -->|匹配命中| E[返回历史分析结果]
    D --> F[人工确认环节]
    E --> F
    F --> G[报告生成节点]
    G --> H[输出合规性报告]
    
    subgraph 流程编排引擎
    B
    C
    D
    F
    G
    end
````

* **LLM分析模块**：负责解析依赖包及许可文本，调用Azure OpenAI生成语义向量及初步分析。
* **向量数据库**：存储历史分析结果，提升复用效率。
* **风险评估节点**：对未命中或需更新的条目，重新调用LLM做合规风险评估。
* **人工确认环节**：基于状态机（OEM、依赖、合规、合同等）引导人工逐步确认。
* **报告生成节点**：整合所有确认结果，自动生成结构化合规报告。

---

## 核心模块设计

### 状态机设计

* 采用抽象基类`StateHandler`定义状态处理器接口
* 定义具体状态处理器：`SpecialCheckHandler`, `OEMHandler`, `DependencyHandler`, `ComplianceHandler`
* `WorkflowContext`负责状态管理和转移
* 状态枚举由`ConfirmationStatus`定义，包含`SPECIAL_CHECK`, `OEM`, `DEPENDENCY`, `COMPLIANCE`, `CONTRACT`

状态转换示意：

```text
SPECIAL_CHECK → OEM → DEPENDENCY → COMPLIANCE → CONTRACT → 结束
```

### 后端聊天服务

* `ChatService`负责接收用户输入，调用对应状态处理器处理消息
* 通过`WorkflowContext`维护会话状态和状态转移
* 使用FastAPI实现接口，提供文件上传分析接口和聊天交互接口
* 支持多组件依次确认，管理多轮对话上下文

---

## 快速开始

### 环境依赖

* Python 3.9+
* FastAPI
* uvicorn
* LangChain
* Azure OpenAI SDK
* PocketFlow（流程编排）

```bash
pip install -r requirements.txt
```

### 启动服务

```bash
uvicorn back_end.server:app --reload --host 127.0.0.1 --port 8000
```

### 使用流程

1. **上传依赖文件**

```bash
curl -X POST "http://127.0.0.1:8000/analyze" -F "file=@yourfile.html"
```

返回 `session_id` 和初始确认组件信息。

2. **发起聊天确认**

```bash
curl -X POST "http://127.0.0.1:8000/chat/{session_id}" -H "Content-Type: application/json" -d '{"message":"用户输入内容"}'
```

服务器返回当前确认状态和系统回复。

3. **查询会话状态**

```bash
curl -X GET "http://127.0.0.1:8000/sessions/{session_id}"
```

---

## 开发指南

* 关键逻辑位于 `back_end/services/chat_service.py` 与 `back_end/services/chat_flow.py`
* `WorkflowContext` 实现状态转移，易于扩展更多状态
* FastAPI 服务器入口在 `back_end/server.py`
* 日志采用标准 logging，级别可调节方便调试

---

## 未来优化方向

* 增加更多智能异常检测与预警策略
* 扩展多语言支持，覆盖更多许可协议语境
* 深度集成知识图谱，提升推理能力
* 接入更丰富的人机交互接口，实现多渠道合规审核
