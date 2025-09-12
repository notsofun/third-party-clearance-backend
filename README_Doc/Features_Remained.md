# 现状
下文将分OSS Readme文档和PCR文件两个部分描述本系统的进展以及后续的功能扩展计划。

## OSS Readme
目前已经实现了，`上传*LicenseInfo*文件` -> `Chatbot确认相关事宜` -> `生成最终OSS Readme的Docx文件` 的操作流程。
生成示例如下：[OSS Readme](downloads\c1bd08a4-bc7c-4a0f-b8fa-b7a1412cf252\Final_OSS_Readme.docx)

---
还需扩展的功能如下：
- 按照自研项目格式修改目前的OSS Readme文件的拼接方法
- Chatbot的确认流程中需要新增一个`FinalList`节点供用户确认最终确认好的组件及对应许可证
- 无需用户确认商业组件，在`CliXML`文件中解析结果确认为商业组件后，将导致其为商业组件的许可证从该组件的许可证列表中去除

暂未解决的bug如下：
- `chat_flow` 未处理用户说自己不需要确认商业授权时，跳转到下一个
- `chat_flow` 选择非`OSS`类为起始节点时，将无法进入到下一个环节

## PCR
目前已经实现了基于上一步解析生成的OSS Readme文件自动化生成PCR文件，暂时以Markdown语言储存。
生成示例如下：[PCR](downloads\test\product_clearance\1th_report.md)

---
还需扩展的功能如下：
- 封面还需要一个表格，用来记录开发人员等信息
- 使用`Spire.Doc`库转换Markdown文件为Docx格式时，需要加上目录

暂未解决的bug如下：
- 模型理解用户意图的能力较弱，有时无法区分是`next`还是`continue`，导致状态流转故障
- **Obligations resulting from 3rd party components**章节，按照组件为单位的子标题还未处理好
- 模型在判断组件名和CliXML文件名的相关性上能力较弱
- **Component Overview**章节缺失标题，同时还需要加上一句描述性的句子
  - 同时，还缺少一列作为序号
- **Product Overview**的生成格式需要约束好，目前会擅作主张生成一个`Key Features`的子标题，内容不符合标准