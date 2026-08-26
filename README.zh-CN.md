# PixelVault

[English](README.md) | 简体中文

基于 React、TypeScript、FastAPI 和 SQLite 构建的自托管个人照片管理系统。

![PixelVault 桌面端照片库](docs/portfolio/assets/pixelvault-desktop.png)

## 功能

- 支持自动重试的并发断点续传
- 相册、收藏、标签、时间线、搜索和批量整理
- 响应式照片库、原图预览和幻灯片播放
- 可设置有效期的照片与相册分享链接
- 重复照片检测、回收站和恢复
- 备份、恢复和存储完整性维护
- 后台缩略图生成与 EXIF 信息处理

## 环境要求

- 推荐使用 Docker 和 Docker Compose 一键启动；或者
- 本地开发需要 Python 3.12+、Node.js 22+ 和 pnpm

## 使用 Docker 运行（推荐）

```bash
copy .env.example .env
docker compose up --build
```

- Web 页面：http://localhost:8080
- 健康检查：http://localhost:8080/api/health
- 部署、HTTPS、备份和回滚说明：`docs/production-deployment.md`

启动应用前，请修改 `.env` 中的 `PIXELVAULT_PASSWORD`。Docker 镜像会构建
前端并将其与 API 一起提供服务，因此不需要本地存在 `node_modules/` 或
`dist/` 目录。

## 不使用 Docker 在本地运行

在仓库根目录通过 PowerShell 启动后端：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
$env:PIXELVAULT_PASSWORD = "replace-with-a-long-random-password"
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

打开第二个终端，安装并启动前端：

```powershell
cd frontend
corepack enable
pnpm install --frozen-lockfile
pnpm dev
```

- 前端开发服务器：http://localhost:5173
- 后端健康检查：http://localhost:8000/api/health
- Vite 会将 `/api` 请求代理到本地后端的 8000 端口。

## 前端依赖与构建产物

仓库只提交源代码和可复现的依赖信息，不提交下载的依赖包或生成的构建产物：

- `frontend/package.json` 定义前端依赖和脚本。
- `frontend/pnpm-lock.yaml` 锁定实际解析的依赖版本。
- `frontend/node_modules/` 保存 pnpm 安装的依赖。Git 会忽略此目录，可通过
  `pnpm install --frozen-lockfile` 重新生成。
- `frontend/dist/` 保存 Vite 生成的生产环境 HTML、CSS 和 JavaScript。Git
  会忽略此目录，可通过 `pnpm build` 重新生成。

执行以下命令生成并检查前端生产构建：

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm build
```

生成的文件位于 `frontend/dist/`。生产环境应根据仓库中的源代码和锁文件构建，
而不是依赖开发者电脑上的本地构建目录。

## 前端结构

- `src/main.tsx`：会话初始化，以及公共页面和登录后页面的路由选择。
- `src/pages`：登录页、匿名分享页和登录后的照片库页面组合。
- `src/components/layout`：桌面端和移动端导航、照片库页头。
- `src/components/library`：筛选器、集合视图、批量操作、照片卡片、详情和确认弹窗。
- `src/components`：独立的备份、完整性检查、重复照片、数据概览和上传面板。
- `src/hooks/usePhotoLibrary.ts`：筛选查询、分页和处理状态轮询。
- `src/hooks/useAlbums.ts`：相册集合加载。
- `src/hooks/useChunkedUpload.ts`：可恢复并发上传状态机。
- `src/hooks/useVaultActions.ts`：需要身份验证的修改、分享和导出操作。
- `src/lib` 和 `src/types.ts`：共享配置、工具函数和领域类型。
