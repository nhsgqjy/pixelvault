# 统一 API 客户端

PixelVault 前端的所有 API 请求统一经过 `packages/api-client`。客户端负责
API 地址拼接、查询参数编码、Cookie 凭据、公共请求头、JSON 序列化、响应解析
以及 `ApiError` 错误对象。

`frontend/src/lib/api.ts` 是应用适配层：读取 `VITE_API_BASE_URL`，追加
`/api`，并创建浏览器端唯一客户端。业务模块只从该适配层导入 `api`，不直接
读取环境变量。

JSON 接口使用 `api.get`、`post`、`patch`、`put` 或 `delete`。需要自行判断
`response.ok`、读取 Blob，或保留上传重试流程时使用 `api.raw`。在 `<img>` 等
DOM 属性中需要完整资源地址时使用 `api.url`。

在仓库根目录执行客户端专项测试：

```powershell
cd packages\api-client
npm test
```

随后验证前端消费端：

```powershell
cd frontend
pnpm build
```

本阶段只调整前端请求边界。PostgreSQL 持久化和对象存储属于后续独立阶段，
此处尚未实现。
