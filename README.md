# Ventoy Center

源码仓库：[SkyWalkerAMD/ventoy](https://github.com/SkyWalkerAMD/ventoy)。

局域网批量装机管理端。客户端在 BIOS / UEFI 的 Boot 菜单选择网卡，由 **iVentoy / PXE** 加载镜像和自动安装配置；本项目负责目标机器、安装任务、授权、安装包和进度回传。

**当前代码：0.3.0-alpha.58，iVentoy 1.0.49 Pro；Linux CLI 装机优先。** 43 个需要适配的 Linux ISO 已直接内置 E610 驱动，普通手动安装与 PXE 自动安装复用同一成品，并在安装收尾自动持久化驱动。43 个成品的 86 项隔离安装与重启验收通过，物理 E610 验收范围另列。常规无桌面装机使用 Ubuntu Server / live-server、Debian 标准系统与 SSH，以及 CentOS / Rocky / AlmaLinux / RHEL 最小化环境，默认启动到命令行。手动与自动安装均预置含软件分发功能的新版 setup，安装后可直接运行。Windows 保留为次要支持。

安装完成后，运行新版 `sudo bash ventoy-linux-setup.run`，会从中心 `software_dir` 自动获取适合本机的 RPM / DEB 并安装或升级。包可直接集中存放，按架构和 EL 版本匹配；同一软件择新、同版本跳过、不降级。中心替换软件后再次执行即可。详见[节点软件分发](docs/deployment/node-software.md)。

日常装机使用“PXE 选择系统版本 → 选择自动安装脚本 → 选择 ext4 / XFS → 自动安装”。文件系统按发行版默认选择：CentOS / Rocky / AlmaLinux / RHEL 为 XFS，Ubuntu / Debian 为 ext4，仍可手动切换。所选格式应用于 /、/tmp、/var、/home；/boot 保持 ext4、EFI 保持 FAT32。一块可用内置盘自动清空安装；多盘在 PXE 画面选盘并输入 `yes`，也可输入 `r`、两个盘号和 `yes`，重建双盘 RAID1 + LVM。单盘已有 LVM/软件 RAID 时也可选盘并输入 `yes` 重建（alpha.45 起还支持释放旧系统的活动 swap），旧存储必须完整落在所选磁盘范围内，否则列出未选成员并停止。日常安装无需先登记带外地址或创建专属任务。详见 [PXE 菜单安装](docs/deployment/pxe-menu.md)。

配置统一 root 密码的 Ubuntu / Debian 新安装允许 root SSH 密码登录，初次启动后再次检查。Linux 自动安装设置主机名和启动网卡 DHCP，并预置 `safe-server-init`，用于安装后修改主机名及向未配置网卡补充 DHCP；保留现有网络配置与脚本的后端限制。

新生成的 Linux 自动安装任务默认锁定内核，并关闭软件源自动刷新和无人值守升级。去重后的 52 个 Linux 基础路径均提供[完整配置包预置](docs/deployment/manual-linux.md)：43 个适配成品已将驱动和配置包写入 ISO，另 9 个原生支持 E610 的镜像保留原驱动及预置绑定。手动安装后直接运行 `/root/ventoy-linux-setup.run`，配置并检查 SSH、主机名、DHCP、内核锁定和禁用自动更新，同时安装匹配的中心软件组；E610 驱动持久化独立于这个手动操作。Ubuntu Desktop 22.04.4 和 26.04 另有 CLI 启动的自动入口，但镜像仍含桌面软件，无桌面装机优先选择 Server。具体行为、检查与恢复见 [Linux 更新策略](docs/deployment/linux-update-policy.md)。

E610 的精确内核驱动、ISO 制作工具和逐镜像验证记录见 [E610 ISO Kit Release](https://github.com/SkyWalkerAMD/E610/releases/tag/v6.4.5-iso-kit-r1)。该工具包需配合用户自行提供的原版安装 ISO；此仓库保存管理端及安装策略源码。当前 setup 使用 [E610 多系统 r4 离线包](https://github.com/SkyWalkerAMD/E610/releases/tag/v6.4.5-multios-r4)，包含 93 个精确系统／内核条目；镜像中的 43 个已注入驱动与 9 个原生支持入口分别核对，不能用预置包数量代替 E610 实机验收。

现场使用 **iVentoy 1.0.49 专业版**，运行目录 `/home/ventoy-center/iventoy`。alpha.41 将手动/自动安装合并到发行版目录下的同一个 ISO，补齐 Rocky 10.2 和 Ubuntu Desktop 26.04，共覆盖 52 个 Linux 镜像；另保留 6 个 Windows 和 1 个 MemTest86，合计 59 个镜像路径。选择系统后，不选自动脚本进入手动安装，选择脚本进入自动安装。旧的 50 个 PXE-Auto 路径是硬链接，移除它们减少菜单重复，不会释放 50 份 ISO 的空间。原版镜像和恢复备份在菜单外保存，专业版授权、原有机器/任务记录和未涉及入口设置保留。

18 个规划标准版本均完成本轮隔离 QEMU/KVM 自动安装与两次硬盘启动验证。CentOS 7.9、Rocky 8.10、Rocky 9.2 和 Ubuntu Server 22.04.3 另有此前完整物理机验收；Ubuntu Server 24.04.3 已补齐物理 PXE 双盘安装后无人干预的正常硬盘启动，并完成普通 ISO 经真实隔离 iVentoy 的交互手动安装、正常重启、setup 配置和再次重启检查。物理与隔离结果分别记录，不能替代其他硬件或启动模式的验收。具体版本与证据见 [当前进度](docs/development/progress.md)和[现场镜像清单](docs/deployment/image-catalog.md)。

alpha.48 新增安装结果报告、原始失败日志、清盘容量预览和安装依赖缓存。alpha.57 取消启动和登录时的 Ventoy/setup 提示，仍保存本地报告并上传中心；升级 setup 时移除旧版自动生成的提示，保留管理员自定义内容。完整软件回归与两次启动的实机验收方法见 [安装结果与验收](docs/installation-acceptance.md)；本轮实机验收待用户执行。

alpha.57 增加 Debian 13.7 DVD / netinst 入口回归，现场新增 DVD 镜像的驱动与验证范围见 [Debian 13.7 验证记录](docs/development/debian137-2026-11-08.md)。

alpha.52 补充早期 setup 的一次性升级助手，并修复传输后执行权限丢失和校验文件过期的问题；alpha.51 将通用 setup 英文化。alpha.50 增加已有节点 `setup --upgrade`：校验更新后直接应用新版功能，按版本迁移旧配置并保留已有密码、主机名和网络。alpha.49 已增加正式发布与回退、缓存并发与依赖预热、磁盘与备份管理、setup 版本更新以及人工实机验收记录。日常操作请以[当前操作与维护指南](docs/operations.md)为准，历史 PXE-Auto 测试路径不再作为操作入口。

## 已实现

- 中文管理页面、管理口令认证、机器登记、按 MAC 搜索和最近启动任务。
- 按目录浏览 / 搜索 ISO、文件名版本建议、系统模板目录；不把文件名识别视为镜像内容验证。
- 按 MAC、磁盘序列号、启动模式绑定安装任务；草稿需核对机器名和磁盘后授权。
- 24 小时任务凭据、单次安装领取、持久状态、取消与过期检查；服务重启不自动重发安装。
- 生成 CentOS 7.6 / 7.9 / 8.0 / 8.4 / 8.5 / Stream 8 / 9 / 10、Rocky 8 / 9 / 10、AlmaLinux 8 / 9、RHEL 7 / 8 / 9 Kickstart，Ubuntu Server 20.04 / 22.04 / 24.04 / 24.10 / 25.04 / 26.04 autoinstall，Debian 10 / 11 / 12 / 13 preseed。
- 通用 PXE 菜单覆盖上述 Linux CLI 模板；单内置盘自动建立任务，多盘在 PXE 本机选盘并生成对应任务。
- Linux 安装前核对身份和磁盘、首次启动核对系统版本并回传安装状态。Debian 使用专门的安装环境保护脚本。
- 同机 iVentoy 文件准备：独立镜像硬链接、安装脚本、持久清单、失败重试和任务结束后的受限清理。
- Windows 安装前核对 MAC、磁盘序列号、磁盘编号和固件模式；需提前制作含所需可选组件的 WinPE。

新装 Linux 默认普通账户为 `user / ventoy`，root 为 `root / ventoy`，支持系统控制台和 SSH 直接登录；BMC 管理网页使用独立账户。自动分区按磁盘容量档位分配 EFI、boot、tmp、swap、var、root，剩余给 home；双盘 RAID1 以较小成员盘计算。详见 [分区规则与登录策略](docs/deployment/pxe-menu.md)。普通手动安装仍由安装器选择分区及账户，进入系统后运行预置 setup 应用账户和系统策略。

## 当前边界

- **本阶段仅装机。** 新任务拒绝 `enroll: true`，界面不再要求节点包或连接文件。alpha.1 历史任务和状态仍保留，不自动迁移或执行。
- **安装包下载不是 PXE 下发。** 需要在 iVentoy 中关联镜像、脚本及按 MAC 的分机独启规则。尚无经过现场验证的 iVentoy 自动配置适配器。
- 通用菜单为每台机器动态领取独立任务，按 MAC、盘序列号和启动模式再次核对。旧式专属任务仍使用各自独立 ISO 路径与脚本绑定。
- Windows ISO 的 WinPE 默认通常不含 PowerShell / StorageWMI，组件不足时安装保护会阻止继续。当前 Windows 模板语言支持 zh-CN / en-US，须与镜像一致。
- Linux 存储模板支持单盘和明确选择的双盘 RAID1 + LVM 重建。已有 LVM / RAID 经本次选盘及 `yes` 确认后可重建；安装前核对完整成员范围，拒绝未选成员、缺失 LVM 成员、挂载盘及活动交换空间。

## 服务端平台

| 平台 | 交付方式 | 当前验证范围 |
| --- | --- | --- |
| Rocky Linux 9（首要目标，包含用户的 9.8 环境） | 静态 Linux x86-64 二进制 + systemd | 9.8 同机服务、TLS 与管理接口已验证；已承载 CentOS 7.9、Rocky 8.10、Ubuntu 22.04.3 实装，具体边界见验收记录 |
| Rocky Linux 8 / 10 | 同一 Linux 二进制 | CI 启动检查，不等于 systemd / PXE 实机验收 |
| Debian 12 / 13 | 同一 Linux 二进制 + systemd | 同上 |
| Ubuntu 24.04 / 26.04 | 同一 Linux 二进制 + systemd | 同上；其他 24–26 间的短周期版本未单独验证 |
| Windows 10 / 11 x64 | Windows 二进制 + 可选计划任务 | Windows 单元测试；桌面系统与 iVentoy 共存需实机验收 |

这里列的是**装机服务器的运行系统**，与[客户端安装版本和镜像要求](docs/deployment/linux-targets.md)分开管理。规划版本与库存扩展版本的模板、隔离安装和物理验收状态分别见进度表。Ubuntu 无桌面装机优先选择 Server / live-server；Desktop 22.04.4 和 26.04 的自动安装保留桌面软件，默认以 CLI 启动，验收单独记录。

## 本地启动

需要 Go 1.25 或更新版本；运行已编译程序不需要 Go、Node.js 或 Python。

```sh
go build -o ventoy-center ./cmd/ventoy-center
./ventoy-center init --dir ./runtime
./ventoy-center serve --config ./runtime/config.json
```

打开 `http://127.0.0.1:26080`，使用 `runtime/admin.token` 登录。将 ISO 按发行版放到 `runtime/iso/` 下，例如 `Rocky/Rocky-9.8-x86_64-dvd.iso`。

默认只监听回环地址。给局域网客户端使用之前，需要配置可达的 HTTPS 地址与证书；详见 [Rocky 9 部署](docs/deployment/rocky9.md)。Windows 命令将可执行文件改为 `ventoy-center.exe`。

## 文档

- [Rocky 9 与 fyhocsys 同机部署](docs/deployment/rocky9.md)
- [外部 DHCP、iVentoy 和安装包配置](docs/deployment/pxe.md)
- [同机准备 iVentoy 文件和权限配置](docs/deployment/iventoy-files.md)
- [iVentoy 现场升级与回退记录](docs/deployment/iventoy-upgrade.md)
- [Linux 安装版本、镜像和验收矩阵](docs/deployment/linux-targets.md)
- [现场镜像清单与新增 ISO 校验记录](docs/deployment/image-catalog.md)
- [CentOS 7.9 镜像、兼容处理与安装验证](docs/deployment/centos7.md)
- [Rocky 8.10 实机验收与启动回归](docs/deployment/rocky8.md)
- [Ubuntu 22.04.3 无人值守实机验收](docs/deployment/ubuntu22.md)
- [当前进度、客户端矩阵与后续工作](docs/development/progress.md)
- [Windows 与其他 Linux 服务端](docs/deployment/platforms.md)
- [架构、任务状态与尚未完成的能力](docs/development/architecture.md)
- [开发与验证](docs/development/testing.md)

本项目是独立编写的管理端，不包含 iVentoy、Windows ISO、fyhocsys 私有源码、节点包或任何授权文件。iVentoy 是单独安装和许可的软件；按 MAC 分机独启及商用需参考其[专业版说明](https://www.iventoy.com/cn/doc_edition.html)。
