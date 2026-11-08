# 开发记录

## 0.3.0-alpha.58 — 2026-11-08

- Fix setup verification on Ubuntu systems using SSH socket activation: prepare the privilege separation directory safely and accept a healthy listening SSH socket before the first connection starts the daemon.
- Keep pending setup results distinct from failed systemd services; real verification and configuration errors still fail.
- Record the Z790 diagnostic bootstrap's successful manual installation and the limitations found during repeated boot tests.

## 0.3.0-alpha.57 — 2026-11-08

- Stop displaying Ventoy/setup reports on the installed system's boot console
  and login shell. Keep acceptance checks, local reports and center uploads;
  upgrades remove only recognized generated banners and preserve custom content.
- Cover Debian 13.7 DVD and netinst names with the existing Debian 13 installer
  profile, shared manual/automatic ISO hooks and CLI installation policies.

## 0.3.0-alpha.56 — 2026-11-02

- Add an explicit Ubuntu/Debian `--restore-user-login` action: verify an existing
  ordinary user's real SSH password login and sudo before disabling root SSH and
  locking root's console password. Failed changes restore previous login settings.
- Preserve the selected user/sudo policy across setup, upgrades and boot recovery;
  skip the root-password dialog in this mode. New installations still enable root
  login by default. `--check-login` checks the saved policy without changing it.
- Include the optional action in the shared manual and automatic Linux preloads.

## 0.3.0-alpha.55 — 2026-11-02

- Deliver matching sckoct-pub / sckoct-pub-suite / sckoct-fyh RPM and DEB files
  to `/root/ventoy-tools` without installing or upgrading them. Match native
  package identities, including renamed files, and exclude dependency installs.
- Reclassify old software reports and verify copied files separately from installed
  software. Preserve previous excluded-package failures as warnings, without
  claiming repair or suppressing unrelated/unknown installation failures.
- Apply the shared policy to manual setup and all Linux installation preloads.

## 0.3.0-alpha.54 — 2026-11-02

- Verify node credentials with a certificate-pinned center heartbeat instead of
  treating a local connection file and running service as proof of enrollment.
- Recover rejected credentials using the official sckocstp/fyhocsys join command,
  retaining a private backup and atomically installing the new connection.
  Healthy bindings are reused without restarting their service.
- Retry the upstream five-minute same-hardware reinstall window for up to 330
  seconds. Hardware conflicts, unknown identities, invalid keys and network
  failures remain explicit errors; none can silently replace a live binding.
- Apply the shared behavior to manual setup and all Linux installation preloads.
- Attempt enrollment of an installed node even when a different package fails;
  preserve the package error and failed overall result alongside the verified binding.

## 0.3.0-alpha.53 — 2026-11-01

- Pin the official E610 MultiOS r4 archive and retain every vendor component,
  including nested r3/r2 installers, exact ABI checks, and rollback state.
- Support the 46 MB archive without truncation; bound downloads at 64 MiB.
- Delegate E610 installation to the original r4 dispatcher with the installed
  kernel. Preserve native support; unknown kernels stop before changes and
  Secure Boot enrollment remains pending. Keep vendor details in a private log.
- Update all 52 Linux manual/automatic preloads. Separately audit the effective
  boot modules and persistence hooks of the 43 injected and 9 native ISO images.
  No physical E610 traffic test is claimed for this release.

## 0.3.0-alpha.52 — 2026-11-01

- Add a standalone, English `ventoy-setup-upgrade.sh` bridge for packages such
  as alpha.47 that cannot parse upgrade options. Reuse the old package's HTTPS
  trust without executing its installer, verify and back up the runner, then
  apply the new setup while retaining existing passwords.
- Repair executable permission even for an already-current runner saved as
  0600 by file transfer. Refresh its SHA-256 sidecar; reject unsafe sidecars.
- Document the one-time legacy migration separately from normal `--upgrade`.
  The helper is distributed through tools; E610 offline content stays unchanged.
