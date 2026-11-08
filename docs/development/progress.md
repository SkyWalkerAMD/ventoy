# Ventoy Center 当前进度

## alpha.58、Debian 13.7 与 Z790 引导验收（2026-11-08）

中心 `192.168.1.2` 已发布 **0.3.0-alpha.58**，iVentoy 为 **1.0.49 Pro**。
当前 60 个镜像中有 53 个 Linux 手动／自动共享入口；全部入口文件和注入包内的
setup 已逐一回读，SHA-256 为
`7057aa2f45ea8c3103a191a23e7375e11f1e9755b41935b5cd4d51a3e260364d`。
Debian 13.7 DVD 已增加、启用并完成驱动 ABI 与注入检查，具体构建和实机边界见
[Debian 记录](debian137-2026-11-08.md)。

安装后的 Ventoy/setup 控制台及 SSH 提示已取消；验收服务、磁盘报告和中心上报
继续静默运行。已装节点执行新版完整 setup 或 `--upgrade` 后迁移已识别的旧提示
文件；仅中心发布不会主动改写旧节点。Ubuntu SSH socket activation 的首次启动
检查也已修复，未获 DHCP 租约的待完成状态不再被误标成 systemd 服务失败。

Z790 HERO / 14900KS / PCIe I350 的 Ubuntu 24.04.3 自动安装已完成，两次硬盘
启动均通过 SSH、容量分区、内核锁定、禁用更新和预置脚本检查；第二次已断开
虚拟光驱。连续 root/user SSH 登录没有重复 Ventoy 提示。
`initrd` 分配错误由 Ubuntu GRUB TPM verifier 的整文件缓冲分配触发；发布的
同一 ISO 增加显式 `low-memory compatibility` 菜单项，选择后跳过当次 GRUB
TPM 测量，不修改固件 TPM/Secure Boot 设置。原默认项仍保留；此验收不代表
其他系统或未接线 I226-V 已通过。详见[实机记录](z790-ubuntu-2026-11-08.md)和
[使用说明](../deployment/ubuntu-uefi-low-memory.md)。

