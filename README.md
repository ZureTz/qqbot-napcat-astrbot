# NapCat + AstrBot QQ 机器人模板

用 Docker Compose 部署 NapCat 和 AstrBot，包含连接配置初始化、持久化数据目录和一个可直接扩展的 AstrBot 插件。

```text
QQ ⇄ NapCat ── OneBot v11 / 反向 WebSocket ── AstrBot ⇄ 模型服务
                                                └── 本地插件
```

## 快速开始

需要 Python 3.10+、Docker Engine 或 Docker Desktop / OrbStack，以及 Docker Compose。支持 macOS 和 Linux；Windows 可在 WSL2 中使用。镜像支持 Linux amd64/arm64，Apple Silicon 无需强制指定 amd64。

```bash
git clone https://github.com/ZureTz/qqbot-napcat-astrbot.git
cd qqbot-napcat-astrbot
python3 scripts/init.py
docker compose up -d
```

初始化会创建 `.env` 和 `data/`，生成三个独立的随机凭据，并将相同的 OneBot 令牌写入两端配置。重复运行会保留已有凭据和配置。不要先复制 `.env.example`：直接运行初始化脚本即可。

### 1. 登录 QQ

打开 [NapCat WebUI](http://127.0.0.1:6099/webui)，使用本地 `.env` 中的 `NAPCAT_WEBUI_TOKEN` 登录，再用手机 QQ 扫码登录机器人账号。

NapCat 首次登录会从 `data/napcat/config/onebot11.json` 创建账号专属的 `onebot11_<QQ号>.json`。已预设反向 WebSocket 地址 `ws://astrbot:6199/ws`，无需手动创建网络连接。

### 2. 配置 AstrBot

打开 [AstrBot WebUI](http://127.0.0.1:6185)，用户名是 `astrbot`，初始密码在 `.env` 的 `ASTRBOT_DASHBOARD_INITIAL_PASSWORD`。首次登录按页面提示修改密码。

在「机器人」中确认已有启用的 `qq` / OneBot v11 连接。模板参数如下：

| 配置 | 值 |
| --- | --- |
| ID | `qq` |
| 主机 | `0.0.0.0` |
| 端口 | `6199` |
| Token | 初始化脚本已自动写入，与 NapCat 相同 |

在 AstrBot 设置中填写你自己的管理员 QQ 号，并配置允许使用的会话白名单。可以用 `/sid` 获取会话 ID，例如 `qq:GroupMessage:群号`。上游对白名单为空的处理是“不启用限制”，因此请在加入实际使用的群之前填写名单。

### 3. 验证收发，再接入 AI

在 QQ 私聊或群内向机器人发送 `/ping`，应收到 `pong · NapCat + AstrBot 消息链路正常`。若设置了唤醒规则，可先 @ 机器人再发送指令。也可以发送 `/bot_info`。

这两个指令不需要大模型 API Key。确认消息链路可用后，再到 AstrBot 的模型服务配置中填写供应商、API 地址、API Key 和模型，并选择默认聊天模型。人设、上下文和知识库也在面板中配置。

## 目录结构

```text
compose.yaml                         # 两个服务及共享媒体目录
.env.example                         # 无真实凭据的配置示例
config/                              # 首次初始化用的 JSON 模板
scripts/init.py                      # 只使用 Python 标准库
plugins/astrbot_plugin_starter/       # 可提交到 Git 的插件源码
data/astrbot/                        # AstrBot 配置、数据库和运行数据（忽略）
data/napcat/config/                  # NapCat 配置（忽略）
data/napcat/qq/                      # QQ 登录会话（忽略）
.github/workflows/check.yml          # Compose 和 Python 语法检查
```

## 开发插件

编辑 `plugins/astrbot_plugin_starter/main.py`。该目录单独挂载到 `/AstrBot/data/plugins/astrbot_plugin_starter`，容器可直接读取本地代码。修改后在 AstrBot 面板重载插件，或执行：

```bash
docker compose restart astrbot
```

插件目录为只读挂载。插件运行数据应使用 AstrBot 提供的数据目录，不要写回源码目录；内置示例没有额外 Python 依赖。如果增加新的本地插件，请在 Compose 中添加对应的目录挂载。通过面板安装的其他插件保存在 `data/astrbot/plugins/`。

仓库根目录是部署项目，不能作为单个插件直接安装到 AstrBot 插件市场。

## 常用命令

```bash
make check                      # 无需启动 Docker 引擎的静态检查
make up                         # 初始化并启动
make status                     # 查看容器状态
make logs                       # 查看日志；可能含登录信息，不要公开上传
make down                       # 停止服务，保留持久化数据
docker compose restart astrbot # 重载应用
```

没有 `make` 时可直接运行对应的 `python3 scripts/init.py` 和 `docker compose` 命令。

## 配置与升级

- AstrBot 固定为 `soulter/astrbot:v4.28.2`；NapCat 默认使用 `mlikiowa/napcat-docker:latest`。NapCat 为滚动标签，需要固定环境时可在 `.env` 中改用已验证的镜像 digest。
- 两个管理端口只绑定本机 `127.0.0.1`。OneBot 6199 仅用于容器间通信，不映射到宿主机。服务器部署可通过 SSH 转发访问面板：`ssh -L 6185:127.0.0.1:6185 -L 6099:127.0.0.1:6099 user@server`。
- `.env` 中的 OneBot 令牌仅用于首次生成配置。修改它不会覆盖已经运行过的配置；轮换时要同步修改 AstrBot 的 Token 和 NapCat 当前账号的 Token。NapCat WebUI Token 和 AstrBot 初始密码也只在首次初始化时生效，后续在各自面板中修改。
- 模板 JSON 的修改仅影响新的初始化。现有实例请在 WebUI 中配置，或停机后编辑 `data/` 下的实际文件。
- 两个容器共享 `/AstrBot/data`，用于图片、音频等本地媒体路径；不要去掉 NapCat 中这一挂载。

升级前先停止容器，备份 `.env` 和整个 `data/` 目录，再修改镜像版本并启动：

```bash
docker compose down
mkdir -p backups
tar -czf "backups/qqbot-$(date +%Y%m%d-%H%M%S).tgz" .env data
# 如需更新 AstrBot，先编辑 .env 中的 ASTRBOT_IMAGE。
docker compose pull
docker compose up -d
```

备份包含 QQ 登录态、密钥和聊天数据，保存在本地；`.env`、`data/` 和 `backups/` 均已加入 `.gitignore`。`.env` 丢失但 `data/` 已有内容时，初始化脚本会停止，避免生成不匹配的新令牌。

## 排错

- `cannot connect to the Docker daemon`：先启动 Docker Desktop / OrbStack / Docker Engine。
- NapCat 连接失败：确认 AstrBot 机器人已启用，地址为 `ws://astrbot:6199/ws`，两端 Token 一致。容器内的 `localhost` 不是另一个服务。
- 已连接但不回复：检查管理员、白名单、唤醒前缀以及插件启用状态；先用 `/ping` 排除模型配置问题。
- 登录新 QQ 号：默认模板只用于创建新的账号配置；检查 NapCat 当前账号网络配置。
- WebUI 提示密码错误：初始化凭据不会覆盖之后在面板修改的密码。

## 上游文档

- [AstrBot OneBot v11 接入](https://docs.astrbot.app/platform/aiocqhttp.html)
- [AstrBot 插件开发](https://docs.astrbot.app/dev/star/plugin-new.html)
- [NapCat Docker 部署](https://github.com/NapNeko/NapCat-Docker)
- [NapCat 文档](https://napneko.github.io/)

本仓库管理部署配置和自有插件，不包含上游项目源码或 QQ 客户端。上游镜像和依赖各自遵循其许可证。