- Validate a real alpha.47 to alpha.51 migration on the Ubuntu 24.04.3 node,
  including full setup, retained hostname/passwords/kernel, and no reboot.

## 0.3.0-alpha.51 — 2026-11-01

- Make setup's network/hostname helper and bundled guide
  English throughout. Run launcher diagnostics in the C locale while retaining
  the caller's locale for the refreshed interactive shell.
- Keep the E610 offline package and driver installers unchanged; their update
  is deferred until the new E610 release is available.
- Publish the same runner for center downloads/tools and all Linux manual/PXE
  preloads. Installed nodes can use `--upgrade` to adopt it without reinstalling.

## 0.3.0-alpha.50 — 2026-11-01

- setup 新增 `--upgrade`：从已信任的中心校验下载、备份并原子替换，然后执行新版完整配置。保留 `--update-setup` 只下载行为，下载失败不执行旧包。
- 已配置节点按包内容摘要迁移新版 SSH、更新策略、服务与工具，修复旧完成标记跳过新策略的问题；检查通过后记录应用版本，失败可重试，同版本正常重启不重复迁移。
- 保留已有节点的账户密码、主机名和已配置网络；仍允许交互主动修改。更新 setup 不重装系统、不升级内核、不自动执行 P95。
- 增加真实启动器更新执行、旧状态迁移、重复运行、失败重试、校验失败拒绝执行及参数边界回归。

## 0.3.0-alpha.49 — 2026-10-31

- 发布回读修正：tools setup 保持 root 所有并授予管理服务组只读权限；发布前完成服务身份的文件审计，失败恢复原文件与权限。
- 发布与回退保存并恢复 iVentoy 原生网络运行状态，避免进程在线但 PXE 仍停在 ready；沿用原接口和地址参数。
- 原生配置独立备份、原子恢复并回读全局设置和全部镜像绑定，防止服务回退打断 config.dat 保存后加载默认设置；配置并发变更和损坏备份均停止发布。
- 新增正式发布、核对与回退工具：隔离生成入口并验证全部预置 setup，活动任务/镜像连接阻止切换，健康检查失败自动恢复；保留新任务记录。
- 安装依赖缓存支持受限并行、同文件请求合并和临时空间预留；新增隔离 APT 签名验证预热工具及带时间的结果展示。
- 管理端增加版本与维护、实机验收页面；观察报告包含节点、安装与启动标识，人工验收区分版本、模式、平台和存储布局。
- 新增保守的发布备份生命周期与磁盘余量报告；未知构建目录、挂载和原始 ISO 保留，不定期自动删除。
- setup 显示阶段与结果摘要，支持版本查询及经中心 HTTPS/哈希验证的自身替换，保留旧文件、不自动执行更新。所有入口预置同一版本。
- 统一当前操作文档，明确发行版共享 ISO 入口、手动配置执行范围、软件回归与操作员实机验收的区别。

## 0.3.0-alpha.48 — 2026-10-30

- 手动、自动安装共用首启报告：显示硬盘启动、系统地址、主机名、内核与更新策略、RAID 和 setup 执行状态；等待初始化结束后刷新空闲登录提示，不重启已登录终端。
- 安装失败保留原始日志并上传限量、脱敏诊断；管理端新增安装结果与诊断页，明确区分观察到的错误、实际失败和安装后报告，不据此自动清盘或重试。
- PXE 清盘确认前显示所选盘序列号、单盘或 RAID1、文件系统和容量档位分配，提示 `/home` 的元数据预留；保持原有磁盘授权和完整成员检查。
- 增加受限的 Ubuntu/Debian 安装依赖缓存，保留原始软件源签名与包校验，原子发布完整下载并限制容量。EL 继续使用 ISO 内的软件仓库。
- 全部 Linux 共享预置包包含只读验收脚本，提供两次启动证据比对及手动/自动、Intel/AMD 实机验收清单。入口覆盖和软件回归与实机验收分别标示。
- 修复管理端重新核对已生成预置包时错误套用 2 MiB 文本上限的问题；压缩包使用独立上限，文本限制不变。

