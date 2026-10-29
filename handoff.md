# Handoff — 金融 Skills 仓库安全加固

更新时间：2026-10-29

## 目标

在 `dreak7/claude-for-financial-services-cn` Fork 中分阶段修复 TLS、SSE 暴露、跨 Agent 提示注入、输入校验、并发竞争、异常信息泄露及依赖/持续扫描问题。用户已明确要求：**MCP v2 迁移暂停，尚未开始。**

## 已完成并推送的工作

| 提交 | 内容 |
|---|---|
| `641d8a4` | iFind 恢复 TLS 证书链和主机名校验，两处请求 `verify=True`，新增 TLS 回归测试 |
| `2b940b5` | 四个 MCP 默认 SSE 仅监听 `127.0.0.1`；非本机监听强制 `MCP_AUTH_TOKEN`；Bearer 中间件和部署文档 |
| `de1ea1a` | Handoff 必须人工输入 `yes`，非交互 fail-closed；修复嵌套 JSON 解析 |
| `99197c2` | AkShare/News 输入边界与异常脱敏；iFind 请求 ID、会话初始化并发和协议顺序修复 |
| `f8d4e0a` | 跨平台哈希依赖锁定、pip-audit、detect-secrets 基线、GitHub Actions 安全流水线 |
| `28cd45d` | 股票/基金/指数代码、Wind/iFind 结构化参数与契约校验；正向和反向测试 |

清理了复核过程中产生的 11 个 0 字节垃圾文件，未进入提交。

## 已验证事实

- 全套单元/安全回归：**27 tests OK**。
- 真实 FastMCP **v1.30.0** 端到端：四个服务均验证无 Token 返回 401，有 Token 可完成 MCP 初始化和一次工具调用。
- `pip-audit -r requirements.txt`：**No known vulnerabilities found**。
- `detect-secrets-hook`：无新增未审核发现；基线中的两项已人工核对为占位符/Agent ID。
- 最新参数校验提交 CI：[run 40872215331](https://github.com/dreak7/claude-for-financial-services-cn/actions/runs/40872215331)，**conclusion=success**。
- 依赖锁定 CI：[run 40854638916](https://github.com/dreak7/claude-for-financial-services-cn/actions/runs/40854638916)，**conclusion=success**。
- 每次主要改造均做独立复核；发现的 TLS 测试边界、ASGI lifespan、iFind 初始化竞态、Windows/Linux 锁定差异、pip hash 模式冲突、Wind 契约误伤/绕过均已修复并复测。

## 重要决策

- 保持 FastMCP v1，当前锁定 `mcp==1.30.0`；**MCP v2 迁移暂停**。
- SSE 使用共享 ASGI Bearer 中间件；远程部署仍要求 HTTPS 反向代理和防火墙。
- Handoff 采用逐次人工确认，而非继续允许模型文本自动 steer；生产环境仍建议可信结构化事件。
- 直接依赖维护在 `requirements.in`，用以下命令生成跨平台锁定文件：
  ```bash
  uv pip compile requirements.in --generate-hashes --universal --output-file requirements.txt
  ```
- Wind 参数以 `mcp-servers/wind-mcp/references/tool-contracts.md` 为准，包括完整 period 枚举、单个名称/代码、`aftime` 仅 `0/1`。

## 路径与常用命令

本地仓库：
`C:/Users/Timber/AppData/Local/hermes/profiles/forge/workspace/claude-for-financial-services-cn`

```bash
uv run --with-requirements requirements.txt python -m unittest discover -s tests -v
uvx pip-audit -r requirements.txt
uvx --from detect-secrets detect-secrets-hook --baseline .secrets.baseline $(git ls-files)
```

## 遗留问题 / 未验证范围

- **MCP v2 迁移未开始，保持暂停。**恢复时需重新核对 MCPServer、工具注册、stdio/SSE 启动和 Bearer ASGI 接法，并做真实 v2 端到端测试。
- 未使用真实 Wind/iFind 付费凭据联调上游协议与数据；当前上游行为由 mock/本地协议测试覆盖。
- 人工 Handoff 能阻断自动注入，但不能防止操作员被诱导误批准。
- 外部新闻/公告/研报的自然语言信任边界仍依赖宿主模型与权限隔离，不能宣称完全消除提示注入。
- `scripts/check-china.py` 在本机仍报告 20 个既有 Skills drift 和 2 个缺失本地密钥配置；这些不是本轮引入的问题，未纳入安全 CI。
- 未发现真实硬编码密钥不等于依赖、部署或运行时绝对安全。

## 后续步骤

1. 等用户明确恢复 MCP v2 迁移后，再单独立项实施。
2. 若投入生产，先用受控账号完成 Wind/iFind 真实联调和 HTTPS 反向代理验收。
3. 后续新增结构化工具参数时同步更新 `mcp-servers/validation.py` 和回归测试。
