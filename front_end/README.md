# Third Party Clearance Frontend

这是一个基于 React 和 Vite 的前端项目，旨在提供一个高效、现代的开发环境，适用于第三方授权管理系统。

## 项目结构

* `src/`: 源代码目录，包含组件、页面和路由逻辑。
* `public/`: 静态资源目录，存放 HTML 模板和公共文件。
* `vite.config.ts`: Vite 配置文件，用于构建和开发设置。
* `package.json`: 项目依赖和脚本配置。
* `tsconfig.json`: TypeScript 配置文件。
* `eslint.config.js`: ESLint 配置文件，确保代码质量。

## 开发环境搭建

### 1. 克隆仓库

```bash
git clone https://github.com/notsofun/third-party-clearance-frontend.git
cd third-party-clearance-frontend
```



### 2. 安装依赖

```bash
npm install
```



### 3. 启动开发服务器

```bash
npm run dev
```



开发服务器默认运行在 [http://localhost:3000](http://localhost:3000)。

## 构建生产版本

```bash
npm run build
```



构建后的文件将输出到 `dist/` 目录，可部署到生产环境。

## 代码质量与格式

* **ESLint**：用于检查和修复 JavaScript/TypeScript 代码中的问题。
* **Prettier**：用于格式化代码，确保代码风格一致。
* **TypeScript**：提供静态类型检查，提升代码可维护性。

## 贡献指南

欢迎提交 Pull Request！在提交之前，请确保：

* 遵循项目的代码风格。
* 添加或更新相关的单元测试。
* 在提交信息中清晰描述更改内容。

## 许可证

本项目采用 MIT 许可证，详情请参阅 [LICENSE](./LICENSE)。