## P95 独立助手 1.0.3 — 2026-10-30

- 修复 CPU 控制器未启用时，单个多线程 P95 与 192 个独立会话的 memtester 因 autogroup 分组不均而出现的 CPU 时间争用。助手服务请求默认 CPU 权重，核对节点实际进入非根 CPU cgroup；仅有 cgroup v2 路径或服务 active 不再算通过。
- 保留 CentOS 7 的 CPUShares 兼容、逐线程 nice 修复及停止恢复记录，不修改节点 unit、内核、压测计划或全局 autogroup 开关。完整 setup 继续仅复制独立脚本，管理员按需手动运行。
- Rocky 9.2 / 9995WX 的 33 秒隔离实测：P95 从约 4.5 增至 97.4 个逻辑 CPU 的平均计算时间，memtester 从 187.6 变为 93.5；各有 192 个工作线程取得进展，测试结束后清理负载，节点服务未重启。此结果不是中心批次或长时间稳定性验收。

## 0.3.0-alpha.47 — 2026-10-30

- 按需手动启用 P95 修复：移除完整 setup 内嵌的 P95 安装器与自动安装/检查步骤，独立脚本 1.0.2 放在 `tools/p95-priority-setup.sh`，保留 CentOS 7.9 和额外 memtester 目录适配。
- 中心 tools 分发只复制和校验脚本；管理员需要时手动运行。已安装的 P95 助手保持原状，旧软件结果中的 P95 记录不再触发服务检查。
- 增加独立脚本完整性与文件复制、更新、重复执行、用户改动保护回归；验证手动/自动共享预置资源中没有 P95 安装器。

## 0.3.0-alpha.46 — 2026-10-30

- setup 在安装/检查节点软件、完成配置的节点接入后，为 fyhocsys-node / sckocstp-node 安装并验证独立 P95 优先级助手 1.0.2；软件包未变化时也会补装/检查，失败保留重试，检查模式不安装。
- 适配 CentOS 7.9 的 systemd 219、cgroup v1 和 EL7 mprime/独立 memtester 路径；保持严格的进程归属检查、真实权限自检和停止恢复逻辑。
- 助手源码、测试、构建工具随仓库与离线 setup 提供；普通 tools 文件仍只复制，助手不修改节点包、内核或启动压测。

## 0.3.0-alpha.45 — 2026-10-29

- 对接 sckocstp / fyhocsys 0.8.6 长期接入密钥：中心从独立 `0600` 私有配置提供地址、证书指纹和密钥；setup 安装节点包后调用官方 `join --key-file`，回读本机绑定并检查 worker、开机服务。重复执行不重建已有绑定，失败保留重试；密钥不进入安装包、软件清单、日志或结果记录。
- 节点绑定严格位于输入、应用并校验主机名之后；未完成的改名请求、运行/持久名称不一致，以及首次接入的常见默认名称均停止绑定。新增首次执行、开机恢复、改名失败/虚假成功的顺序回归；软件模式拒绝静默忽略 `--hostname`。
- 匹配的 DEB/RPM 在 `/root/ventoy-tools/` 保留原文件，复用 SHA-256 校验、原子替换和用户改动保护。已安装但没有包副本时补传；安装失败仍保留包，重复执行和 `--check-software` 均核对副本。
- 修复 setup 在新网卡链路建立较慢时仅保存 Netplan 配置、未加载 DHCP 的问题。networkd 和 Netplan 的新配置会先加载并等待链路；配置生成、发布、重载或激活失败明确报告待处理，可再次执行重试。增加 12 项隔离回归及 Ubuntu 22.04 用户空间的真实 DHCP、重复执行和重启检查。
- 旧存储重建按 LVM 卷组 UUID 核对成员，修复两块盘拥有独立但同名卷组时被误判为跨盘存储的问题。重复 UUID、真实跨盘成员和新 RAID 卷组名称冲突仍停止安装。
- 一次性安装授权成功后重新核对 LVM 状态，仅按 UUID 为所选的同名旧卷组改成唯一名称，解决 Debian 原生分区器继续按名称误判跨盘的问题。授权失败、状态改变、临时名称冲突或重命名失败均停止；后续重试可识别已改名的旧卷组。
- 旧系统的 swap 被安装环境启用时，允许在显式确认重装后仅关闭所选范围内的 swap，覆盖普通分区、LVM 和 MD。Python 与 Debian 选盘客户端区分 swap 和真实挂载，避免直接拒绝已有系统盘；授权后再次核对完整成员、挂载与设备身份，关闭失败或范围变化时停止安装。
- 存储回归扩至单盘/双盘各 39 个场景，增加可在无 KVM 云环境运行的 QEMU 真实 LVM/MD 检查，逐项核对未选磁盘的完整 SHA-256。