服务器构建残留已按引用和挂载审计清理，最终 `/home` 可用约 **127.65 GiB**；
生产 ISO、当前发布包、回退文件及验收证据保留。相关源码见
[PR #37](https://github.com/SkyWalkerAMD/ventoy/pull/37)、
[PR #38](https://github.com/SkyWalkerAMD/ventoy/pull/38) 和
[PR #39](https://github.com/SkyWalkerAMD/ventoy/pull/39)。

## 仓库迁移到 SkyWalkerAMD（2026-11-01）

仓库已转移至 [SkyWalkerAMD/ventoy](https://github.com/SkyWalkerAMD/ventoy)，仓库 ID `1416418315` 与迁移前一致，迁移时 main 为 `160ae20`。本地 origin、Go 模块及内部导入地址、此仓库的历史 PR/CI 链接同步到新地址。

新模块地址下的 `go vet ./...`、`go test ./...` 及 Linux / Windows amd64 构建通过。

本次为源码地址迁移，中心 `192.168.1.2` 保持 alpha.50 / iVentoy 1.0.49 Pro。节点 setup 的更新与软件下载继续使用中心 HTTPS 地址；已安装节点及 PXE 入口无需因仓库迁移重新配置。

## alpha.50 已安装节点的 setup 升级（2026-11-01）

[PR #28](https://github.com/SkyWalkerAMD/ventoy/pull/28) 已合入 main（`3f283fd`），13 项 CI 通过。中心 `192.168.1.2` 已发布 **0.3.0-alpha.50**，iVentoy 保持 **1.0.49 Pro**。52 个 Linux 手动／自动共享入口及 tools 中的 setup 全量回读一致，SHA-256 为 `28253d1ee2fc7b14dbeaced8326dab4feb693fcfac5af99b28c2ffef08833e47`；59 个镜像绑定、ISO 元数据、其他 tools 文件、私有配置和任务历史核对保持。

新版 `./ventoy-linux-setup.run --upgrade` 下载、校验、备份并替换当前文件，随后执行新版配置及软件检查。已经完成 setup 的节点按包内容迁移 SSH、内核／更新策略、离线配置包和服务，保留当前密码、主机名及既有网络；失败可重试，普通开机不重复迁移同一版本。`--update-setup` 继续只下载；alpha.49 旧文件第一次使用它，再直接运行新版。更早没有更新入口的文件须先从管理端获取新版一次。操作详见[维护指南](../operations.md)。

9 项新增隔离测试覆盖真实启动器更新执行、配置包与服务替换、旧完成标记迁移、账户保留、失败重试、重复运行及校验失败不执行；原有账户、主机名、软件、安装模板和分区回归同时通过。正式发布后，使用中心原有 alpha.49 文件完成真实 HTTPS 下载到 alpha.50、备份核对及再次更新幂等验证。没有在中心执行节点系统配置，也没有重装客户机；完整实机升级验收由用户继续执行。发布及回退目录为 `/home/ventoy-center/releases/alpha50-20261101`，证据在中心 `e610-pxe-media-20261023/setup50-20261101/`。

## iVentoy 1.0.49 专业版升级（2026-10-31）

中心已运行 iVentoy **1.0.49 Pro**，管理端保持 **0.3.0-alpha.49**。升级前无活动安装或镜像连接；授权、全部全局配置、59 个镜像配置和 52 个 Linux 共享手动／自动入口的脚本及注入包逐项核对通过。ISO 元数据、用户文件与 tools 内容摘要保持一致，两个服务及 PXE 网络均正常。升级包摘要、备份和回退方法见[升级记录](../deployment/iventoy-upgrade.md)。本轮未重装客户端，实机安装验收由用户继续执行。

## alpha.47 独立 P95 分发与 CPU 分组修复（2026-10-30）

[PR #21](https://github.com/SkyWalkerAMD/ventoy/pull/21) 已合入 main，13 项 CI 通过。中心已发布 `0.3.0-alpha.47`，iVentoy 为 `1.0.48` 专业版。全部 52 个 Linux 手动/自动共享入口与 tools 中的完整 setup 已逐一校验，共同 SHA-256 为 `a7e45907fde193645aa533222f18bae5ce4363f1d386f7b36dc04c7150490ed1`。

**完整 setup 不再集成 P95 修复**，只将中心 tools 中的独立脚本同步到 `/root/ventoy-tools/p95-priority-setup.sh`，需要时由管理员手动执行；不会自动安装、升级、重启或检查已装的助手。

独立助手 `1.0.3` 增加实际 CPU 控制器检查与默认权重配置，解决仅调整 nice 后 P95 仍被大量 memtester 会话挤占的问题。Rocky 9.2 / 9995WX 已完成 33 秒、1% 内存的隔离对比测试，P95 和 memtester 均有 192 个工作线程取得 CPU 时间进展，节点服务及内核保持。数据、边界及复查方式见 [P95 CPU 分组验收记录](p95-cpu-sharing-2026-10-30.md)。CentOS 7 保留 systemd 219 渲染和 cgroup v1 夹具验证，不能将本次 Rocky 实测推广为所有平台的混合压测验收。

## alpha.46 P95 集成与 CentOS 7.9 适配（2026-10-30）

[PR #20](https://github.com/SkyWalkerAMD/ventoy/pull/20) 已合入 main，13 项 CI 全部通过。中心 `192.168.1.2` 已发布 `0.3.0-alpha.46`，iVentoy 保持 `1.0.48` 专业版。tools 中的 `ventoy-linux-setup.run` 与全部 52 个 Linux 手动/自动共享入口均已更新；发布后逐项核对预置包，共同 SHA-256 为 `253d647f0fd1aee4b0365a466b4c73e00389f1f2a74453da1fcdf5205f6ac084`。59 个 ISO、菜单绑定、其他 tools 文件及私有接入配置核对保持。

完整 setup 在节点软件安装及已配置的接入完成后自动配置、检查 P95 助手；即使软件包版本没有变化，也会执行此步骤。P95 助手升级为 `1.0.2`，支持 CentOS 7.9 的 systemd 219、EL7 mprime 和额外 memtester 路径。旧 systemd 使用兼容的服务配置，助手自行保护 `/run` 下的恢复记录。只匹配节点服务 cgroup 内指定路径和参数的 mprime 线程，将 nice 19 调回 0；不启动压测，不改写节点软件包。

带外 `.235` / 系统 `.52` 的 CentOS 7.9 完成独立助手安装、真实 nice 系统调用自检、只读检查、重复运行以及助手服务重启后的恢复记录保留测试。随后以生成的完整 `.run` 无参数执行：hostname/root 密码提示均出现，留空保留现有设置；4 个匹配软件包保持原版本，SSH/DHCP、内核锁定、禁用自动更新、FYHOC 解锁、节点接入和 P95 检查通过。内核仍为 `3.10.0-1160.el7.x86_64`，原节点服务持续运行。

本轮没有启动用户的压力测试、重启整台测试机或重新安装全部发行版，也没有新增 AMD 平台的压测/性能验收。全量 Go/脚本回归、52 份预置内容核对与 CentOS 7.9 实机 setup 验证分别记录，不能扩大为所有平台已实测。发布证据在中心 `e610-pxe-media-20261023/integration46-20261030/`，回退目录为 `production-backup-20261030-082535`。

## alpha.45 现场发布与 setup 实机复测（2026-10-29）

[PR #19](https://github.com/SkyWalkerAMD/ventoy/pull/19) 已合入 main，13 项 CI 全部通过。初次 CI 发现包副本测试复用已有内核策略时漏带真实检查脚本，已修复测试准备流程并完整重跑；没有跳过安装后的内核策略验证。中心 `192.168.1.2` 已更新至 `0.3.0-alpha.45`，iVentoy 保持 `1.0.48` 专业版，全部 52 个 Linux 手动/自动共享入口和 tools 中的 setup 已更新。59 个 ISO 的内容/元数据、菜单绑定、tools 中其他软件包及专业版许可保持。

现场重新取得的 FYHOCSYS 接入参数已核对中心 TLS 指纹，保存至服务账户拥有的 `0600` 私有文件，生产独立鉴权接口验证通过；包内容检查确认接入密钥不在 setup 中。52 个入口内置 setup 的共同 SHA-256 为 `ed0b6543db2f7d9bf0d5f784355ad2409b1de6211133a5db19f9fda821a96eca`。

带外 `.235` / 系统 `.52` 的 CentOS 7.9 上，无参数交互 setup、系统检查、软件检查和重复软件执行通过：hostname 与 root 密码提示均出现，留空保留 `s4-2495x1` 和当前密码；9 个附加文件及 4 个匹配 RPM 的原文件摘要通过，RPM 副本权限为 `0600`，重复运行不重装。内核仍为 `3.10.0-1160.el7.x86_64`，内核包与密码摘要保持，SSH/DHCP/更新策略及 FYHOC 自动解锁检查通过。

该机已有 FYHOCSYS 0.8.6 绑定，新版 setup 验证绑定、中心证书、worker 和开机服务；重复执行不改绑定、不重启运行中的节点服务，中心节点总数仍为 35，`s4-2495x1` 的心跳持续更新。临时接入密钥文件已清理。本轮实机覆盖既有绑定的重复接入，没有把它计为新节点首次登记、重装重新绑定或重启验收；首次/失败/重试边界由隔离回归覆盖，本轮也没有重新实装全部 Linux 或验证 E610 实卡。

发布、回退和实机证据保留于中心 `e610-pxe-media-20261023/integration45-20261029/`：`deployment.json`、`all52-entry-audit.json`、`ci-acceptance.json`、`node235-acceptance.json` 与 `node235-interactive.log`。回退目录为 `production-backup-20261029-161940`。用户确认 `.249` 安装已停止后，已通过管理端结单并在无活动安装和镜像连接时刷新服务。

alpha.45 集成旧存储重装、DHCP 链路延迟适配、软件包副本保留和长期密钥节点接入。2026-10-29 已在 Windows 工作区复测 Go 全量测试、vet 和 JavaScript 语法，并在中心的隔离目录复测 Linux 脚本与模板。一次性交接文档已移除；复现方法保留于[开发与验证](testing.md)，私有配置方法见[软件与节点接入](../deployment/node-software.md)。

本轮 Linux 检查包括单盘/双盘各 39 个存储场景、56 个单盘及 54 个 RAID 配方、660 项容量档位和 220 项文件系统配方、DHCP 12 项回归，以及 root 身份运行的节点接入隔离检查。生产发布证据集中保存于中心 `e610-pxe-media-20261023/integration45-20261029/`；只有该目录的 `deployment.json` 与实机验收记录完成，才表示对应生产更新和实机验证完成。以下云端结果保留原有测试范围，不扩大为全部发行版或硬件的实机通过。

## setup 长期密钥接入与包副本保留（alpha.45）

核对 sckocstp 0.8.6（`1d6310c50341cf3e07e4aef67e3f0ca79502196b`）与 fyhocsys 0.8.6（`c66dc8febdbaeda81ee144c9afacbe2e02bfb13d`）源码和发布说明。两者的长期接入均使用官方 `join --key-file`；中心生成/显示/作废密钥，新节点使用主机名和 DMI 序列号登记，同机重装按中心记录的 DMI UUID 和 5 分钟离线条件重新绑定，重复执行不重建同一中心的本机连接。

新增 `node_join_config_file` 私有 JSON 和独立的软件下载鉴权接口。新版 setup 在匹配节点包安装后执行接入，校验版本至少 0.8.6、保存的中心地址/证书/主机名、官方 worker 检查及节点开机服务。服务首次启用失败后可重试，不重启已经运行的节点服务，不覆盖不同中心的绑定。完整 setup 接入失败保留软件重试请求。密钥不进入源码、清单、setup 或结果文件，临时 `0600` 密钥文件在成功、失败、超时后清理；用户提供的实际配置仅在工作区仓库外准备，未发布到生产。

按用户补充要求，绑定必须等输入/确认的主机名应用并回读成功；即使改名命令返回成功，但实际名称未变，也停止后续软件/绑定。节点接入再次检查未完成的改名请求、运行与持久名称一致、执行中名称未变，并拒绝首次使用常见系统默认名。软件模式带 `--hostname` 会明确要求先运行完整配置。首次执行、启动恢复、改名失败和虚假成功均有真实 Bash 控制流回归。

匹配的 DEB/RPM 同时保留到 `/root/ventoy-tools/`，全组下载校验后安装；旧版已装软件但临时包已清理时补传副本，再次执行不重复下载或安装。安装失败保留副本，受管同名文件可原子更新，用户改动的文件保留并报错。`--check-software` 检查软件版本、包副本、原样工具和已配置的节点绑定。

Go 全量测试、vet、race 通过；Python 软件回归覆盖两种包格式，接入回归覆盖两种命令、秘密文件/输出、重复执行、旧版本、错误/超时、重试和本地绑定/服务检查。Ubuntu 22.04 的 APT 与 Rocky Linux 9.8 的 RPM 另通过真实 HTTP 下载、安装、保留原文件、重复运行、缺失补传且不重装、用户改动保护验证。完整 setup 的网络、主机名、SSH、待重启和软件请求恢复回归通过。

接入测试使用隔离节点命令与中心响应夹具；没有向用户真实中心登记节点或进行生产开机、心跳、压测验收。公开发布资产读取返回 404；尝试构建原版 0.8.6 节点时，SQLite 依赖的下载重定向被云端网络策略拒绝，未绕过限制。当前云端没有生产内网通道。复用配置和部署方法见[软件与节点接入](../deployment/node-software.md)，本轮证据在 `/workspace/ventoy-validation/node-setup-report.md`。

## setup DHCP 链路延迟适配（alpha.45）

根据 Ubuntu 22.04.3 的 DHCP 问题反馈，复现了 setup 的一个独立缺陷：新网卡启用后只等待 1 秒，若此时还没有 carrier，包装脚本跳过 Netplan 生成配置的发布/加载；因此 YAML 和 managed.tsv 已存在，稍后接通链路仍无法申请地址。现在先加载所选新增网卡的 networkd 配置或 Netplan/NetworkManager autoconnect 配置，再等待链路，不重启全局网络、不转换已有静态配置。生成、复制、重载和激活失败均明确保留待处理状态，修正了条件函数中失败状态被后续清理命令掩盖的问题。

12 项隔离回归覆盖 networkd / NetworkManager 的迟到链路、生成失败、加载失败（含无 carrier）、激活失败、重试和已有主接口配置保留；已接入 `validate_manual_setup.py`。全套 setup 回归与 Go 全量测试通过。

云端 QEMU 的 Ubuntu 22.04.5 用户空间使用真实 Netplan `0.107.1-3ubuntu0.22.04.5`、systemd `249.11-0ubuntu3.23`：旧脚本在断开次要网口时保存配置但未加载，接通后仍无地址；新版在保留旧脚本所写 YAML/状态的情况下加载配置，接通后获得 `10.0.3.15`，重复执行及再次启动通过。主网口原配置 SHA-256、默认路由和 DNS 保持，次要网口未接管 DNS。测试由 QMP 控制虚拟链路，使用 Debian 测试内核 `6.12.113+deb13-amd64`，不是 Ubuntu 22.04.3 原介质或 E610 实卡验收。现场是否为同一故障，仍需要对应 setup 日志判断；没有修改用户主机或发布中心 setup 文件。

证据：`/workspace/ventoy-validation/jammy-dhcp-final/boot1.log`、`boot2.log`、`manual-setup-final.log`，说明见 `dhcp-report.md`。

## 云端旧存储重装回归（alpha.45）

继续适配已有系统盘：安装环境启用旧 swap 后，客户端原先直接拒绝目标盘，Python 客户端还将 `[SWAP]` 与真实挂载混为一谈。现支持显式确认的单盘/双盘重建：领取前仅检查，领取后重新检查完整成员、挂载、设备身份和 LVM 状态，随后只关闭所选块设备上的 swap。未选 swap 保持启用；真实挂载、只读盘、跨未选磁盘的存储，以及关闭失败或关闭后仍启用，均停止安装。

本次新增回归使单盘/双盘隔离检查各达到 39 项。云端真实存储检查达到 27 项，加旧版本对照共 28 项通过；新增普通分区、LVM、MD 的 swap 释放与未选 swap 保持启用检查，每项仍验证保留盘完整 SHA-256。Go 全量测试、vet、race、Python/原生 Debian 客户端及 52 份模板、28 份账户策略、56 个单盘与 54 个 RAID 配方验证通过。证据为 `/workspace/ventoy-validation/reinstall-*`。

本次还从上轮已经安装并两次启动的 Debian 13 系统盘创建 qcow2 快照，保留旧分区并启用旧 swap。旧脚本在同一磁盘上复现拒绝；新准备流程释放 `/dev/vda4` 后，原生 partman 完成覆盖安装。两次硬盘启动均确认旧标记文件消失、根文件系统 UUID 改变、五个挂载点正确，保留盘完整 SHA-256 不变。日志位于 `debian-reinstall/install.log`、`boot1.log`、`boot2.log`。

修复已确认的同名 LVM 卷组误拦截：两块磁盘独立安装同一发行版时，卷组名称可能相同。原预检按名称扩展成员，把未选盘误判为所选卷组的成员；现在按 UUID 检查完整成员。真正跨盘、重复 UUID、无法读取身份和挂载继续拒绝；活动 swap 的后续适配见上文。新建 RAID 的 `vcvg` 名称被未选卷组占用时仍停止，不能因所选盘也有同名卷组而放行。

原生 Debian Installer 13 的对照试验另复现：只修预检仍会在分区阶段提示 `Unable to automatically remove LVM data`，因为 partman 按卷组名称枚举 PV。已增加授权后的准备步骤：领取一次性任务成功、重新核对存储状态后，按 UUID 仅为所选同名旧卷组改名，让原生安装器能准确移除其旧存储。拒绝授权时不改名；状态变化、临时名称冲突或改名失败都会停止。

前一轮在云端 QEMU TCG 中完成 22 项真实存储检查，另用旧版脚本复现同名卷组误拦截，共 23 项通过。覆盖空盘、遗留 PV、活动/非活动 LVM、同名独立卷组、重复预检、授权后改名及重复准备、挂载 LV、swap、跨盘 VG，以及活动/非活动 MD RAID；每项均检查未选 64 MiB 虚拟磁盘的完整 SHA-256。目标盘为两块临时 128 GiB 稀疏磁盘，未映射宿主或生产块设备。可复用脚本为 `scripts/validate_storage_vm.py`，运行方法见[开发与验证](testing.md)。

Debian 13.7 原生安装器的 BIOS 实装另已通过：在所选盘和保留盘上分别创建独立但同名的旧 LVM 卷组，使用实际渲染的存储预检、授权后准备和单盘配方，由原生 partman 完成覆盖分区及系统安装。GRUB 安装成功，退出安装器后两次仅从硬盘启动，均读取到 Debian 13.7 / `6.12.107+deb13-amd64`，根、boot、tmp、var、home 均挂载为 ext4。安装收尾及两次启动的保留盘完整 SHA-256 全部一致。

该实装使用签名校验通过的 Debian netboot 和软件源，测试专用应答配置账户及启动校验；控制器的一次性授权另由 Go/API 和实际渲染的领取步骤回归验证。本轮实装范围为存储重建、原生安装与硬盘启动，不包含真实 iVentoy 网启、UEFI/物理硬件、生产账户登录和业务软件。启动校验后主动关机时记录了 systemd bus 退出提示，不据此声称日志零告警。云端证据位于 `/workspace/ventoy-validation/`，包括 `storage-vm-preparation.log`、`debian-native/without-preparation-failure.log`、`debian-native/install.log` 与两份硬盘启动日志。

Go 回归、vet、race，52 份 Linux 模板、单盘/双盘各 31 个存储场景、56 个单盘重建组合、54 个 RAID 组合、660 项容量及 220 项文件系统组合通过。云端存储检查结果不代表所有发行版、硬件或 iVentoy 网启均已实装；本轮没有发布到生产管理端。

## alpha.43 已有 LVM 的单盘重装（2026-10-28）

PXE 选盘新增旧存储重建。单块内置盘已有 LVM/软件 RAID 时显示选择页，用户选择该盘并输入 `yes`，安装前核对全部旧成员均在所选范围内，再使用原生安装器重建分区。两盘镜像继续使用 `r` 选择双盘 RAID1 + LVM。USB、未选成员、挂载、活动 swap、重复序列号及无法可靠检查的存储不会被隐式清理。该变化覆盖 Anaconda、Subiquity、Debian Installer 和 Ubiquity，手动入口仍保留原生分区交互。

新增 API 一次性确认、实际 Python/原生 Debian 客户端和成员检查回归；单盘重建的 56 个模板/启动模式组合、现有双盘布局、容量档位与 ext4/XFS 验证通过。`.249` 的原始原因已确认是旧 Rocky LVM，取得目标盘清空授权后在 alpha.42 上完成 CentOS 7.9 实装和正常硬盘启动，保留 USB 数据盘；`.235` 的新版 setup 与重启验证也已完成。具体边界见[平台与实机记录](../deployment/linux-platform-checks.md)。

新流程的隔离 CentOS 7.9 UEFI 完整安装已通过：带旧 LVM 启动后能进入文件系统/选盘页，确认目标盘后原生重分区、正常重启到硬盘系统，root/user SSH、分区、更新策略和 setup 检查通过，USB 模拟盘保持。旧流程在页面出现前就拒绝单盘 LVM 的问题已在客户端和管理端同时修正。

13 项 CI 通过后，[PR #17](https://github.com/SkyWalkerAMD/ventoy/pull/17) 已合入 main，并于 2026-10-28 发布 alpha.43。发布前确认没有活动安装任务，`.249` 已从硬盘运行；备份后更新管理端、52 个 Linux 共享入口及 tools 中的 setup，刷新 iVentoy 并核对全部绑定。59 个 ISO 的内容和元数据、tools 的其他软件包、专业版许可及私有解锁凭据保留。发布后 `.249` SSH 再次登录通过。

发布记录在中心 `e610-pxe-media-20261023/storage43-20261028/deployment.json`，同目录保存全量入口核验、CI 和隔离安装结果及生产回退副本。全部 52 个入口预置 setup 的共同 SHA-256 为 `df51467abc6a250dbb2dd661b864115f082d91fc39d4da8eaaaa73c0dff038a9`。

## alpha.42 退出介质、软件解锁与终端刷新（2026-10-28）

iVentoy 已升级为 1.0.48 专业版，许可、59 个 ISO 路径及原有绑定核对通过；升级与回退记录见[部署说明](../deployment/iventoy-upgrade.md)。管理端 alpha.42 已于 2026-10-28 发布：用户确认客户端退出安装器后，备份配置与预置文件，更新全部 52 个 Linux 手动/自动共享入口及 tools 中的 setup，刷新服务并核对绑定和摘要。ISO 内容及 tools 内其他软件包保持不变。源码经 13 项 CI 检查通过，已通过 [PR #16](https://github.com/SkyWalkerAMD/ventoy/pull/16) 合入 main。

Ubuntu 26.04 在安装完成后，为 Casper 的 vendor-mask 创建仅本次 live 环境有效的 cdrom 挂载单元，实际启用 LazyUnmount；同时通过 finalrd 运行时钩子补入 systemd 动态加载的 libmount。Desktop 自动安装和 Server 逐页手动安装均完成并通过原生重启进入硬盘系统；未强制重启、提前弹出镜像或改写目标系统的关机逻辑。`/cdrom` 的单元卸载失败和 libmount 缺失问题已修复；最终退出仍可能记录 loop 设备忙的提示，不能称为关机日志完全无告警。

自动安装检查分区、CLI、root/user 密码 SSH、user sudo、root 控制台登录、内核/更新策略及预置包摘要，并通过第二次硬盘启动。手动安装在首次执行完整 setup 前已检查更新策略和预置包，随后运行 setup 配置 SSH/DHCP 并安装软件。两者内核保持介质版本 `7.0.0-14-generic`。手动模式保留原生选盘、账户、网络等页面。

FYHOC 使用真实 `unlk` 认证，并启用每次开机离线重新认证的服务。CentOS 7.9 的 RPM 和 Ubuntu 26.04 的 DEB 实测安装 `fyhoc 1.1.24-1`、动态选择 `fyhocsys-node 0.8.5`，正常重启后解锁仍有效；9 个附加工具文件传输及摘要检查通过。口令保存在中心私有文件和节点 root-only 文件，不写入公开源码、ISO、setup 或日志。完整 setup 成功改名后，前台 `.run` 启动器进入新 Bash 提示符；PTY 回归验证了目录保留、sudo 原账户及后台/失败不打开 shell。

完整 `.run` 交互增加 root 密码修改：隐藏输入并二次确认、留空保留，修改当次测试真实 SSH 登录。保存自定义状态而不保存密码，后续 setup/开机不恢复默认值，普通账户密码不变。PTY 回归覆盖空白字符、取消、输错重试、密码策略失败和 SSH 验证失败后的准确提示；Ubuntu 26.04 与 CentOS 7.9 隔离虚拟机均验证新密码登录、重复执行、正常重启保持、普通账户密码保持以及当前 root 提示符刷新。

52 个 Linux 手动/自动共享入口已核对预置包一致性。全量模板与策略检查、代表版本完整安装及 AMD CPU 软件模拟的边界详见[平台检查](../deployment/linux-platform-checks.md)。没有把这些结果扩大为全部 AMD/Intel 主板实机通过，也没有操作用户要求保留的 `.54`。用户已更正：`updates_disk_hook` 截图属于 `.249` 的 10980XE，`.235` 的 2495X 可正常到达选择页，随后已完成 CentOS 7.9 安装与旧版 setup。

隔离证据位于中心 `e610-pxe-media-20261023/ubuntu26-reboot42-20261027/`：完整回归、全量入口核验、手动/自动首次启动、FYHOC 重启验收与 AMD 模拟记录分别留存。现场最终发布结果单独记录为 `deployment.json`。

发布后在 `.235` 已安装的 CentOS 7.9 上完成新版 setup 实机复测：无参数执行、交互提示及正常重启均通过，FYHOC 开机自动解锁，现有主机名与自定义密码保持，内核和内核包未更新。`.249` 的 KVM 日志确认本次 CentOS 停止源于内置 SSD 上的旧 Rocky LVM 保护；约 480 GB 的 USB/exFAT 盘不是安装目标，实装等待该机 120 GB 内置盘清理范围确认。详见[现场检查](../deployment/linux-platform-checks.md)。

## alpha.41 共享 ISO 入口与补齐 52 个 Linux 自动安装（2026-10-27）

手动和自动安装合并到发行版目录下的同一 ISO。选择系统后，`Boot without auto install script` 进入手动安装，`Boot with ...` 选择自动脚本；默认手动、无倒计时。补齐 Rocky 10.2 和 Ubuntu Desktop 26.04，覆盖当前 52 个 Linux 镜像。发布移除 50 个历史 PXE-Auto 别名，目录由 109 个路径减为 59 个，包含另外 6 个 Windows 和 1 个 MemTest86；Linux 的完整 setup、驱动和策略钩子仍保留。

新增两项均在独立 UEFI 虚拟机中完成自动安装及两次硬盘启动，控制器回报 `installed`。实际验证 root/user 密码 SSH、user sudo、root 系统控制台密码登录、CLI 默认启动、128 GB 四分之一档分区、内核锁定、禁用自动更新以及预置 setup 摘要。Rocky 10.2 默认 XFS，运行内核为 `6.12.0-211.16.1.el10_2.0.1.x86_64`；Ubuntu Desktop 26.04 默认 ext4，运行内核为 `7.0.0-14-generic`，保留桌面软件但默认 CLI。

Desktop 26.04 的 live 环境没有 curl，发现/授权客户端改用 Python 标准库 HTTPS，继续验证 CA 并正确处理 HTTP 失败。其 Casper 已屏蔽 `cdrom.mount`，收尾现在保留屏蔽，避免因无法启用 LazyUnmount 而把已完成的安装判为失败。最终安装退出介质时仍有 SQUASHFS/卸载告警，但正常请求重启，随后从硬盘启动并通过检查；没有把这一结果表述为关机日志无告警。

隔离的原生 iVentoy UEFI 网启另验证 CentOS 7.9、Debian 12.8、Ubuntu Server 22.04.3 各自的手动分支和自动分支，以及 Rocky 10.2 自动分支，共 7 项。手动进入原生安装器，自动进入文件系统选择页；这些菜单测试停在写盘前，不等同于七次完整安装。52 份模板、28 份账户配置、54 份 RAID 配置、660 项容量和 220 项文件系统组合，以及 16 项 Kickstart 条件注入检查通过。没有操作 `.235` 或 `.39`，没有新增物理 E610 或 RAID 故障测试。

已清理退役隔离磁盘、过期构建文件和挂载，释放约 170.2 GiB。历史 PXE-Auto 文件原本是硬链接，移除别名主要整理菜单，不会再释放 50 份 ISO 数据空间。当前 ISO、tools 软件、恢复副本、授权和任务历史保留。安装、菜单截图、测试、发布与回退证据保存在中心 `e610-pxe-media-20261023/release41-20261027/`；清理记录为同级 `disk-cleanup-20261027/result.json`。源码见 [PR #15](https://github.com/SkyWalkerAMD/ventoy/pull/15)。

## alpha.40 发行版默认格式与 setup 检查（2026-10-27）

新建 Linux 自动安装默认使用红帽系 XFS、Ubuntu/Debian ext4，保留控制台切换以及历史任务原有格式。普通手动安装由安装器选择格式，setup 不转换分区。新版 setup 检测 RPM 安装脚本的失败并保留失败版本记录，避免仅凭包数据库存在就报告成功。

`.235` 的 Rocky 10 手动安装后 setup 实测：主机名 `s4-2495x1`、root/user SSH 密码登录、DHCP、内核锁定和禁用更新均通过；fyhoc 与 fyhocsys-node 0.8.4 可运行，工具文件摘要一致。`sckoct-fyh 1.1.8-1.el10` 自带 Cython 初始化失败，需要提供修正后的软件包；setup 本轮修复负责准确报告失败，不能代替修复该业务软件。真实 RPM/DNF 隔离事务已验证失败识别、重复运行拒绝误报和升级到修正版本后的通过行为。没有新增全部发行版或 E610 实卡验收。

## alpha.39 文件系统选择（2026-10-26）

Linux PXE 自动安装支持 ext4（默认）和 XFS，选择用于根、tmp、var、home；boot 固定 ext4、ESP 固定 FAT32。单盘、硬 RAID 逻辑盘和双盘 RAID1 + LVM 沿用原容量档位。匹配的后台授权任务保留其指定格式，旧任务未指定时兼容 ext4；手动安装和 setup 不转换已有文件系统。

生成配置完成 220 项文件系统/布局/固件组合验证，原 660 项容量和范围检查通过；错误输入、取消、重复领取、授权格式不匹配及实际挂载不符都有回归覆盖。Ubuntu 24.04.3、CentOS 7.9、Debian 13.4.0 的隔离单盘 XFS 安装、两次硬盘启动、各挂载点、账号 SSH、内核锁定、禁用更新和预置 setup 摘要已检查。更多本轮原生安装记录保存在中心 `e610-pxe-media-20261023/manual-update39/qa/`，PR 中列出最终范围。没有重装 `.235`，也没有新增物理 E610 或物理 RAID 故障测试。

## alpha.34 普通手动安装的更新保护（2026-10-26）

用户报告 `.235` 在 Ubuntu 手动安装过程中出现更新问题，改用 PXE 自动安装后正常。核查发现普通入口之前仅预置 setup，首次运行前没有与自动安装相同的保护；安装后检查成功不能证明安装过程中未更新。

现为 Ubuntu Server 增加只包含更新策略的 Subiquity 交互配置：不填写磁盘、账户或网络答案，保留手动页面，提前固定介质内核并阻止收尾阶段的无人值守包升级。安装器自身刷新另行关闭；不用会重新开启该检查的 `interactive-sections: ['*']`。Ubuntu/Debian 在首次硬盘启动前应用和检查持久更新策略，Debian 还在 pkgsel 前保护内核。完整 setup 继续由用户手动执行，预置不等于已改写 SSH、账户或网络。

隔离 UEFI 虚拟机使用现场成品 ISO，Ubuntu 22.04.3、24.04.3 通过在线软件源、逐页手动选盘/账户、安装完成及正常重启；运行内核分别保持 `5.15.0-78-generic`、`6.8.0-71-generic`。升级日志记录候选包被排除，unattended-upgrades 的 dpkg 日志为空。Debian DVD 12.15.0 用测试专用 preseed 驱动原生安装器，验证提前和完成钩子，硬盘启动后为 `6.1.0-50-amd64`；不把这项测试称为逐页人工操作或在线 mirror 验收。三者均在完整 setup 尚未执行时通过 hold/pin、APT 周期选项及五个更新单元 masked/inactive 检查。

记录位于服务器 `e610-pxe-media-20261023/manual-update34/`。Ubuntu Desktop 的安装前保护和其他版本没有据此扩大为完整验收。发布包已在隔离目录生成；生产仍为 alpha.33，用户确认 `192.168.0.102` 还在使用安装镜像，需等安装完成后再刷新绑定。

## E610 重复入口清理与 Ubuntu 软件检查（2026-10-25）

现有 Linux 镜像覆盖核对为 43 个内置 E610 驱动成品、9 个原生支持版本，加上两个历史重复别名。CentOS 7.9 / Ubuntu 22.04.3 的普通与 E610 命名版本各自为同一 inode。按用户要求移除两个 E610 基础别名及其两个 PXE 自动入口后，现场为 109 个镜像路径、52 个不重复 Linux 基础路径、50 个自动入口。保留普通名称下的驱动适配成品，脚本、驱动、setup、其他原生绑定与历史任务不变；镜像外保留恢复备份。详见[当前清单](../deployment/image-catalog.md)。

清理前等待用户的新一轮 Ubuntu 22.04.3 双盘安装完成；后台回报 installed，并经 SSH 核对 `.235` 的硬件身份、本地 LVM 根文件系统及无安装镜像挂载。用户确认 root 的 KVM 系统控制台和 SSH 登录可用。其随后执行 setup 已安装三个业务软件（含 fyhocsys-node 0.8.3）；APT 仅在补齐依赖时升级三个 GCC 运行库相关包，内核仍为 5.15.0-78，锁定和自动更新禁用均保持。附加网卡仍待 IPv4 租约，系统 PENDING 与软件成功分别记录，见[软件验证范围](../deployment/node-software.md#验证范围)。

证据位于服务器 `e610-pxe-media-20261023/dedup-20261025/`：`plan.json`、`node-installed.json`、`node-policy-audit.json`、`stale-cleanup.json`、`result.json`。本轮未重新执行全量安装或增加 E610 实卡验收。

## alpha.33 容量分区、user/root 登录与软件升级（2026-10-25）

Linux 自动安装改用[统一容量档位](../deployment/pxe-menu.md#默认分区容量alpha33)：EFI 1 GiB、boot 2 GiB 固定，480/512 GB 档的 tmp/swap/var/root 为 5/32/64/128 GiB，home 使用余量。更小容量按半档、四分之一档，大容量继续倍增；RAID1 以较小成员盘计算。单盘使用 GPT 直接分区，双盘保留 RAID1 boot、RAID1 数据及 LVM。容量不足在领取安装授权前停止。

以下 UEFI 隔离完整安装均使用当前成品 ISO 的内核/initrd 和实际生成的 PXE 客户端；双盘按 `r → 1 2 → yes` 操作。安装后核对实际块设备容量、所有挂载点、swap、预置 setup 摘要、内核/更新策略、CLI、后台 installed，以及两次硬盘启动。每项均实际验证 `root / ventoy` 和 `user / ventoy` 的 SSH 密码登录、user sudo、root 系统控制台密码登录；不是仅检查配置文件。

| 系统 | 测试磁盘标称容量 | 布局 | 安装及正常重启 |
| --- | --- | --- | --- |
| Ubuntu Server 24.04.3 | 128 GB | 单盘，四分之一档 | 通过 |
| CentOS 7.9 | 256 GB | 单盘，半档 | 通过 |
| Debian 13.4 | 1.92 TB | 单盘，四倍档 | 通过 |
| Ubuntu Server 22.04.3 | 480 + 512 GB | RAID1 + LVM，基准档 | 通过 |
| Rocky 8.10 | 960 GB + 1.024 TB | RAID1 + LVM，两倍档 | 通过 |
| Debian 12.15 | 128 + 256 GB | RAID1 + LVM，四分之一档 | 通过 |

本轮检查 660 个容量/模板/固件组合及档位边界、不同容量成员、错误配置拒绝、user/root 密码策略和旧 admin 标记迁移。完整安装是上述六个隔离代表版本；未增加物理 PXE、E610 实卡或拔盘故障切换验收。Debian 分区使用原生十进制 MB 配方，实际对齐大小可相差数 MiB。

物理 `.235` 保留 Ubuntu 24.04.3 的现有磁盘布局，更新预置 setup 后直接执行 `./ventoy-linux-setup.run`。旧 admin 及其文件保留，新增 user；外部 user SSH 和本机 root/user 密码认证均通过。工具从中心目录自动选择 DEB，将 `fyhocsys-node 0.8.2-1` 升级为 `0.8.3-1`，其他两项业务软件保留版本；`ipmitool-IPMITOOL_1_8_19.tar.gz` 只传输、校验，不解压执行。再次执行没有重复下载或安装未变化的软件，SSH、主机名、DHCP、内核锁定和自动更新禁用检查全部通过。内核仍为 `6.8.0-71-generic`，启动 ID 与 fstab 摘要均保持不变。

证据保存在服务器 `e610-pxe-media-20261023/storage33-20261025/`：`final-tests.log`、`qa/*/acceptance.json`、`qa/*/console-login.txt`、`node-final-acceptance.json`。BMC 网页凭据与系统 root 账户独立；普通手动安装先使用安装器设定的账户，进入系统后执行预置 setup 才应用统一账户策略。

现场已发布 alpha.33，iVentoy 保持 1.0.47 Pro。发布前确认没有活动任务或网络镜像连接，备份后更新全部 52 个 PXE 自动入口和 54 个普通 Linux 入口；各入口预置包与当前下载一致。统一 setup SHA-256 为 `895ca3556ca1e3497d66e21774b32455e97b576591de15c6cd9c10b5fe5bbc09`。ISO 内容、路径、其他绑定及 tools 软件包保持一致，发布核验为 `deployment.json`，回退备份为 `production-backup-20261025-211637/`。源码与验证见 [PR #7](https://github.com/SkyWalkerAMD/ventoy/pull/7)。

## alpha.28 CentOS 7.9 物理 PXE 网络修复（2026-10-25）

在 `.235` 复现用户的 `r → 1 2 → yes` 失败：Anaconda 读取第二条 Kickstart 网络指令后，创建并激活新连接，先断开正在使用的 PXE 网卡 `eno2`。IPv4 丢失后 iSCSI 安装介质读取超时，随后 `nm_get_all_settings` 和 `NetworkManager.GetDevices` 报 `GLib.Error: Timeout was reached (24)`。这次错误发生在原生分区安装前，原因不是 RAID 成员校验。

CentOS 7.6、7.9 和 RHEL 7 模板改用 `--no-activate --onboot=yes`：保留 live 安装器的现有连接，同时保存按 MAC 绑定的 DHCP 开机配置。第一条仅含 hostname 的网络指令继续保留，防止 dracut 等待 udev 重命名前的 ethN。用原版 CentOS 7.9 Anaconda 网络初始化函数对比验证：旧配置会调用连接激活，新配置保存 DHCP/ONBOOT 而不替换 live 连接。Go 测试与 vet、52 份安装模板、28 份账户策略、PXE 动态配置及 54 组 RAID 配置检查通过。

现场已发布 alpha.28，iVentoy 保持 1.0.47 Pro。发布前确认失败安装器退出且物理机关机，关闭旧任务并清理其残留连接；只重启管理端，未重启 iVentoy。52 个自动入口、113 个 ISO 路径、文件指纹和原生绑定一致。备份与发布核验在服务器 `e610-pxe-media-20261023/centos7-physical-20261025/production-backup-20261025-094712/`、`production-alpha28.json`。

修复后的任务 `2200e4c2ad39f80d012c785c` 从 LAN1 → iVentoy → `PXE-Auto → CentOS-7.9-x86_64-DVD-2009-Auto-24282e` 启动，按同样的 `r`、`1 2`、`yes` 完整安装，自行重启进入硬盘系统并回报 `installed`，没有进入 BIOS 或强制复位。首次启动的实际 root/admin 密码 SSH、sudo、DHCP、主机名、CLI、内核及更新策略均通过。两块 HFS480G3H2X069N（Q0Q/Q0R）构成 RAID1 `/boot` 和 RAID1 数据卷，数据卷承载 `vcvg/root`、`vcvg/swap`，两组阵列和两个 EFI 引导成员检查通过。系统为 CentOS Linux 7.9.2009，内核 `3.10.0-1160.el7.x86_64`，系统地址为 `192.168.1.52`。

首次启动和第二次正常重启复查全部通过，证据为同目录 `fixed-boot1.json`、`fixed-boot2.json`；两个启动 ID 不同，第二次启动继续从 CentOS 本地 EFI 入口进入系统，没有失败的 systemd 单元。数据阵列首次同步约 18%，仍在后台，不能计为同步完成或实物拔盘验收。本轮物理网卡是 Intel X710，未增加 E610 实卡验证；CentOS 7.6 和 RHEL 7 仅增加模板与原版函数回归，不扩大为这两个版本的物理实装通过。

## alpha.27 Ubuntu 24.04.3 正常重启与手动 setup（2026-10-25）

修复 Ubuntu Casper 安装完成时 `/cdrom` 仍被 live 根文件系统引用的卸载问题：在成功完成安装钩子后，为安装环境的 `cdrom.mount` 设置 `LazyUnmount=yes`，让系统在正常关机阶段解除挂载。仅接受 Ubuntu、overlay 根和只读 ISO 挂载，写入 `/run` 并回读 systemd 确认；不提前拔出介质、不强制重启，也不写入目标系统的启动配置。对照测试中原版出现 `/cdrom` 卸载失败及 SquashFS I/O 错误，修复后正常重启，未再出现这两类错误。

- **物理 PXE 自动安装**：`.235` 经 LAN1 → iVentoy 1.0.47 Pro → Ubuntu 24.04.3 自动脚本，选择 `r`、`1 2`、`yes`。任务 `bfc55ce64f8f2721a0e9a9ac` 安装完成后自行进入硬盘系统并回报 installed；本轮没有进入 BIOS 或强制复位。双盘 RAID1 + LVM、两盘 EFI 文件、root/admin 密码 SSH、sudo、主机名、DHCP、CLI、内核及更新策略检查通过。首次阵列同步仍在后台，不扩大为拔盘验收。
- **普通 ISO 手动安装**：隔离网络命名空间内使用真实 iVentoy 1.0.47 和与生产相同的 Ubuntu ISO；没有自动答案或测试 Kickstart。逐页操作原生安装器，点击 Reboot Now 后自行从新硬盘启动。点击至新系统启动约 134 秒，没有外部复位。启动后先确认 `/root/ventoy-linux-setup.run` 只是预置、没有应用配置，随后执行 setup，再正常重启并核对实际登录和所有策略。
- **手动 setup 补充修复**：Ubuntu 24.04 原有 SSH socket 已启用时保留该启动方式，避免额外启用 ssh.service、创建别名后遗留旧监听进程。已回退隔离机的账户/SSH 初始状态，验证新包首次应用、实际 root/admin SSH、管理员 sudo，以及再次重启后检查通过，始终只有一个 SSH 监听进程。
- **预置包更新**：可以刷新 ISO 中尚未使用的旧托管 setup，但必须同时匹配 PRELOADED_ONLY 标记、原 SHA-256 记录及实际文件内容，且不存在已应用状态。保留旧包备份；用户修改、未标记或已应用的同名文件不替换。

两条路径的运行内核均为 `6.8.0-71-generic`。手动测试是隔离虚拟机，自动测试是 Intel X710 物理机；本轮没有 E610 实卡，也没有扩大为所有 Ubuntu 版本或 HWE 内核已通过。Go 测试/vet、52 份安装模板、28 份账户策略、54 组 RAID 配置，以及安装收尾、预置升级保护和 SSH 启动回归通过。

证据在服务器 `e610-pxe-media-20261023/reboot-qa/`：`physical235/normal-reboot-proof.json`、`physical235/ubuntu24-raid-boot1.json`、`manual-pxe/manual-first-boot.json`、`manual-pxe/manual-fixed-apply.json`、`manual-pxe/manual-fixed-boot1.json`、`manual-pxe/manual-fixed-boot2.json` 和 `tests27b.log`。修复已合入 main（`d6120fe`），13 项 CI 全部通过。经用户明确授权，确认 `.235` 关机后关闭旧 CentOS 安装任务、清理其残留镜像连接，发布 alpha.27 并刷新 iVentoy。14 个 Ubuntu 普通安装入口已更新预置注入包；52 个自动入口、113 个 ISO 路径及内容指纹保持不变。部署备份为 `production-alpha27-20261025-091952/`，发布核验记录为 `production-alpha27.json`。

用户另报告 `.235` 的 CentOS 7.9 在 Anaconda `networkInitialize → NetworkManager.GetDevices` 超时。该问题与 Ubuntu `/cdrom` 收尾不同，后续诊断、修复与物理复测见上方 alpha.28；旧的隔离验收结果不能替代此次物理流程。

## Ubuntu 24.04.3 实机 PXE 双盘回归（2026-10-24）

用户本次使用 `PXE-Auto` 自动入口，在安装控制台依次输入 `r`、`1 2`、`yes`。这是双盘 RAID1 + LVM 自动安装，不是普通 ISO 手动安装。任务 `e5a6e60e9da47e9d7847d011` 于 `12:09:23Z` 开始安装；Curtin 的分区、目标系统安装和引导步骤均为 SUCCESS。

安装退出时曾显示 `Failed unmounting cdrom.mount - /cdrom`，用户随后进入 BIOS。诊断时退出 BIOS，保留原有硬盘优先顺序，系统从 Ubuntu 硬盘入口正常启动，于 `12:35:01Z` 回报 `installed`。此行属于安装介质卸载阶段，不能单独作为系统安装失败的依据；本次没有据此重新清盘。由于中间进入过 BIOS，本轮不声称已经观察到安装器退出到硬盘启动的连续无人干预过程。

实机为 Intel X710 / UEFI，系统 Ubuntu Server 24.04.3，内核 `6.8.0-71-generic`。Q0Q、Q0R 各自含 1 GiB ESP，两个 RAID1 阵列分别用于 2 GiB `/boot` 和约 444 GiB 数据卷；数据阵列承载 `vcvg/root` 约 442 GiB 与 2 GiB swap。两次启动均通过实际 root/admin 密码 SSH、管理员 sudo、DHCP、主机名、CLI、内核锁定及禁用 APT 自动刷新/无人值守升级检查，后台保持 installed。

首次从 Q0R 的 Ubuntu EFI 项启动（BootCurrent 0001）；另一次正常重启只设置 BootNext，改从 Q0Q 的 EFI 项启动（BootCurrent 0000）。永久 BootOrder 保持不变，两个 ESP 的回退引导文件摘要一致。两组阵列均为 `[2/2] [UU]`；第二次检查数据阵列初次同步约 24.8%，继续在后台进行，不能视为同步已完成。本轮两块盘始终连接，未做实物拔盘或降级运行验证，也不增加 E610 实卡验收结果。

服务器证据位于 `e610-pxe-media-20261023/diagnostic235/ubuntu24-raid-boot1.json`、`ubuntu24-raid-boot2.json`。当前这台机器的系统地址为 `192.168.1.52`，带外地址为 `192.168.1.235`。

## 源码与 E610 Release（2026-10-24）

Ventoy 的 [PR #2](https://github.com/SkyWalkerAMD/ventoy/pull/2) 已合入 main，包含原 PR #1 的工作，13 项 CI 全部通过。E610 的 [PR #6](https://github.com/SkyWalkerAMD-org/E610/pull/6) 也已合入 main。[E610 ISO Kit 6.4.5 r1](https://github.com/SkyWalkerAMD-org/E610/releases/tag/v6.4.5-iso-kit-r1) 已正式发布，7 个附件的 GitHub SHA-256 与本地逐项一致。该包包含驱动、制作工具及验证记录，需要自行提供原版 ISO，不包含完整操作系统镜像。

## alpha.25 E610 原生 ISO 注入（2026-10-24 已发布）

本轮按所有库存 Linux 镜像核对启动内核：43 个原版需补充 E610，9 个原版的启动驱动已覆盖 E610，另有 2 个历史 E610 专用版本。制作 41 个新适配成品，并更新既有 CentOS 7.9 / Ubuntu 22.04.3 专用版本，不另加重复版本菜单。旧 Ubuntu 22.04.3 的 HWE 6.2 启动路径尚缺驱动，旧专用镜像的手动安装持久化也不能仅凭文件名视为通过。

驱动直接进入 ISO 的启动 initramfs；通过 Anaconda、Debian、Subiquity、Ubiquity 原生安装收尾钩子写入目标系统并重建 initramfs。普通手动入口与 PXE-Auto 已使用同一份成品；手动安装完成不需要先联网下载 E610 驱动。通用 `/root/ventoy-linux-setup.run` 仍按用户要求预置后手动执行，驱动持久化不依赖执行该配置工具。

43 个独立 ISO 已按最终配置包重建；38 个精确 ABI 模块的加载/卸载检查通过。Debian 文字与 GTK initrd 分别生成模块索引，并保留 `lib -> usr/lib` 与原版内置模块信息；Debian 13.4 的文字和图形 UEFI 安装画面、安装环境内 ixgbe 6.4.5 加载检查已通过。9 项归档、合并模块目录与精简 initramfs 回归检查通过，包含 EL10 延迟解出符号链接时的目录冲突回归。完整手动/PXE 安装、目标系统密码 SSH、驱动与策略、再次重启共 86/86 项全部通过，结果按最终 ISO SHA-256 匹配，重制后的镜像不沿用旧版测试结论。手动路径由测试专用答案驱动原生安装器，交付 ISO 不含这些答案；先验证驱动自动持久化，再执行预置 setup。

真实 iVentoy 的隔离网启发现 Ubuntu `/init` 会被启动器替换。现改为原始 `scripts/init-bottom/ORDER` 的唯一 CPIO 记录调用准备脚本，保留其他记录、硬链接及微码。Ubuntu 22.04.3 最终镜像的 GA 5.15.0-78 与 HWE 6.2.0-26、Ubuntu 20.04.3 的 GA 5.4.0-81 均已通过实际 iVentoy UEFI 网启、安装收尾脚本存在及 ixgbe 6.4.5 加载/卸载检查。Ubuntu 20.04 的独立只读模块目录另使用临时 tmpfs/overlay，保留原树并允许 live 环境加载注入模块。Debian 13.4 最终镜像的文字及图形入口也分别通过同样的真实隔离 PXE 检查，内核为 6.12.73+deb13-amd64。

Desktop 原生收尾钩子固定真实工具 PATH，避免 Ubiquity 的兼容 depmod 空实现导致目标模块索引未生成。后续隔离完整安装还发现 Casper DHCP DNS 在进入 live resolved 后丢失，安装 SSH 软件包失败；现按当前默认网卡与 IP 核对早期租约，仅解析字面 DNS 地址供目标 chroot 临时使用，不修改现有全局网络。新增 8 项 DNS 回归及 Desktop 全新手动安装、配置、重启已通过。自动安装另发现 Ubiquity success_command 超出 Linux 单参数长度上限；改为 gzip/base64 传输并限制长度，完整自动安装、SSH、策略与再次硬盘启动均已通过。52 份 Linux 配置和 28 份账户策略通过对应版本解析器及 shell 语法检查。Ubuntu 24.04.3 本地原版另有一个损坏的 linux-firmware 包，已从官方 ISO 的精确范围恢复并核对包 SHA256/介质 MD5，只替换到待验收输出，原版保留；最终输出的全介质 MD5 检查通过。

手动 setup 等待已排队的 cloud-config 完成，避免首次登录过早时 SSH 配置被覆盖，不等待会造成 systemd 顺序循环的 cloud-final；实际密码 SSH 验证还处理 sshd 异步 reload 的短暂过渡，只在应用时最多重试三次，永久拒绝或身份不匹配仍失败。Ubuntu 20.04.3、22.04.3 最终镜像的 PXE 全新安装、驱动、账户、策略与重启已通过；最终逐项结果覆盖全部 43 个成品，公开证据以 `baked-catalog.json` 和 `catalog-evidence.json` 为准。

CentOS 实际 iVentoy 网启发现启动器遗漏追加 CPIO，因此 EL 镜像改为把驱动、索引和安装完成钩子合入原始主 CPIO，保留其余记录和硬链接。另在 Anaconda 切换根目录前写入 live 模块覆盖与索引。CentOS 7.9 最终镜像已通过真实隔离 iVentoy UEFI 网启、原生安装器钩子存在及 ixgbe 6.4.5 实际加载检查。28 个 CentOS / Rocky / RHEL / AlmaLinux 镜像已按此重建，56/56 项完整安装案例通过。EL10 的启动环境另缺少 chroot，已增加使用其 live 根目录自身 loader、库和 chroot 的兼容路径。实际网启还发现 BusyBox cpio 延迟创建符号链接时，新增 `/usr/lib/dracut/hooks` 子文件先建立真实目录，导致原有链接及后续 udev 入口解出失败；现将新增文件写入原始链接的规范目标 `/var/lib/dracut/hooks`，不改变原有链接。CentOS Stream 10 和 Rocky 10.0 的重建成品均通过真实隔离 iVentoy UEFI 网启、进入 Anaconda、原生钩子存在及驱动加载/卸载，完整安装按各自新哈希验收通过。CentOS Stream 10 另完成真实隔离 UEFI PXE → iVentoy ISO/自动脚本 → 自动安装 → 两次硬盘启动，控制器回报 installed。

构建代码与公开成品摘要位于 [E610 PR #6](https://github.com/SkyWalkerAMD-org/E610/pull/6)，本机目录为 `F:\OpenAI\Codex\project\E610\pxe-media-e610`。现场已切换至管理端 alpha.25，iVentoy 保持 1.0.47 Pro，共 113 个路径（61 个基础/工具路径、52 个自动入口）。43 个成品及两个旧 E610 别名替换对应基础路径，全部自动入口核对为相应基础镜像的硬链接；适配路径不再叠加外部手动驱动注入，9 个原生镜像绑定保留。

发布备份为 `/home/ventoy-center/e610-pxe-media-20261023/production-backup-20261024-195208/`，最终验收为同级任务目录 `production-acceptance.json` 与 `production-postcheck.json`。管理页 HTTPS 200、两个服务 active/enabled、专业版状态、52 项启用与绑定、原机器/任务历史及服务配置均复核通过。针对部分旧原版仅 root 可读的权限，将新成品统一为管理端可读；原版权限保留于备份。发布检查曾触发回退，修正了新成品读取权限与预期变化的镜像大小/指纹比较，原版恢复路径已实际验证。最终公共配置包 SHA-256 为 `94e0003aa3c2af38bef405a80a4265a68bc6ba02bb1d99b13ea8b9bc3cfc4c5e`。

`.39` 已换为无 E610 的 X870E / 9950X3D 机器；本轮没有操作其磁盘。当前无 E610 实卡，真实网口探测、链路、DHCP、收发及 Secure Boot 信任登记仍须按物理硬件独立验收。

| E610 适配家族 | 成品数 | 原生手动安装路径 | 生成的 PXE 自动安装配置 |
| --- | ---: | ---: | ---: |
| AlmaLinux | 2 | 2/2 通过 | 2/2 通过 |
| CentOS | 8 | 8/8 通过 | 8/8 通过 |
| Debian | 7 | 7/7 通过 | 7/7 通过 |
| RHEL | 8 | 8/8 通过 | 8/8 通过 |
| Rocky | 10 | 10/10 通过 | 10/10 通过 |
| Ubuntu | 8 | 8/8 通过 | 8/8 通过 |
| 合计 | 43 | 43/43 通过 | 43/43 通过 |

Ubuntu 24.04.3 的完整安装验收使用普通 GA 6.8.0-71 入口。早期测试答案误选 HWE 6.14.0-27，而该 ISO 的离线 pool 不带对应内核 DEB；修正测试选择后重跑通过，没有改动 ISO 或驱动，不计为 HWE 目标系统验收。Ubuntu Desktop 22.04.4 的自动路径采用 CLI 启动，但不删除镜像中的全部桌面软件；无桌面装机仍优先选择 Server。

## alpha.24 双盘 RAID1 + LVM 与手动配置包预置（2026-10-23 发布，10-24 实机回归）

现场已发布 `0.3.0-alpha.24`，iVentoy 为 1.0.47 Pro。39 个 CLI 自动入口统一支持本机选盘：一块可用内置盘直接安装；多盘选盘号、输入 `yes`，或输入 `r`、两个盘号和 `yes`，清空两盘后重建 RAID1 + LVM。无需先到管理端登记目标盘。原有单盘保护保留；双盘重建必须完整覆盖旧 LVM/MD 成员，涉及未选盘、缺失成员、挂载或交换空间时停止。

原 29 个入口已更新，新增 AlmaLinux 8.10 / 9.5，RHEL 7.6 / 7.9、8.0 / 8.1 / 8.6 / 8.10、9.2 / 9.4。下面记录本轮隔离安装器实装结果；QEMU 使用原 ISO 的内核/initrd 和实际生成的 PXE 客户端，不冒充物理 BIOS 到 iVentoy 的完整网启验收。

| 双盘实装系统 | 完整镜像启动、SSH、CLI、DHCP、内核/更新策略 | 每个成员独立 UEFI 启动 |
| --- | --- | --- |
| Ubuntu Server 22.04.3 | 通过 | 两盘分别通过 |
| Debian 13.4.0 DVD | 通过 | 两盘分别通过 |
| CentOS 7.9 | 通过 | 两盘分别通过 |
| AlmaLinux 8.10 | 通过 | 两盘分别通过 |
| AlmaLinux 9.5 | 通过 | 本轮未单独测试 |
| RHEL 7.9 / 8.10 / 9.4 | 三个版本分别通过 | 本轮未单独测试 |

每个安装测试另带一块未选磁盘，完整摘要保持不变。独立成员启动使用新 UEFI 变量和只含一个成员的临时副本。最终安装后校验按实际分区父盘查找成员和 ESP，兼容 Anaconda 将第二盘 ESP 放在不同分区号的布局；AlmaLinux 8.10、9.5、RHEL 8.10、9.4 已用最终修正重新安装通过。旧 LVM/MD 范围、隐藏/缺失/第三方成员、重复序列号及占用保护检查通过；Linux Go 测试、44 份模板、24 份账户配置、46 个 RAID profile/固件组合解析通过。其他版本不能据此列为本轮逐版本实装通过。

54 个普通 Linux ISO 已绑定手动安装配置包预置注入，在新系统中放入 `/root/ventoy-linux-setup.run`，由用户安装后手动执行。Ubuntu Server 20.04.3、22.04.3、CentOS 7.9、Debian 13.4.0 的原生安装收尾及硬盘启动已确认文件摘要、权限和 `PRELOADED_ONLY`，并确认没有自动执行 setup、创建 admin 或应用网络/更新策略。包内完整配置的六系统运行与重启验收见下方 alpha.23。原始 ISO 文件本身未改写；其他介质启动不携带此注入。Desktop 仅有钩子结构检查，不计为本轮预置实装通过。

生产备份为 `/home/ventoy-center/qa-raid25/production-backup-20261023-201242/`，验收记录为 `production-acceptance.json`。发布后目录为 100 个路径（61 个基础/工具镜像、39 个自动入口），全部绑定及全局参数复核通过。39 个自动入口与 54 个手动预置绑定分别维护，所有已有 ISO 的 inode、大小和修改时间均保留。配置包摘要为 `1013b7baea3261ae24640d6809ae1d434ae40b3bb9f3da38703573cb5ba7fca3`。

2026-10-24，`.235` 完成真实 LAN1 → iVentoy 1.0.47 → PXE-Auto → Ubuntu 22.04.3 → 自动脚本的双盘实装。在安装控制台输入 `r`、`1 2`、`yes`，没有预建目标盘任务；系统自动生成 `85f62946f7d698811a2a1ccc` 并回报 `installed`。安装前确认超时的上一轮没有写盘。此次按授权清理 Q0Q 上的旧单盘 LVM，将 `BDD9N5327I2709Q0Q`、`BDD9N5327I2709Q0R` 重建为两盘各 1 GiB ESP、2 GiB RAID1 `/boot`、约 444 GiB RAID1 数据卷，再建 `vcvg/root` 约 442 GiB 与 2 GiB swap。

首次硬盘启动和另一次正常重启均通过实际 `root / ventoy`、`admin / ventoy` 密码 SSH 与 sudo 验证。主机名保留 `VC-C7-235`，`eno2` DHCP 地址为 `192.168.1.52`，内核为 `5.15.0-78-generic`；CLI、两盘 EFI 文件、RAID/LVM、内核 hold、APT 周期配置和五项自动更新服务的 masked/inactive 状态均通过，没有失败服务。安装结束曾显示 `/cdrom` 卸载失败，随后自行重启进入硬盘系统，无需额外回车、强制断电或手动调整启动顺序。

第二次启动时两组阵列均为 `[UU]`，数据阵列首次同步约 12.6%，继续在后台进行；这不表示首次同步已经完成。本轮没有实物拔盘，不能把隔离单成员启动结果扩大为该物理机拔盘验收。实机证据为服务器 `qa-raid25/physical235/boot1.json`、`boot2.json`；升级、8 组隔离双盘实装、8 次独立成员启动、4 组手动预置与实机结果统一归档到 `qa-raid25/acceptance-evidence/alpha24-acceptance-evidence.tar.gz`，SHA-256：`b204ce4009e55017004cd7daf1b6feed163ca34704d82aefa358f9e81bd5b907`。

E610 其他 Linux 安装环境的广泛驱动注入仍后置，现有两种已验证 E610 ISO 保留。39 个入口代表已发布的配置范围，不能等同于全部库存镜像、全部硬件均已实装通过。

## iVentoy 1.0.47 专业版升级（2026-10-23）

现场已从 1.0.45 Pro 升级到 **1.0.47 Pro**，程序继续位于 `/home/ventoy-center/iventoy`。使用用户提供的专业版安装包，SHA-256 为 `419dcd591e936f157524729e3ce1589c0821ee02f13e60914d2479691d895ea6`。新版本运行状态为专业版，当前启动日志确认授权校验成功；原授权文件摘要一致。

升级前确认 `.235` 已关机，无活动安装任务，并在用户明确授权后清理系统地址 `.52` 的残留镜像连接。按[官方旧版本迁移方式](https://www.iventoy.com/en/doc_update.html)使用全新程序目录，迁移配置、授权、自定义脚本和镜像目录。90 个镜像路径及全部原有脚本/注入绑定、全局参数逐项核对一致；ISO 的设备号、inode、大小和修改时间，以及自定义脚本摘要和所有者均未改变。没有操作客户端磁盘。

本机浏览器确认 `http://192.168.1.2:26000` 显示 **iVentoy Pro / Version 1.0.47**，原生服务 running；`https://192.168.1.2:26080` HTTP 200。程序升级时管理端为 `0.3.0-alpha.23`；随后另行发布 alpha.24，双盘安装与手动配置包预置的结果记录在上一节。

备份位于服务器 `/home/ventoy-center/upgrade-iventoy-1.0.47/switch-20261023-200216/`，验收记录为同级 `upgrade-acceptance.json`。升级校验兼容 1.0.47 移除旧授权接口字段的变化，回退恢复旧版也已实际验证。

## alpha.23 普通 ISO 安装后完整配置（2026-10-23）

为所有现有 Linux 家族增加同一手动安装配置入口：Ubuntu、Debian、CentOS、Rocky、AlmaLinux、RHEL。管理端提供经过认证的 `ventoy-linux-setup.run` 下载，包含 SSH、主机名、DHCP、内核锁定、关闭包管理器自动更新、CLI 与 E610 驱动处理。安装后执行一次，后续每次启动自动继续与检查。普通 ISO 安装器和原始镜像不改写，具体用法及边界见 [手动安装完整配置](../deployment/manual-linux.md)。

现场已发布 `0.3.0-alpha.23`；完整包下载摘要为 `a16346f9e1aee85e1c7db9a29ae798e6cddd130d3a81e7a046c34c076c885a9e`。发布备份：`qa-alpha23-manual/production-backup-20261023-161513`。实际认证下载与测试产物逐字节一致；29 个自动入口状态和原脚本摘要保持不变，iVentoy 未重启。

本轮在先前安装结果的独立 qcow2 副本中，撤销原 root SSH / 内核更新策略后执行完整包；没有重装或改动 `.39`、`.235`。下列六个版本通过实际 root/admin 密码 SSH 登录、主机名、IPv4、CLI 与内核/更新策略检查。Ubuntu、Debian 使用新增网卡验证持久 DHCP 和租约，RPM 系统保留已存在的 NetworkManager 配置。

| 系统 | 运行内核 | 手动完整配置 |
| --- | --- | --- |
| Ubuntu Server 22.04.3 | `5.15.0-78-generic` | 配置、重复执行、重启检查通过 |
| Ubuntu Server 24.04.3 | `6.8.0-71-generic` | 同上；永久 MAC 匹配兼容修复 |
| Debian 10.11.0 | `4.19.0-18-amd64` | 同上；ISC dhclient 接口隔离 |
| Debian 13.4.0 | `6.12.73+deb13-amd64` | 同上；dhcpcd 次要接口策略 |
| CentOS 7.9 | `3.10.0-1160.el7.x86_64` | 同上；Python 2 与旧 systemd 兼容 |
| Rocky 8.10 | `4.18.0-553.el8_10.x86_64` | 同上；platform-python、SELinux enforcing |

其他版本复用相应 Linux 家族实现，不把以上六个版本的运行验证扩大成所有版本的新实装验收。AlmaLinux / RHEL 的此次完整配置包尚未逐版本运行验收。自动安装的此前结果仍见 alpha.20–22，不与本轮手动配置测试混用。

E610 组件已提交到 [E610 PR #5](https://github.com/SkyWalkerAMD-org/E610/pull/5)，自动检查通过。固定引用多系统 r2 离线包，并为没有精确模块的内核提供按当前头文件构建路径。三个真实 legacy 驱动包和源码解包、危险路径拒绝及 MOK 待处理分支已验证；本轮虚拟机没有 E610 实体网卡，源码构建路径不作为所有未知内核硬件验收。原版安装器缺少驱动时仍需 E610 适配介质。

验证记录在服务器 `/home/ventoy-center/qa-alpha23-manual/`：六台隔离系统的 `final-apply.log`、`final-reboot-evidence.log`，以及 `linux-go-tests-final.log`。发布仅更新管理端下载功能和固定驱动包，iVentoy 服务、原始 ISO、29 个 PXE 绑定及已生成的安装脚本保持原状。

归档为服务器 `acceptance-evidence.tar.gz`，本地 `.local/alpha23-manual-evidence.tar.gz`。发布后管理端 active、iVentoy HTTP 200、未登录下载返回 401；六台临时虚拟机均已正常关机。

## alpha.22 PXE 本机选盘、root SSH 与初始化工具（2026-10-23）

现场已发布 `0.3.0-alpha.22`，29 个 Linux 自动安装入口均已更新并启用，策略为 `single-or-console`。只有一块可用内置盘时直接安装；多盘在 PXE 控制台选择目标盘、输入 `yes` 后自动执行，不再要求到管理端指定磁盘。现有 LVM / RAID、挂载盘和无法明确识别的磁盘仍须先处理，不能据此宣称任意存储布局均可自动清理。

配置统一密码的 Ubuntu / Debian 新安装启用 root SSH 密码登录，现场账户为 `admin / ventoy` 和 `root / ventoy`。安装时设置主机名与 DHCP，默认 CLI，保留内核锁定和禁用自动更新策略，并预置用户提供的 `safe-server-init`。初始化工具只为未配置网卡补充 DHCP，保留原脚本的既有配置保护及后端激活限制。

本轮使用原始 ISO 与实际生成的 PXE 客户端，在隔离 QEMU/KVM UEFI 的两块测试盘上完成下列验证：选择第二块盘、输入 `yes` 后完成自动安装，两次硬盘启动、管理员 SSH / sudo、主机名、DHCP、CLI、内核与自动更新策略均通过；第一块保留盘完整摘要不变。Ubuntu / Debian 另实测了两次 root 密码 SSH 登录。初始化工具在安装后执行了版本、hostname 和网络预览检查，没有把预览宣称为新增网口实际取得租约。

| 系统 | 结果 | 安装任务 |
| --- | --- | --- |
| Ubuntu Server 22.04.3 | 两次启动通过 | `d6699b1ae9e2f55b3c879464` |
| Ubuntu Server 24.04.3 | 两次启动通过 | `a3992093546761ae1d1a8083` |
| Debian DVD 10.11.0 | 两次启动通过 | `fd3591618204d12d1c0673f5` |
| Debian DVD 13.4.0 | 两次启动通过 | `bf4cc4f4f8d638203325df49` |
| CentOS 7.9 | 两次启动通过；root SSH 策略不变 | `c2205853981eca5082dd4dd4` |

Debian 回归修复了精简安装器缺少 `stty` / `chvt`、以及本机选盘错误占用 cdebconf 通道造成的等待。新增回归检查确认原有配置传递通道保持可用。Windows / Linux Go 测试、Go vet、34 份 Linux 安装模板、19 个账户策略及 PXE 客户端行为检查通过。

发布备份为服务器 `qa-alpha22/production-backup-20261023-135701`，原生绑定备份为 `native-backup-20261023-135759`。发布前确认无活动安装或网络镜像连接；89 个镜像路径保留，29 项绑定已复核，原版 ISO 内容及全局设置未改变。随后在 `.235` 完成 Ubuntu 22.04.3 的真实 LAN1 PXE 回归：从通用入口选择系统和脚本，在本机选择 Q0Q 并输入 `yes`，未预建目标盘任务，后台自动生成 `e9e59c6742e87433ac5978e9` 并回报 `installed`。两次硬盘启动均实测 `admin / ventoy` 与 `root / ventoy` 的密码 SSH 登录；主机名 `VC-C7-235`、DHCP 地址 `192.168.1.52`、内核 `5.15.0-78-generic`、CLI、更新策略及 Q0R 空盘检查通过，无失败服务。第一次重启阶段曾显示 `/cdrom` 卸载失败，随后已从硬盘启动；没有执行强制断电或手动调整启动顺序。物理结果单独保存，不扩大其他版本的物理验收范围。

验收证据保存在服务器 `qa-alpha22/acceptance-evidence.tar.gz`，本地为 `.local/alpha22-acceptance-evidence.tar.gz`；其中分别记录隔离虚拟机和 `.235` 两次启动结果，不含控制器令牌或私钥。

**普通 ISO 手动安装不自动获得这些配置。** 原版安装器仍采用其默认账户、SSH、主机名和网络设置；管理端现有手动配置脚本仅负责内核锁定和关闭自动更新，需要在安装后执行。管理端升级也不会自动修改已经安装的系统。

## 2026-10-23 现场问题修复与镜像清理

`.235` 已按用户授权清理 Q0Q、Q0R 共同组成的旧 Rocky LVM；通过真实 LAN1 PXE 选择 Ubuntu 22.04.3 和自动安装脚本后，预设任务自动将系统安装到 Q0Q，Q0R 保持无分区空盘。任务 `7a69aabc4a4f150a6924404a` 回报 `installed`，两次硬盘启动和 SSH 验收通过：系统地址 `192.168.1.52`、根分区 `/dev/sda2`、内核 `5.15.0-78-generic`，管理员 `admin` 和 root 初始密码符合用户设定。APT 五项 Periodic 设置均为 0，五个自动更新服务/计时器均 masked 且 inactive，没有失败服务。证据保存在目标机 `/var/log/ventoy-center-acceptance/boot1.json`、`boot2.json`，并已下载到本地工作区 `.local/`。

同时移除了六个已取消任务的镜像、脚本和空目录，入口数 86 → 80；60 个基础镜像、20 个有效自动安装入口和 E610 成功镜像保留。随后完成 9 个新增库存 CLI 版本验收并发布 alpha.21，当前为 89 个路径（60 个基础镜像、29 个自动入口）。`ventoy-center/` 下仅保留 `PXE-Auto/`。详见[镜像清单](../deployment/image-catalog.md)。

按用户最新要求，默认自动安装统一为无 GUI 的 CLI 环境。已停止 Desktop 自动安装测试并将两个桌面版从发布清单剔除；原版 Desktop ISO 保留手动使用。Ubuntu Server、Debian 基础环境及 CentOS / Rocky 最小化安装显式设置 `multi-user.target`。`.235` 已确认没有桌面会话文件，并应用 CLI 启动目标。

## alpha.21 库存 CLI 扩展及发布

此处记录 alpha.21 发布时的状态，现场随后已升级 alpha.22。29 个自动入口均启用，按 CentOS 5、Rocky 5、Debian 7、Ubuntu Server 12 分布，其中包含 CentOS 与 Ubuntu 各一个 E610 版本。现场全部 Ubuntu Server / Debian DVD 镜像均有入口；默认菜单不包含 Desktop。当时采用单盘自动安装、多盘须预设目标盘的规则。普通 ISO 手动安装不自动应用这些模板和更新策略。

新增下列 9 个库存版本在隔离 QEMU/KVM UEFI 中使用原始 ISO、实际生成的 PXE 客户端完成无人值守安装和两次硬盘启动；`admin` SSH / sudo、后台 `installed` 回报、内核锁定、APT 五项 Periodic 设置为 0、五个更新单元 masked / inactive 均通过，无失败服务。随后增加一次已安装系统启动，检查没有桌面会话和显示管理器，执行与新模板相同的 `systemctl set-default multi-user.target` 并复核更新策略。该补充检查不冒充使用最终 CLI 默认值重新做了一轮完整安装。

| 新增 CLI 镜像 | 两次启动确认的内核 | 结果 |
| --- | --- | --- |
| Debian DVD 10.11.0 | `4.19.0-18-amd64` | 通过 |
| Debian DVD 11.4.0 | `5.10.0-16-amd64` | 通过 |
| Debian DVD 12.5.0 | `6.1.0-18-amd64` | 通过 |
| Debian DVD 13.4.0 | `6.12.73+deb13-amd64` | 通过 |
| Ubuntu Server 20.04.3 | `5.4.0-81-generic` | 通过 |
| Ubuntu Server 24.04 | `6.8.0-31-generic` | 通过 |
| Ubuntu Server 24.10 | `6.11.0-8-generic` | 通过 |
| Ubuntu Server 25.04 | `6.14.0-15-generic` | 通过 |
| Ubuntu Server 26.04 | `7.0.0-14-generic` | 通过 |

与 alpha.20 合计 27 个标准 ISO 完成隔离自动安装与两次启动；两个 E610 版本另有物理机结果。这些隔离检查验证安装器和配置，不替代其他物理机 BIOS、网卡驱动及 iVentoy 介质传输验收。`.235` 的 Ubuntu 22.04.3 本轮真实 PXE 结果与虚拟机结果分开保存。

此次修复包括 Ubuntu 20.04 的 Python / PyYAML 兼容、从介质包读取内核版本、Debian 10/11 精简安装环境缺少工具、DVD 安装错误访问旧软件源，以及 PXE 控制台中文错误无法显示的问题。Linux / Windows Go 回归、34 份 Linux 安装模板语法、19 个 Linux profile 双账户策略通过；其中 Desktop 两个 profile 仅结构测试，不计为自动安装验收。

生产发布前备份位于 `/home/ventoy-center/qa-alpha21/production-backup-20261023-121301`，原生 iVentoy 绑定备份位于 `native-backup-20261023-121348`。用户明确批准清理 `.235` 三条残留 iSCSI 连接并短暂刷新服务；已核对客户端从硬盘运行且不使用网络镜像。发布后 29 项绑定与文件摘要、全局设置、无 Desktop 自动入口、管理端 active 和 iVentoy running 均通过。验收归档为服务器 `qa-alpha21/acceptance-evidence.tar.gz`，本地 `.local/alpha21-acceptance-evidence.tar.gz`。

## alpha.20 验收及历史记录

以下为 2026-10-23 alpha.20 发布时的记录，现场随后已升级 alpha.21。服务部署在现有 Rocky Linux 9.8 服务器上。当时通用单盘自动安装流程扩展到 CentOS、Rocky、Debian 和 Ubuntu Server 22.04 / 24.04。以下分别记录当轮隔离虚拟机安装和此前物理机验收，不混用两类结果。本阶段只做直推装机，未修改 sckocstp / fyhocsys，也未开启装机后接入。

alpha.20 按优先顺序完成了六个规划 Ubuntu Server 版本、三个 Debian DVD 版本，以及其余九个 CentOS / Rocky 版本的隔离自动安装、两次硬盘启动、管理员登录、内核锁定和关闭自动更新验证，共 18 个标准版本。Debian 不再依赖 Python 或控制台选盘；安装器自动领取本机配置、完成分区并在首次启动后回报。Ubuntu / Debian 安装后的 APT 自动刷新和无人值守升级均在运行系统中复核，不仅检查模板文字。

现场已准备用户规划的 18 个标准版本及两个保留的 E610 版本，共 20 个有明确系统版本名称的 PXE 自动安装入口。入口均为 `single-internal`：选择版本和自动安装脚本后，一块可用内置盘直接安装；多盘停止，须预先指定目标盘并授权。现有 LVM / 软件 RAID、已挂载盘和未知连接保护继续生效。管理员为 `admin`，管理员和 root 初始密码沿用用户指定的 `ventoy`。

本轮修复覆盖 Debian 分区问题尚未注册、Debian 13 首启 DHCP 时序、旧 Python 的 UTF-8 配置读取、安装器内存盘误计入多盘，以及 Ubuntu / Anaconda 目标根目录中安装介质标记的识别。Windows / Linux Go 回归、28 份安装模板、14 个账户策略模板和实际生成的 PXE 客户端模拟检查通过。测试虚拟机仅使用新建 qcow2 磁盘，未重装 `.39` 和 `.235`。

部署和隔离验收证据位于服务器 `/home/ventoy-center/qa-alpha20/`。iVentoy 仍为 1.0.45 Pro；镜像目录共 86 个路径，20 个自动脚本关联、配套注入文件、默认脚本编号 1 和脚本超时 0 已逐项核对。全局默认镜像为空、全局倒计时为 0；原版镜像及其他入口参数保留。普通 ISO 手动安装仍需另行应用更新策略。

alpha.19 首先按用户选择将 Ubuntu 流程改为“PXE 选择系统 → 选择自动安装脚本 → 自动安装”：一块可用内置盘时直接安装，不再选盘或输入 `yes`；多盘或连接位置不明时停止，须先指定目标盘并授权对应任务。暂不可用的第二块内置盘仍计入多盘，USB / 可移除介质不作为自动安装目标。既有 LVM / 软件 RAID 保护保留，预先指定的有效任务仍可用于多盘机器。管理员 `admin`、管理员/root 密码及内核锁定、关闭 APT 自动刷新和无人值守升级策略沿用原配置。

本轮 Windows / Linux Go 回归、Go vet、28 份 Linux 安装模板和 14 个账户策略模板检查通过；客户端模拟覆盖无终端输入、单盘、多盘、USB、未知连接、硬件变化和规则不一致，Linux 实际 PTY 兼容检查通过。三个现有入口（Ubuntu 22.04.3 原版、22.04.3 E610、24.04.3）已重新准备并启用，iVentoy 已刷新；脚本选择超时改为 `0`，等待用户选择脚本。全局默认镜像为空、系统倒计时为 `0`；69 个镜像路径、三个入口关联及全局配置核对保留。此轮未重装物理机，不增加完整实装验收数量。部署备份和检查记录位于服务器 `/home/ventoy-center/qa-alpha19/`，管理端备份目录为 `backup-20261023-074119`。

alpha.18 将后续 Linux 安装的管理员统一为 `admin`，沿用已配置的管理员/root 初始密码；既有任务和已安装机器保持原账户。Ubuntu 使用 `autoinstall.user-data.users` 避免保留用户名限制，Debian 在目标系统 late-command 中迁移安装账户，其他模板直接创建。Ubuntu 22.04.3 原生安装器 identity 读取及 cloud-init schema 检查、隔离目标文件系统的 admin 创建/sudo/root su 认证通过；Debian 账户迁移及已有 admin 时中止检查通过。Go 回归、28 份 Linux 模板、14 个模板的双账户配置与 Linux PTY 检查通过。PXE 清盘改为核对选盘后输入 `yes`，`no` / `q` 取消，空回车不确认。此次配置更新不计为新的物理安装验收。

alpha.18 当时已部署管理服务和三个 PXE 入口文件，但因 `192.168.1.52` 仍使用普通 Rocky 8.10 ISO，按用户要求推迟刷新。2026-10-23 再次确认无未完成任务、无网络镜像传输连接后，随 alpha.19 更新完成刷新。alpha.18 备份仍保留在服务器 `/home/ventoy-center/qa-alpha18/backup-20261019-152540`。

用户在此次更新前再次从 `.39` 的 E610 Ubuntu 22.04.3 入口确认安装，任务 `51eadeed98a6b1bdd3a1d726` 于 `07:02:19Z` 开始，`07:07:41Z` 回报 `installed`。重启时曾显示 `/cdrom` 卸载失败，但随后正常从 `/dev/sda2` 启动；SSH 核对 E610 地址 `192.168.1.46`、ixgbe 6.4.5、内核 `5.15.0-78-generic` 保留和三个自动更新单元 masked 均通过，无失败服务。这次任务的管理员仍是 `deployadmin`。

alpha.17 增加服务器统一 Linux 初始密码策略，覆盖现有 PXE 入口新发出的任务和新建指定机器任务，管理员及 root 使用配置中的密码哈希；现有已发出任务保持快照。现场 3 个 PXE 入口已重新生成并核对 iVentoy 关联。28 份 Linux 模板解析、14 个系统模板的双账户策略、Go 回归及 Linux PTY 连续输入检查通过。`.39` 再次网启时在清盘确认不匹配处停止，未创建新任务；已恢复原有 Ubuntu 本地启动，并同步用户指定的管理员/root 密码，实际 `sudo` 与 `su` 认证通过，SSH 策略保持不变。清盘确认新增最多三次重试，仍需完整序列号确认。这些配置和输入流程检查不新增系统实装验收项。

alpha.16 新增 E610 适配镜像安装后的驱动验证：在目标系统中核对 ixgbe 与 initramfs 后再完成更新策略及首启回报。Ubuntu 22.04.3 E610 于 `05:35:43Z` 开始安装，`05:41:01Z` 回报 installed；两次本地启动均确认 `5.15.0-78-generic`、ixgbe 6.4.5、E610 DHCP/SSH、模块与 initramfs 哈希、内核 hold、APT 服务屏蔽通过。原有 CentOS LVM 经授权单独清理，通用 LVM/RAID 保护未取消。适配源码和脱敏实机证据维护在独立 E610 仓库，详见 [Ubuntu E610 验收](../deployment/ubuntu22.md#alpha16-e610-pxe-自动安装验收2026-10-19)。

E610 适配及证据已推送为提交 `7d233cb`，见 [E610 草稿 PR #1](https://github.com/SkyWalkerAMD-org/E610/pull/1)，尚未合并主分支。用户随后要求保留当前 E610 测试机的结果，另一台 `.235` 的 Ubuntu 24.04.3 回归稍后继续。

alpha.12 新增可复用的“PXE 自动安装”系统入口：客户端选系统后在控制台核对磁盘并确认清空，自动建立绑定本机的单次安装任务；已有匹配有效授权可直接继续。后台提供准备与停用入口，iVentoy 脚本关联仍需单独配置。Go 回归、安装配置解析及模拟客户端检查通过；alpha.13 已在 `.235` 完成 Ubuntu Server 22.04.3 新流程验收。其他系统的通用菜单尚未实装验收。详见 [PXE 菜单安装](../deployment/pxe-menu.md)。

该入口的首次实机启动遇到 Ubuntu 登录终端冲突，已修复为 tty9 独立输入。随后在 EFI 包下载时遇到 HTTP 403。10 月 19 日读取现场日志发现根因：动态配置保留了 cloud-init 的 `autoinstall:` 外层，而 Subiquity 23.08.1 重新读取 `/autoinstall.yaml` 时需要直接的安装参数，结果使用了默认软件源、LVM 和内核配置。alpha.13 在执行保护脚本之前转换并验证配置格式，回归测试通过。失败任务 `5e3ae5fd9bf14ffb43caf941` 已保存日志并结单，再准备 Q0Q 后重新网启。

本次新任务 `8644357133c0fcd0d05b3772` 由 PXE 控制台确认自动创建，`00:39:45Z` 领取授权，`00:43:53Z` 首次硬盘启动后回报 `installed`。实际安装配置采用指定 HTTPS 软件源、仅 Q0Q 的 EFI / ext4 分区和 `linux-image-5.15.0-78-generic`。两次硬盘启动均确认内核为 `5.15.0-78-generic`，APT 自动刷新关闭、无人值守升级服务屏蔽、SSH / sudo 正常、无失败服务，Q0R 首尾 1 MiB 校验及分区信息保持一致。未手工填写安装器答案或修改安装后的启动顺序。`26080` 无需登记带外地址：正式装机从 BIOS 网卡入口选择系统和目标盘即可，带外只用于这次远程验收。详见 [Ubuntu 验收记录](../deployment/ubuntu22.md#alpha13-通用-pxe-菜单验收2026-10-19)。

alpha.11 新增 Linux 内核锁定与关闭自动更新策略，已部署到现场，管理端和 iVentoy 均正常运行。新任务自动应用；普通 ISO 手动安装后可从“镜像管理”下载脚本执行。Ubuntu 22.04.3 实际镜像的隔离根目录验证了内核固定、新 ABI 拒绝、非内核包候选不受阻和服务屏蔽；Rocky 9.8 隔离根目录验证了持久规则与真实 DNF 解析。10 月 16 日新增 CentOS 7.9 / E610 / MR9540-8i 的 alpha.11 无人值守实装，已通过首次硬盘启动、第二次正常重启、驱动持久化、SSH / sudo、更新策略和完成回报检查；其他三个版本仍按此前验收版本记录。详见 [Linux 更新策略](../deployment/linux-update-policy.md)和 [CentOS 7.9 E610 记录](../deployment/centos7.md#intel-e610-实机适配2026-10-16)。

随后用户在 `.39` 手动重装，已协助恢复网络：应用 r2 驱动、保存 DHCP 自动连接，并处理两张网卡同网段的地址代答及回包问题。正常重启后，E610 的 `.46` 地址、ixgbe 6.4.5、SSH、定向连通性及手动安装后的内核锁定检查均通过。基础适配 ISO 仍需手动执行驱动持久化与更新策略；此修复不增加已验收系统版本数量。

## 已交付的流程

Ubuntu Server 22.04.3 已验收物理 PXE 入口，包括本轮 `.235` 预设 Q0Q 任务后无选盘确认的完整安装。alpha.20 / alpha.21 已部署省去选盘确认的统一 Linux 单内置盘流程，并完成隔离完整安装回归。单盘机器无需提前创建任务，多盘机器必须预先指定目标盘并授权；其他物理硬件组合仍需分别验收。

管理页面可登记机器，按 MAC、目标磁盘序列号和固件模式创建安装任务，授权后生成每台机器独立的安装文件，并在同机 iVentoy 目录准备镜像硬链接与脚本。客户端从网卡进入 iVentoy 后加载安装脚本，安装前领取单次授权，首次从硬盘启动后回报结果。

管理端已有 HTTPS、管理口令、持久任务状态、授权有效期、禁止重复领取、人工失败结单及受管文件清理。iVentoy 的镜像与脚本关联仍通过其原生页面配置；现场辅助操作脚本不等于产品已实现网页一键下发。

## alpha.20 隔离完整安装矩阵

下列 18 个原始 ISO 均使用新建 28 GiB qcow2 磁盘、QEMU/KVM、UEFI 和通用自动安装客户端完成安装；安装器内未补填答案。每个版本均完成两次硬盘启动、`admin` SSH / sudo、更新策略检查和后台 `installed` 回报，两次启动均无失败服务。Ubuntu / Debian 的五个更新 service / timer 均为 masked / inactive；RPM 系列核对内核排除规则和自动更新单元屏蔽。

| 版本 | 两次启动确认的内核 | 结果 |
| --- | --- | --- |
| CentOS 7.9 | `3.10.0-1160.el7.x86_64` | 通过 |
| CentOS Linux 8.5 | `4.18.0-348.el8.x86_64` | 通过 |
| CentOS Stream 9 | `5.14.0-383.el9.x86_64` | 通过 |
| CentOS Stream 10 | `6.12.0-54.el10.x86_64` | 通过 |
| Rocky 8.10 | `4.18.0-553.el8_10.x86_64` | 通过 |
| Rocky 9.2 | `5.14.0-284.11.1.el9_2.x86_64` | 通过 |
| Rocky 9.6 | `5.14.0-570.17.1.el9_6.x86_64` | 通过 |
| Rocky 9.7 | `5.14.0-611.5.1.el9_7.x86_64` | 通过 |
| Rocky 9.8 | `5.14.0-687.10.1.el9_8.0.1.x86_64` | 通过 |
| Debian DVD 12.8.0 | `6.1.0-27-amd64` | 通过 |
| Debian DVD 12.15.0 | `6.1.0-50-amd64` | 通过 |
| Debian DVD 13.0.0 | `6.12.38+deb13-amd64` | 通过 |
| Ubuntu Server 22.04.3 | `5.15.0-78-generic` | 通过 |
| Ubuntu Server 22.04.4 | `5.15.0-94-generic` | 通过 |
| Ubuntu Server 22.04.5 | `5.15.0-119-generic` | 通过 |
| Ubuntu Server 24.04.3 | `6.8.0-71-generic` | 通过 |
| Ubuntu Server 24.04.4 | `6.8.0-100-generic` | 通过 |
| Ubuntu Server 24.04.5 | `6.8.0-139-generic` | 通过 |

本轮从各 ISO 提取原始安装内核 / initrd 并加载生成的菜单脚本，验证安装器、动态授权、自动分区和安装后行为；没有模拟物理 BIOS、网卡固件及 iVentoy 网络介质传输链路。E610 变体保留此前物理验收结果，本轮未重装其物理机。所有测试虚拟机、私有控制器和临时种子服务已停止，正式管理端与 iVentoy 保持运行。

服务器 `qa-alpha20/acceptance-summary.json`、各版本目录的 `acceptance.json` 和 `accept-boot1.log` / `accept-boot2.log` 记录逐项证据；本机副本位于 `.local/alpha20-acceptance/`。正式控制器最终 SHA-256 为 `95db0ce0d802bf5cb1547b3f86f20a384c9840f6a5974d764d7745b36a2a1642`。隔离结果不能扩大为所有硬件、所有架构或所有 Debian / Ubuntu 版本均已通过。

## 客户端物理验收矩阵

以下为用户当前优先清单，共 18 个具体版本的物理机记录。模板可生成、隔离虚拟机完整安装、进入物理安装器和完整物理实装分别记录，不互相替代。

18 个版本的 ISO 现已全部出现在 iVentoy 与管理端列表中。此次新增的 Debian 12.8 / 12.15 / 13.0、Ubuntu Server 22.04.5 / 24.04.4 / 24.04.5 已校验官方 SHA-256、内部版本与 amd64 架构，详见[镜像清单](../deployment/image-catalog.md)。

| 版本 | 当前证据 | 尚需完成 |
| --- | --- | --- |
| CentOS 7.9 | 原版 DVD / X710 已通过完整实装；新增 alpha.11 / E610 适配镜像 / MR9540-8i 自动安装、本地启动、第二次重启、SSH / sudo、内核锁定和完成回报通过 | 其他硬件、Legacy BIOS、批量并发、E610 构建流程产品化 |
| CentOS Linux 8.5 | ISO 已准备；独立模板、版本保护及解析检查通过，镜像发行版 RPM 和软件组已核对 | 完整实装 |
| CentOS Stream 9、10 | ISO 已准备；独立模板、版本保护及解析检查通过，镜像发行版 RPM 和软件组已核对 | 每个 ISO 完整实装 |
| Rocky 8.10 | UEFI 实机自动安装、硬盘启动、登录及完成回报通过；网络等待修复回归通过，initrd 阶段降到 12.733 秒 | 其他硬件、Legacy BIOS、批量并发 |
| Rocky 9.2 | 1.0.45 Pro / alpha.10 全新无人值守实装、自动硬盘启动、控制台 / SSH / sudo、完成回报、旧授权拒绝及保留盘检查通过；网络修复自动应用，第二次正常重启通过 | 其他硬件、Legacy BIOS、批量并发 |
| Rocky 9.6、9.8 | ISO 内部版本、架构及内嵌介质校验通过，共用 Rocky 9 模板 | 每个 ISO 完整实装 |
| Rocky 9.7 | 已通过 PXE 到达安装器；当时因旧磁盘 UUID 重复停止 | 完整实装和首次启动验收 |
| Debian 12.8、12.15、13.0 | ISO 校验并入库，对应大版本的 preseed 模板已实现 | 每个 ISO 完整实装 |
| Ubuntu Server 22.04.3 | alpha.13 / X710 原版镜像及 alpha.16 / E610 适配镜像通用 PXE 菜单选盘后自动实装、UEFI 硬盘启动、SSH / sudo、完成回报、第二次重启、内核锁定和关闭自动更新通过；X710 双盘场景另有保留盘检查 | 其他硬件、Legacy BIOS、批量并发 |
| Ubuntu Server 22.04.4 | ISO 已核对并准备 | 完整实装 |
| Ubuntu Server 24.04.3 | alpha.25 / X710 / UEFI 实机 PXE 双盘 RAID1 + LVM 安装、两盘 EFI 入口分别启动、SSH、DHCP 与策略检查通过 | 安装器到硬盘启动的连续观察、同步完成与实物拔盘、其他硬件 |
| Ubuntu Server 22.04.5、24.04.4、24.04.5 | ISO 校验并入库，对应 LTS 模板已实现 | 每个 ISO 完整实装 |

18 个具体版本中，目前 5 个版本有完整物理安装、硬盘启动与登录证据。CentOS 7.9 的原版 DVD 验收为 alpha.3，E610 适配镜像新增验收为 alpha.11；Rocky 8.10 最近物理回归为 alpha.7，Ubuntu 22.04.3 的 X710 双盘回归为 alpha.24、E610 为 alpha.16，Rocky 9.2 最近物理回归为 alpha.10，Ubuntu 24.04.3 的 X710 双盘回归为 alpha.25。24.04.3 中间进入过 BIOS，连续自动重启仍按上方记录保留边界。本轮隔离安装不增加物理验收数量。详细证据见 [CentOS 7.9](../deployment/centos7.md)、[Rocky 8.10](../deployment/rocky8.md)、[Rocky 9 客户端](../deployment/rocky9-client.md)、[Ubuntu 22.04.3](../deployment/ubuntu22.md)和本页最新实机记录。

此前“无人值守通过”指预先完成机器登记、目标盘清盘授权、存储准备及专属任务绑定后，从正确网启入口自动执行分区、安装、重启和完成回报。Ubuntu 22.04.3 的 alpha.13 还验收了通用入口：无需预建本机任务，在 PXE 控制台选择磁盘并输入完整序列号确认后，剩余安装自动执行。已有 LVM / RAID 仍需独立离线准备；管理端尚未提供经过验收的一键配置 iVentoy 功能。

## 服务端平台

| 平台 | 当前验证范围 |
| --- | --- |
| Rocky 9.8 | 现场同机部署，TLS、管理接口、iVentoy / 外部 DHCP 配合及真实 PXE 已验证 |
| Rocky 8 / 10、Debian 12 / 13、Ubuntu 24.04 / 26.04 | 静态二进制与安装脚本已提供；CI 检查用户空间启动，不等于完整 systemd / PXE 现场验收 |
| Windows 10 / 11 | Windows 二进制与安装脚本已提供；单元测试使用 Windows CI，桌面系统同机 PXE 仍待验收 |

## 当前限制和下一步

1. Ubuntu 22.04.3 的通用入口已有 live-server / UEFI / Intel X710 和 E610 的物理验收。alpha.20 新增 Ubuntu 六个规划版本与 Debian 三个规划版本的隔离完整自动安装回归；其他网卡、物理存储控制器、Legacy BIOS 和批量并发需分别验证。
2. Rocky 8.10 的约 10 分钟早期网络等待修复已通过 2026-10-15 的完整实机回归，initrd 阶段为 12.733 秒。SSH、sudo、完成回报和旧授权拒绝检查通过，保留盘分区表及四项设备签名与基线一致。
3. 当前存储模板只处理按序列号指定的一块普通非 USB 磁盘；已有 LVM / RAID 需要独立的离线准备，不自动拆除跨盘存储。
4. 尚未实现经过验收的 iVentoy 自动配置适配器、批量授权与并发限制、安装失联超时诊断和更细的实时进度。
5. Windows 客户端安装为次要优先级；WinPE 组件与驱动流程尚待完整验证。fyhocsys 接入留到装机阶段完成后另行安排。

后续物理验收继续按具体 ISO、网卡和存储控制器逐项进行；当前物理环境之外的结果不能相互替代。Ubuntu / Debian 仍可能从在线源获取安装依赖；禁用自动更新不等于提供完整离线软件仓库。

服务器重启后的后台访问故障已修复：补齐指定内网和 VPN 来源的运行时、永久防火墙规则，用户已确认管理端与 iVentoy 页面恢复。现场地址分别为 `https://192.168.1.2:26080` 和 `http://192.168.1.2:26000`。

2026-10-15 完成前三项实装后，按用户要求将现场 iVentoy 从 1.0.44 升级到 1.0.45 免费版，再使用用户购买的配套程序包和授权文件注册为 **1.0.45 专业版**。注册页面已确认专业版及原机器码；59 个镜像入口、40 个用户文件、27 项当前页面参数与 Ubuntu 专属任务绑定均核对保留，管理端状态未变，两个服务正常运行且保持开机启动。旧程序与配置可回退。升级当时 CentOS 7.9、Rocky 8.10、Ubuntu 22.04.3 的实装结果基于 1.0.44；10 月 16 日新增的 Rocky 9.2 和 CentOS 7.9 E610 适配镜像完整验收基于 1.0.45 Pro，尚不能代替其他 ISO 的升级后重测，详见[升级记录](../deployment/iventoy-upgrade.md)。

2026-10-16，又按用户要求将实际运行目录改为 `/home/ventoy-center/iventoy`，迁移服务配置、六个任务的准备根目录及 11 处脚本 / 注入包绑定。随后补齐六个计划 ISO，当时共 **65 个 iVentoy 入口（59 个原始镜像 + 6 个已有任务镜像）**。专业版授权、原有参数和绑定均保留；任务状态、凭据与领取记录未变，两个服务正常运行且保持开机启动。目录迁移本身未新增实机安装结果。继续准备测试任务并加入 E610 基础适配 ISO 后，入口曾增加到 70 个；已完成的 `.39` 一次性自动安装 ISO 已从公共菜单归档移除。

随后按用户确认范围保留全部原版 ISO，清理 9 个已结束任务的镜像硬链接、配套脚本和绑定，保留任务历史。清理后为 **61 个入口（59 个原版镜像 + 1 个 E610 基础适配镜像 + 1 个 Rocky 9.6 待测任务入口）**。E610 成功任务 ISO 的私有验收副本保留，无用的临时驱动测试 ISO 及其 Windows 工作区副本已删除。基础镜像、待测任务及全局参数均核对保留，两个服务正常运行。详见[镜像清理记录](../deployment/image-catalog.md#历史测试残留清理2026-10-16)。

alpha.12 新增 Ubuntu 22.04.3 通用 PXE 自动安装入口后，当前共 **62 个入口**。为改测通用 PXE 流程，已撤销 `.235` 的旧 Rocky 9.6 待启动任务授权；其历史记录和镜像入口仍保留，不能再用于自动安装。59 个原始 ISO 和 E610 基础适配 ISO 均保留。

当前属于单机现场验证中的 Alpha 版本，不能把模板覆盖范围或容器启动检查视为所有系统已支持完毕。

## 代码与验证

alpha.10 的本地 Go 测试、vet、服务器 Linux 测试及 28 组 Linux 安装模板解析通过，另执行 Rocky 9 网络 keyfile 的隔离回归。CentOS Linux / Stream 身份、错误小版本和其他发行版的拒绝行为已有 Linux 执行检查。Rocky 9.2 首次任务 `163cc707353d9f9fb2423f63` 因原生 hook 未加载 Kickstart 而停止；重试任务 `e9885756e98fe74fe3d32f38` 同时绑定 Kickstart 和 dracut 兼容包，完成实装后定位了网络等待问题。alpha.10 新任务 `bba89ab191b5bc79c03e62ef` 已通过网络修复的完整新装、首次启动与第二次正常重启，用户空间启动分别为 12.804 秒和 8.470 秒，无失败服务。

Rocky 9.2 本轮验收代码为 `15f8c66`，CI [38841473820](https://github.com/SkyWalkerAMD/ventoy/actions/runs/38841473820) 的 10 项任务全部通过。当时准备的 Rocky 9.6 任务未启动安装，后来为通用 PXE 测试撤销了授权，版本实装仍待验证。

此前 Ubuntu 22.04.3 的验收代码为 `1bbaa20`，CI [38709558965](https://github.com/SkyWalkerAMD/ventoy/actions/runs/38709558965) 的 10 个任务全部通过：Linux / Windows 测试、Linux race、安装模板解析、二进制构建和七种 Linux 用户空间启动检查。Ubuntu 还使用原始 Subiquity 5004 与真实 udev 数据验证了磁盘匹配。

alpha.8 的 Go 测试、Go vet、22 组 Linux 安装模板解析和 JavaScript 语法检查已通过。Ubuntu 注入脚本在 Linux 临时目录中执行验证：缺失或不匹配的 user-data、异常 init 标记、错误系统版本或 MAC 均不会启用无人值守入口；匹配输入会生成预期的 live systemd 配置。实机排查还修复了早期 `/dev/null` 不存在导致的注入失败，加入对应回归，并用实际 iVentoy BusyBox 与原始 initramfs 在隔离目录执行验证。原始 Subiquity 23.08.1 的 UEFI / BIOS 存储模型检查通过，UEFI 完整无人值守实装也已通过；BIOS 模型检查不等于 BIOS 实机验收。

早期代码曾在 `codex/linux-install-verification` 分支以草稿 PR 维护。2026-10-24，[PR #2](https://github.com/SkyWalkerAMD/ventoy/pull/2) 连同 CentOS 工作 [PR #1](https://github.com/SkyWalkerAMD/ventoy/pull/1) 已合入 main；后续验收状态以上方最新记录为准。
