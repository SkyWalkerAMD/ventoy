# Ventoy Center

面向局域网的 PXE 装机管理端。iVentoy 负责网络引导和镜像传输，Ventoy Center 负责镜像与安装任务管理、安装脚本和注入包生成、节点软件分发，以及安装结果和失败日志回传。主要用于 Linux 命令行系统部署，也提供 Windows 专属任务模板。

**当前部署**使用 Ventoy Center **0.3.0-alpha.64** 和 **iVentoy 1.0.50 Pro**，共 60 个镜像，其中 53 个 Linux 镜像提供共享的手动／自动安装入口。IPv4 与同网段 IPv6 的 UEFI 引导文件已验证可下载。各系统的模板、虚拟机及实机验收范围见[当前进度](docs/development/progress.md)和[现场镜像清单](docs/deployment/image-catalog.md)。

## 快速启动

从源码构建需要 **Go 1.25+**。下面的命令启动一个只监听本机的管理端，适合先查看界面和镜像目录。

```sh
go build -o ventoy-center ./cmd/ventoy-center
./ventoy-center init --dir ./runtime
./ventoy-center serve --config ./runtime/config.json
```

浏览器打开 `http://127.0.0.1:26080`，使用生成的 `runtime/admin.token` 登录。将安装镜像按发行版放入 `runtime/iso/`。Windows 上构建和运行时使用 `ventoy-center.exe`。

部署到装机中心时，可从 [GitHub Actions](https://github.com/SkyWalkerAMD/ventoy/actions/workflows/ci.yml) 的成功构建获取 `ventoy-center-packages`，按包内的 `SHA256SUMS` 校验。Linux 使用 [systemd 部署指南](docs/deployment/rocky9.md)，Windows 见[服务端平台](docs/deployment/platforms.md)。

正式部署还需要准备以下运行文件。

| 用途 | 所需文件与配置 |
| --- | --- |
| 中心服务 | 用 `init` 生成配置和管理口令。为客户端配置可达的 HTTPS 地址、服务证书和 CA。 |
| 网络引导 | 单独部署 iVentoy 和所需授权，准备自己的原版 ISO，配置 DHCP 和 iVentoy 镜像绑定。[PXE 配置](docs/deployment/pxe.md) |
| Linux setup 与预置包 | 在 `package_dir` 放置 [E610 多系统 r4 离线包](https://github.com/SkyWalkerAMD/E610/releases/tag/v6.4.5-multios-r4)中的原始 `E610-MultiOS-6.4.5-r4.tar.gz`。管理端生成 setup 时会校验固定摘要。[完整配置包](docs/deployment/manual-linux.md#检查结果和边界) |
| 节点软件分发 | 在 `software_dir` 放置适用的 RPM、DEB 和工具文件。私有接入参数和密钥使用分发目录之外的受限文件。[软件分发](docs/deployment/node-software.md) |

公开仓库提供源码、构建与验证脚本，以及部署文档。ISO、iVentoy 专业版程序和许可证、部署配置、节点软件包及私有密钥由部署方提供和保管。

## 装机流程

1. 客户端从 BIOS／UEFI 网卡启动，在 iVentoy 里选择发行版和版本。同一 Linux ISO 可进入原生安装器手动安装，也可选择自动脚本。
2. 自动安装可选择 ext4 或 XFS。Ubuntu／Debian 默认 ext4，红帽系列默认 XFS。多盘或旧存储重建按提示核对盘号和分区预览，确认后才清理目标盘。可选双盘 RAID1 + LVM。
3. 安装并从硬盘启动后，检查系统、网络和中心报告。需要完整节点配置时执行预置的 `/root/ventoy-linux-setup.run`。

Linux 主要覆盖 Ubuntu、Debian、CentOS、Rocky Linux、AlmaLinux 和 RHEL。具体版本、安装源和硬件验收见[目标系统矩阵](docs/deployment/linux-targets.md)。操作步骤和分区规则见[PXE 菜单](docs/deployment/pxe-menu.md)和[安装验收](docs/installation-acceptance.md)。

## Linux 节点 setup

```sh
sudo bash /root/ventoy-linux-setup.run --help
sudo bash /root/ventoy-linux-setup.run
```

无参数运行时应用主机名、账户和 SSH、未配置有线网口的 DHCP、内核锁定和更新策略，并安装中心匹配的软件组。E610 需要补驱动时，按当前内核匹配离线包。

| 命令 | 用途 |
| --- | --- |
| `--list-software` | 查看匹配的软件包及可分发文件。 |
| `--software`、`--check-software` | 单独安装软件组，或验证上次的安装和文件。 |
| `--check-version`、`--update-setup` | 查询中心版本，或只下载并替换 setup。 |
| `--upgrade` | 更新并应用最新版 setup。 |
| `--install-fyhoct` | 显式安装匹配的 `sckoct-fyh` 并初始化组件。常规软件分发仅保存它的包文件。 |
| `--restore-user-login` | 在 Ubuntu／Debian 验证普通用户及 sudo 后，关闭 root 直登。 |
| `--uninstall` | 预览并确认卸载受管软件及文件。旧版安装记录可通过 `--include-legacy-packages` 纳入预览。 |

命令细节和退出码见英文帮助，常见升级、软件和登录操作见[日常维护](docs/operations.md)。

## 源码和文档

| 目录 | 内容 |
| --- | --- |
| [`cmd/ventoy-center/`](cmd/ventoy-center/) | 管理端命令入口。 |
| [`internal/center/`](internal/center/) | HTTP API、PXE 任务、镜像与软件管理、Web 界面、安装模板和 setup 源码。 |
| [`deploy/`](deploy/) | 服务安装、发布、回退和维护脚本。 |
| [`scripts/`](scripts/) | 安装模板、setup 和发布流程的验证脚本。 |
| [`tools/`](tools/) | ISO 兼容构建工具及独立 P95 助手。 |

```sh
go test ./...
go vet ./...
python3 scripts/validate_operations.py  # Linux 发布与回退测试
```

开发入口见[架构说明](docs/development/architecture.md)和[开发与验证](docs/development/testing.md)。部署维护见[日常操作](docs/operations.md)、[iVentoy 升级记录](docs/deployment/iventoy-upgrade.md)和[版本变更](CHANGELOG.md)。