## 0.3.0-alpha.44 — 2026-10-28

- setup 将系统配置已检查后的软件安装失败单独标记为退出码 4，保留软件重试请求和原始错误。软件包存在或能显示版本不会消除安装脚本失败记录。
- 交互完整安装在软件失败或网卡/驱动待完成时，仍提供可选 root 密码修改，并刷新本次改名后的 Bash 提示符；退出新 shell 后保留失败/待完成退出码。
- 增加真实 Bash 软件失败控制流及 PTY 交互回归，验证密码提示、保留原密码、非交互不提示和 sudo 账户不变。

## 0.3.0-alpha.43 — 2026-10-28

- PXE 本机选盘新增单盘旧存储重建：识别到旧 LVM/软件 RAID 时显示可重建选项，选择目标盘并输入 `yes` 后继续，无需后台建任务或手工清理签名。
- 清盘前复用完整成员检查，确认旧卷组/阵列没有跨到未选磁盘；挂载、活动 swap、USB、只读、重复序列号仍拒绝。跨盘错误列出设备和序列号，不能把单盘确认扩大为整组清盘。
- CentOS/Rocky/RHEL/AlmaLinux、Ubuntu（含 Desktop）和 Debian 使用各自原生单盘分区流程；Debian 补齐旧 LVM/MD 移除的自动应答，容量档位及默认文件系统保持原规则。
- 增加单盘重建的 API、实际客户端、完整成员与 native recipe 回归，覆盖 28 个 Linux 模板的 BIOS/UEFI 组合；与双盘 RAID1 布局分开计算容量。

## 0.3.0-alpha.42 — 2026-10-28

- Ubuntu Casper 完成安装后，为被发行版屏蔽的 `cdrom.mount` 建立仅本次 live 环境有效的完整挂载单元，使 `LazyUnmount` 实际生效；不覆盖管理员屏蔽、不提前弹出介质、不强制重启。
- 为 finalrd 的关机内存环境补入 systemd 动态加载的 libmount 及依赖，避免 Ubuntu 26.04 退出安装介质时因缺少库而无法枚举挂载点。
- setup 在软件组安装校验后执行真实 FYHOC 解锁，安装每次开机重新认证的服务。凭据通过受认证的独立 HTTPS 接口获取，节点以 root-only 文件保存；不进入公开代码、ISO、setup 或普通清单。
- 增加凭据隔离、轮换、认证失败/超时、终端回显拒绝和启动状态检查。全部 Linux 手动/自动共享入口继续使用同一份预置 setup。
- 完整 setup 成功修改主机名后，在前台交互终端打开新的 Bash 提示符，避免旧提示符缓存旧名称；sudo 调用保持原用户，后台、检查、失败和待完成状态不打开交互 shell。
- 完整 `.run` 支持可选修改 root 密码，隐藏输入并确认两次、留空保留；用新密码验证真实 SSH 登录，之后不保存明文、不在再次执行或开机时恢复默认密码，普通账户密码保持不变。

## 0.3.0-alpha.41 — 2026-10-27

- 补齐 Rocky 10.2、Ubuntu Desktop 26.04 的现场自动安装入口，覆盖库存全部 52 个 Linux 镜像。Ubuntu 安装客户端使用现有 Python HTTPS 支持，修复 Desktop 26.04 live 环境缺少 curl 导致发现/授权失败的问题，保留 CA 校验与失败停止。
- 保留 Desktop Casper 已有的 `cdrom.mount` 屏蔽，避免成功预置 setup 后，收尾脚本因无法加载被屏蔽单元的 LazyUnmount 配置而使安装失败。
- 同一系统的手动/自动安装统一绑定原始 ISO；准备入口不再生成 `PXE-Auto` 镜像硬链接。选择系统后，在 iVentoy 脚本菜单选择手动或自动安装，默认无倒计时。
- 共享的红帽系注入包仅在用户选中的 Kickstart 与入口脚本完全匹配时启用自动安装；手动模式保留 E610、setup 预置及安装策略，不强制指定不存在的自动脚本。
- 旧独立入口不会在准备 API 中静默转换；发布时需一并迁移状态与 iVentoy 绑定，保留回退备份。

## 0.3.0-alpha.40 — 2026-10-27

- Linux 自动安装按发行版选择默认文件系统：CentOS、Rocky、AlmaLinux、RHEL 为 XFS，Ubuntu、Debian 为 ext4。PXE 控制台仍允许切换；/boot 继续 ext4，EFI 继续 FAT32，容量分配规则不变。
- 新安装任务持久化解析后的格式；历史授权未指定格式时保留 ext4，既有入口的显式格式设置不被覆盖。
- 修复 RPM / DNF 在安装脚本失败但退出码为 0 时，setup 误报软件安装成功的问题。记录失败的软件版本，再次运行不再把同版本残留误报为成功；更新为修正版本后可重新验证。
- 普通 Linux 手动安装和 PXE-Auto 共用新版 setup 预置包；setup 不更改已有文件系统。

## 0.3.0-alpha.39 — 2026-10-26

- Linux PXE 自动安装增加 ext4 / XFS 选择：默认 ext4，所选格式用于 /、/tmp、/var、/home；/boot 保持 ext4、EFI 保持 FAT32、swap 不变。沿用容量档位、单盘和双盘 RAID1 + LVM 分配。
- 管理端安装任务可指定文件系统，授权后由 PXE 保留；选择随任务持久化。安装前检查格式化工具，首次硬盘启动检查实际挂载格式，错误选择、缺失工具或格式不符会明确失败。
- 压缩 Debian 12/13 的安装收尾命令，修复双盘 RAID1 配置超过命令参数长度限制后跳过 root SSH、主机名和启动验收的问题；增加包含真实规模证书与账号策略的长度回归检查。
- 普通手动安装仍由安装器选择格式；setup 不重分区、不转换现有文件系统。

## 0.3.0-alpha.38 — 2026-10-26

- 修复所有 Linux 共用 setup 将管理员修改后的主机名恢复成旧缓存的问题。默认保留当前持久化名称，显式 `--hostname` 只应用一次，开机重试和只读检查不再强制旧名称。
- 终端直接运行完整 setup 时可输入新主机名，回车保留当前名称；参数指定、非交互执行和开机恢复不提问，软件分发和只读检查不改名。
- 兼容清理旧版遗留的固定主机名请求；继续保护 cloud-init 主机名、初始名称生成及失败重试。增加旧状态迁移、连续改名、启动恢复和校验回归。

## 0.3.0-alpha.37 — 2026-10-26

- tools 根目录的独立工具和其他普通文件也原样分发到 `/root/ventoy-tools/`，支持无扩展名工具、`.sh.x` 等文件。新增 `copy_files` 清单字段，旧客户端的 RPM / DEB 和压缩包流程保持兼容；普通文件不执行，继续校验摘要、保护用户修改、跳过临时文件和生成的 setup 本身。

## 0.3.0-alpha.36 — 2026-10-26

- tools 压缩包分发新增 `.tgz` 和 `.zip`，包括 Onload 和 ExaNIC 压缩包；保留原文件名，原样传输到 `/root/ventoy-tools/` 并校验 SHA-256，不解压或执行。与 `.tar.gz` 使用相同的重复运行、受管文件替换和用户改动保护规则。

## 0.3.0-alpha.35 — 2026-10-26

- Ubuntu Server 普通手动入口默认使用官方 HTTPS 主源和安全源，避免 HTTP 镜像源返回 403 导致 EFI 引导包下载失败；24.10 / 25.04 使用 HTTPS 归档源。仍保留镜像源选择页面、手动分区和账户设置，以及介质内核锁定和禁用自动升级策略。

## 0.3.0-alpha.34 — 2026-10-26

- Ubuntu Server 普通手动入口在安装开始前固定介质内核、阻止安装期间的无人值守包升级，并默认跳过安装器自身更新；保留手动选盘、分区确认和账户设置。
- Ubuntu/Debian 在首次启动前应用并检查内核锁定、APT 周期刷新和无人值守升级屏蔽；Debian 在基础系统完成后提前保护 pkgsel 阶段。完整 setup 仍由用户安装后执行。
- 保护已选择的 PXE 自动安装答案和外部手工答案，不用手动默认配置覆盖它们。

## 0.3.0-alpha.33 — 2026-10-25

- Linux 自动安装按实际磁盘容量分档：EFI 1 GiB、boot 2 GiB 固定；480/512 GB 档的 tmp/swap/var/root 为 5/32/64/128 GiB，120/128 GB 与 240/256 GB 分别缩至四分之一和一半，960 GB 及以上按档位倍增，home 使用余量。
- 覆盖 Kickstart、Subiquity、Debian Installer 和 Ubiquity；双盘 RAID1 + LVM 以较小成员盘计算，保留镜像及双盘引导结构。容量不足在领取安装授权前停止；普通手动分区及现有系统不被重分区。
- 默认普通管理员改为 `user`，现场策略统一 user/root 初始密码 `ventoy`，支持系统控制台和 SSH 的 root 直接登录；BMC 网页账户独立。
- 新版预置 setup 补齐 user、sudo 和 root 登录配置，兼容旧版 admin 完成标记，保留其他账户及文件。
- 增加各容量档位、不同容量 RAID1、原生分区配方和 user/root 密码策略的回归验证。

## 0.3.0-alpha.32 — 2026-10-25

- tools 根目录的 `tar.gz` 文件随 setup 原样传到 `/root/ventoy-tools/`，校验 SHA-256，不解压执行；未变化文件免重复下载，同名已托管文件支持替换，保留用户修改的文件。
- 修复完整 setup 因附加网卡等待 DHCP 或驱动等待重启而提前退出、跳过用户请求的软件安装的问题；已有网络可用时继续安装并检查中心软件。
- 保留未完成系统检查的 `PENDING` 状态；软件下载或安装失败明确报错并保留重试请求，普通后续启动不会自动拉取软件升级。
- 增加软件安装与待完成系统检查并存、失败重试、离线及只读检查的流程回归。

## 0.3.0-alpha.31 — 2026-10-25

- 直接运行 `./ventoy-linux-setup.run` 默认应用并检查 SSH、主机名、DHCP、内核锁定、禁用自动更新，以及匹配的中心软件安装；不再要求 `--apply`。
- 保留 `--apply` 兼容用法，`--software` 仅安装软件；`--hostname`、`--offline`、`--keep-passwords` 可直接用于默认完整配置。
- 更新普通 Linux 手动安装与 PXE 自动安装的预置包说明和运行提示；安装器继续只复制文件，进入系统后由用户执行。

## 0.3.0-alpha.30 — 2026-10-25

- 将新版 setup 与软件分发客户端加入 Linux 普通手动安装和 PXE 自动安装的预置包；安装后直接运行 `/root/ventoy-linux-setup.run`。
- 自动安装完成前显式复制并校验预置文件，注入链保留启动修复与 E610 驱动钩子。缺少完整离线包时拒绝生成不完整入口。
- 仅刷新带完整校验记录且尚未应用的旧托管 setup，保留旧文件备份；安装器不执行 setup 或安装中心软件。

## 0.3.0-alpha.29 — 2026-10-25

- 新增中心软件目录、只读分发接口和“软件分发”页面；节点运行新版 `ventoy-linux-setup.run`，按 DEB/RPM、架构、EL 版本自动选择默认软件。
- 支持包内版本比较、同一软件择新、已安装版本跳过、不降级、未变化软件免重复传输。中心替换软件包无需重新生成 setup。
- 缺依赖时由本机已配软件源解析；检查 SHA-256、包元数据、安装结果及现有内核/更新策略。只执行软件安装事务，不进行全系统升级。
- 提供按发行版配置专属组以及明确的 RPM 跨 EL 版本兼容规则。`--apply` 完整配置包含默认软件，`--offline` 不下载；旧预置 setup 需替换为新版一次。

## 0.3.0-alpha.7 — 2026-10-14

- Ubuntu 自动安装显式使用官方 HTTPS 主仓库和安全仓库，关闭 GeoIP 自动替换镜像站，修复 22.04.3 实机因镜像站 HTTP 403 无法安装 EFI 引导包的问题。
- Ubuntu Server 22.04.3 已完成 Intel X710 / UEFI 实装、硬盘启动、控制台 / SSH / sudo 登录、网络与首次启动回报；无失败服务，保留盘分区表及签名一致，旧授权返回 HTTP 401。
- 此流程仍需一次安装 `yes` 确认；测试机由现场调整为硬盘优先启动，尚未实现完整无人值守。实际系统标识为 22.04.3，在线更新后内核为 `5.15.0-198-generic`。

## 0.3.0-alpha.6 — 2026-10-14

- 修正 Ubuntu 自动安装的磁盘匹配：`lsblk SERIAL` 与 Subiquity 使用的 udev `ID_SERIAL` 不同，旧配置可能没有匹配磁盘并报 `NoneType ... id`。
- 在 MAC、唯一短序列号、设备类型、存储和固件检查通过后，将确认的磁盘路径原子写入 `/autoinstall.yaml`；初始路径不可安装，写入失败时不领取安装授权。
- 增加 Ubuntu 绑定及失败顺序回归测试；在 22.04.3 原始 Subiquity 5004 上复现旧匹配失败并验证新路径准确命中目标盘。后续完整安装结果见 alpha.7。

## 0.3.0-alpha.5 — 2026-10-14（待实机复测）

- 将 CentOS 7 已验证的分离 hostname / MAC 绑定网络配置扩展到 Rocky 8，避免 initramfs 等待 udev 改名前的 `ethN`。
- Rocky 8.10 原始安装器解析器的隔离复现通过：旧配置生成 `ip=eth1:dhcp:` / `bootdev=eth1` 和网络等待标记；新配置不生成这些条件，保留 MAC、DHCP 和自动连接。此修复尚未完成物理机回归。

## 0.3.0-alpha.4 — 2026-10-14

- Rocky 8 任务增加 `rocky-iventoy.tar.gz` 启动注入包，补齐 iVentoy 1.0.44 的 Kickstart 入口，并纳入准备、校验和清理清单。
- Rocky 8.10 DVD 已完成 Intel X710 / UEFI 实机自动安装、硬盘启动、控制台 / SSH / sudo 登录和首次启动回报；保留盘分区信息一致，完成任务重放返回 HTTP 401。
- 本次安装存在约 10 分钟 initramfs 网络等待，日志定位到已改名的 `eth1`；功能验收通过，启动等待问题待 alpha.5 实机复测。

## 0.3.0-alpha.3 — 2026-10-14

- CentOS 7.9 任务额外生成受清单管理的 iVentoy 注入包，通过 dracut 的 `cmdline.d` 传入 Kickstart 路径；管理页面显示两份文件的绑定路径。
- 修正 iVentoy 提前加载网卡驱动时的 CentOS 7 网络配置：避免把 udev 改名前的 `ethN` 写成启动等待目标，安装器网络按 MAC 绑定。
- 已用官方 DVD 的原始 `parse-kickstart` 在隔离环境复现旧配置的 `eth1` 等待条件，并验证新配置不产生该条件、保留 MAC / DHCP / 自动连接设置。
- CentOS 7.9 官方 DVD 已通过 Intel X710 / UEFI / iVentoy 1.0.44 的物理机自动安装、目标盘启动、控制台 / SSH / sudo 登录及首次启动回报；另一块盘原有分区保留，已完成任务的授权重放返回 HTTP 401。
- 本轮先在已授权测试机上离线解除旧 RAID 并仅准备目标盘；模板仍拦截现有 RAID / LVM，不把单盘实装结果扩展为多盘存储或其他启动模式已验收。

## 0.3.0-alpha.2 — 2026-10-13

- 修复 CentOS 7.9 安装环境缺少 `base64`、旧版 `lsblk` 不能读取 VirtIO 磁盘序列号导致的安装前中止。
- 按 CentOS 7.9 DVD 的软件包清单使用 `minimal` 环境，避免安装器因错误的软件包组等待人工应答。
- 默认管理员改为 `deployadmin`，拒绝 Linux 内置 `operator` 账户；首次启动核对普通用户 UID 与登录 shell，再报告安装完成。
- 识别官方 `CentOS-7-x86_64-DVD-2009.iso` / Everything 文件名，拒绝不适用于当前模板的 Minimal、NetInstall 和 Live 镜像。
- 增加旧版 / 新版磁盘标识、重复序列号、错误版本、固件、USB、RAID 和授权拒绝的隔离回归测试。
- 记录用户当前的 18 个目标版本，Ubuntu 限 Server / live-server；CentOS 7.9 优先，其余逐 ISO 验收。
- CentOS 7.9 官方 DVD 已在独立 UEFI 虚拟机中通过无人值守安装、无 ISO 磁盘启动、SSH / sudo 登录、完成回报和凭据重放拒绝；真实硬件完整 PXE 自动安装仍待验收。

## 0.2.0-alpha.1 — 2026-10-13

- 调整为 Linux 直推装机优先；新任务仅安装系统，sckocstp / fyhocsys 接入后置，不改其代码。
- 增加系统 profile：CentOS 7.9、Rocky 8/9/10（含 10.2）、Ubuntu 20.04/22.04/24.04/26.04 LTS、Debian 11/12/13；Windows 保留次要支持。
- 新增 Debian preseed、安装器 HTTPS 授权与失败阻塞钩子；Linux 首次启动核对系统版本。
- 镜像目录树、文件名版本建议、MAC 搜索、启动任务表、系统版本页。
- 新增版本匹配、安装状态流转及 Debian 写盘前阻断测试；实机 PXE 验收仍待完成。

## 0.1.0-alpha.1 — 2026-10-13

- 建立独立 Go 管理端和中文部署工作台。
- 实现机器与安装任务、磁盘确认、单次授权、持久状态和受限安装回调。
- 提供 Rocky 9、Ubuntu Server 24.04 与 Windows 安装包生成。
- 提供 Linux fyhocsys 连接文件导入与节点包校验流程。
- 增加 Rocky 优先的 systemd 部署、Windows 安装脚本、跨平台构建和 Linux 启动矩阵。
- 当前交付为 alpha：iVentoy 规则人工配置，Windows fyhocsys 节点未实现，真实机器 PXE / 装机 / 中心心跳验收待完成。
