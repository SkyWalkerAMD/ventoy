# 普通 ISO 手动安装后的完整配置

alpha.56 新增 Ubuntu/Debian 可选的普通用户登录恢复功能：

```bash
sudo /root/ventoy-linux-setup.run --restore-user-login
# 手动安装使用其他管理员名称时，指定已存在的账户：
sudo /root/ventoy-linux-setup.run --restore-user-login --login-user alice
sudo /root/ventoy-linux-setup.run --check-login
```

默认选择 `user`，提示隐藏输入该用户的当前密码，实际验证 SSH 登录及 sudo 后，才关闭 root SSH 直登并锁定 root 控制台密码登录。普通用户密码不变，登录后使用 `sudo -i` 提权；原有会话保留。缺少可用普通账户或验证不通过时停止；切换过程中失败会回退并报告结果。备份位于 `/var/lib/ventoy-center/manual-init/login-backup.*`，不保存明文密码。

这是手动选择的恢复功能，**新装系统默认允许 root 直登的行为不变**。恢复后，完整 setup、升级和开机恢复均保留普通用户模式，不再弹出 root 改密提示。`--check-login` 只检查当前配置及账户状态，不宣称重新验证了密码登录。此选项不改变软件、网络、内核锁定、自动更新策略或带外网页账户。

当前操作见[日常装机与发布维护](../operations.md)。alpha.41 起采用发行版目录的共享 ISO 入口，手动/自动共用启动注入包；不要用旧的纯手动注入包覆盖当前绑定。alpha.50 起 `--upgrade` 校验、备份并替换自身，随后应用新版配置和软件；已配置节点保留密码、主机名和既有网络。alpha.49 旧文件先运行 `--update-setup`，再直接运行新版即可；`--version`、`--check-version` 可查询版本。

alpha.31 将包含[安装后软件分发](node-software.md)的新 setup 统一预置到普通手动安装和 PXE 自动安装结果。无参数运行 `/root/ventoy-linux-setup.run` 即应用完整配置、安装匹配的软件组并自动检查；`--apply` 保留兼容，`--software` 仅安装或升级软件。后续中心替换 RPM / DEB 不需要更换 setup。

中心配置启用 `"linux_setup_preload": true` 后，生成的 Linux 专属任务与 PXE 菜单注入包包含当前 setup，安装收尾必须完成复制和 SHA-256 校验。普通手动入口绑定 `/api/linux-manual-setup?format=injection` 生成的当前注入包。升级中心后应重新生成并发布既有入口的注入包；已有准备文件不会在活动安装期间自动改写。若已校验的 E610 完整离线包缺失，生成失败，不会悄悄省略 setup。

此更新通过 iVentoy 注入覆盖介质中的旧托管预置，不重建 ISO，也不改变内置 E610 驱动。脱离该 iVentoy 直接使用旧 ISO 时，仍是原来内置的版本。此前已安装的节点可显式运行 `--upgrade` 获取新版；不识别该参数的旧包先使用独立升级桥接脚本。

从 alpha.24 起，普通 Linux ISO 可以绑定 **手动安装配置包预置注入文件**。安装器保留交互步骤，在安装收尾时将完整配置包复制到新系统的 `/root/ventoy-linux-setup.run`。进入硬盘系统后，由用户手动执行：

```bash
sudo /root/ventoy-linux-setup.run
# 如需指定主机名：
sudo /root/ventoy-linux-setup.run --hostname server01
```

这套配置覆盖现有 Linux 家族：Ubuntu 20–26、Debian 10–13，以及 CentOS、Rocky、AlmaLinux、RHEL 7–10（x86_64）。不仅用于 Ubuntu / Debian。Windows 不在本轮 Linux 配置包范围内。

**预置不等于完整配置已完成。** 运行前仍使用手动安装时创建的账户和网络设置，预置过程不改密码、不启用 SSH、不应用 DHCP，也不替用户选盘。alpha.34 将 Ubuntu/Debian 的内核锁定和 APT 自动更新保护单独提前到安装阶段，首次启动前检查完成；其他完整配置仍由 setup 执行。`/var/lib/ventoy-center/manual-setup-preloaded` 中的 `PRELOADED_ONLY` 只证明 setup 已放入，不能当成 SSH/DHCP/软件验收通过。更新保护另有 `/var/lib/ventoy-center/manual-install-update-policy` 标记，并可运行 `/usr/local/sbin/ventoy-center-update-policy --check` 检查。

alpha.24 的普通 ISO 预置依赖 iVentoy 的注入绑定。alpha.25 的 E610 适配 ISO 已把驱动、原生安装完成钩子及配置包写入镜像：普通手动入口与 PXE-Auto 复用同一成品，E610 驱动随安装自动写入目标系统，配置包仍由用户安装后手动执行。原生已支持 E610 的镜像继续保留原驱动和普通预置绑定。未经适配、也未绑定注入的原 ISO 不会携带这些内容；管理端保留下载入口供已有系统使用。

在终端直接运行时会显示当前主机名，并提示输入新名称；直接回车保留当前持久化名称。`--hostname NAME` 可跳过提问直接指定；非交互运行和开机恢复服务不提问。默认 localhost 会替换成机器标识生成的名称。显式名称是一次性设置：以后的 setup 和开机恢复服务不使用旧缓存覆盖管理员改名。默认账户为 `user / ventoy`、`root / ventoy`；保留其他用户。需要保留原密码时加 `--keep-passwords`，此时须已有可用的 user/root 密码，并自行做客户端登录验证。

安装后改名使用 `sudo hostnamectl set-hostname server02`，或 `sudo safe-server-init hostname server02 --update-hosts` 同时维护本机 hosts。仅执行 `hostname server02` 属于临时改名，不会保存到下次启动。alpha.37 及以前的 setup 存在固定旧名称的问题；现有机器需替换新版 `.run` 并执行一次，才能更新 `/opt/ventoy-manual/current` 和开机恢复服务。只替换磁盘上的 `.run` 文件不会更新已安装服务。

alpha.33 起，首次执行新版 setup 会补齐 `user` 账户和 sudo 权限，并设置 user/root 初始密码；旧版 admin 及其文件保留。root 的密码同时用于系统控制台和 SSH，不改变 BMC 网页账户。新版已完成账户配置后再次运行不会重置用户后来修改的密码；`--keep-passwords` 保留已有密码。

交互式完整 setup 在最后询问是否修改 root 密码。输入 `y` 后可手动输入并确认新密码，密码字符不回显。选择回车或等待 60 秒则保留当前密码，输入和确认各有 120 秒。已切换到普通用户登录模式的 Ubuntu/Debian 不显示该提示。

Ubuntu Server 普通手动入口从 alpha.35 起默认使用官方 HTTPS 主源和安全源，24.10 / 25.04 使用 HTTPS 归档源。镜像源页面仍可手动修改。安装 EFI 引导程序所需的包可能需要从源下载，这属于安装依赖；内核锁定和禁止自动升级仍生效。若手动改回不可用的 HTTP 源，仍可能在下载引导包时遇到 `403 Forbidden`，应检查安装日志里的实际失败地址。

## 自动应用和检查

alpha.27 保留 Ubuntu 已启用的 SSH socket 启动方式，避免首次执行 setup 时同时留下采用旧策略的 SSH 监听进程。Ubuntu 24.04.3 已通过真实隔离 iVentoy 交互手动安装、点击重启后进入硬盘系统、setup 配置及再次重启验收。普通 ISO 的完成钩子只为 live 安装介质准备正常卸载；目标系统配置仍需手动执行 setup。

| 项目 | 应用方式 | 完成检查 |
| --- | --- | --- |
| SSH | 启用服务、root 密码登录、user sudo；放行已启用防火墙中的 SSH 端口 | 检查有效配置，并实际以 root/user 密码连接本机 SSH |
| 主机名 | 默认保留当前名称；显式改名时备份并同步 hosts；让 cloud-init 保留名称 | 静态名称与运行名称一致，不要求等于旧缓存 |
| DHCP | 为未配置硬件有线网卡建立持久 DHCP 配置，并激活新增配置 | 检查持久配置和已连接接口的实际 IPv4 地址 |
| 内核锁定 | APT hold/pin 或 yum/dnf `kernel*` 排除 | 比对已安装内核清单、包管理器策略 |
| 禁用自动更新 | APT 周期刷新和 unattended-upgrades；或 yum-cron/dnf 自动升级及缓存刷新 | 持久屏蔽和当前运行状态 |
| CLI | 默认 `multi-user.target` | 读取默认启动目标 |
| E610 | 原生支持则保留；否则通过 r4 原始分发器精确匹配系统及内核，未覆盖的内核停止并保留现状 | 校验 ABI/设备 ID、启动镜像、实际加载模块与 E610 绑定状态 |

alpha.45 起：网卡链路建立较慢或稍后接网线时，先加载新增 DHCP 配置，使链路就绪后自动申请地址；之前版本可能只保存 YAML 而未加载。配置生成、发布或加载失败会报告 `DHCP_ACTIVATION_PENDING`，修复依赖/配置问题后可重新执行 setup。`DHCP_SAVED_NO_CARRIER` 表示当时没有链路，`DHCP_LEASE_PENDING` 表示有链路但尚未取得 IPv4，二者应结合实际网线、交换机和 DHCP 服务判断。

已有 DHCP、静态网络、Bond/VLAN/Bridge、USB、Wi-Fi 和当前 SSH 出口保留。新增次要 DHCP 接口不接管默认路由和 DNS。支持 NetworkManager、Netplan、systemd-networkd、ifupdown 的 ISC dhclient / dhcpcd，以及符合检查的传统 ifcfg；复杂或无法确定的配置保留并报告待处理。

安装包自解压，支持 Python 2.7 / Python 3 / EL8 platform-python，不要求最小化系统已有 tar。包内包含已校验的 E610 多系统 r4 离线包（93 个精确系统／内核条目），保持原始嵌套安装器及回退文件；缺少 SSH 或 sudo 等依赖时可从系统软件源补齐，不做系统或内核升级。`--offline` 禁止下载。

## 检查结果和边界

```bash
sudo bash /opt/ventoy-manual/current/install.sh --check
sudo cat /var/lib/ventoy-center/manual-init/status
sudo journalctl -u ventoy-manual-init.service
```

`VERIFIED` 表示当前适用检查通过；`PENDING` / 退出码 3 表示仍需要驱动重启、证书注册或 DHCP 租约。已安装服务在以后每次启动继续处理和检查，不自动重启机器。没有 E610 时输出 `E610_NOT_PRESENT`，不能据此认定实际 E610 硬件已验收。

alpha.32 将用户请求的软件安装与这些待完成检查分开：例如启动网卡已联网、附加网卡尚未取得 DHCP 地址时，仍会安装中心软件。软件安装结果单独输出；系统检查仍未完成时继续报告 `PENDING`，不会把附加网卡误报为已获得地址。软件下载或安装失败保留重试请求，`--check` 只检查系统、不触发软件安装。

更新策略锁定执行脚本时的内核，不把手动安装过程中已更新的内核降回 ISO 版本。E610 适配 ISO 保留原生安装器的手动流程，并独立完成驱动持久化，不依赖执行本配置包；启动内核和安装目标内核必须各有精确匹配的驱动。未经适配的原 ISO 在安装环境缺少 E610 时，不能依靠安装后才执行本包来解决网启问题。

Secure Boot 首次使用外部签名驱动可能需要控制台 MOK 注册；未知内核也可能缺少历史头文件。遇到这些情况明确停止或报告待处理，不强行加载其他 ABI 的驱动，也不将保存配置等同于验证成功。

日志：`/var/log/ventoy-manual-init.log`。账户及配置备份：`/var/lib/ventoy-center/manual-init/`；主机名备份：`/var/backups/safe-server-init/`。驱动按原包说明回退，动态构建路径为 `/var/lib/e610-ixgbe/manual-系统-内核/payload/install.sh --rollback`。

管理端 API 为经过管理员认证的 `/api/linux-manual-setup?format=run`，不含控制器令牌。服务端需要在配置的 `PackageDir` 放置原始 `E610-MultiOS-6.4.5-r4.tar.gz`，固定 SHA-256 为 `35cfb7ef582d95e8f005220b518aa2a7a1acc44aac95d65c94acfbd65055f1af`；缺失或校验错误时拒绝生成。`/api/linux-manual-setup` 保留 tar.gz 下载。

`/api/linux-manual-setup?format=injection` 生成 `ventoy-manual-preload.tar.gz`。将其绑定到普通 Linux ISO 的启动注入文件，不绑定自动安装答案。注入包包含经过校验的完整 `.run` 文件、Debian d-i 的 `finish-install.d`、Anaconda 的 `post-scripts` 和 Ubuntu 的安装收尾钩子。复制前后核验 SHA-256，不覆盖用户已有的内容不同的同名配置包；目标系统的 `/root/README-ventoy-setup.txt` 提供操作说明。启动配置只属于安装器环境，不会在已安装系统中启用自动执行 setup 的服务。

Ubuntu 20.04.3 的 Subiquity 尚无原生 postinst 目录，因此在安装器的完成阶段增加复制回调，保留原交互流程；Ubuntu 26 桌面版保留原启动参数和全部内置完成钩子，只增加预置复制。两种兼容启动包装都不传入自动安装参数，不修改原始 snap 文件。

更新预置绑定时，只有尚未执行的托管旧包才可刷新：`PRELOADED_ONLY`、原校验文件和实际 SHA-256 必须一致，且不存在 `manual-init` 已应用状态。旧文件以 `.preload-backup.<摘要>` 保留。用户修改、无标记或已应用的文件继续保护，不覆盖；介质内置 E610 驱动不受此更新影响。

用户提供的 `safe-server-init` 保留为独立工具；本项目另加激活和检查封装。此处适配增加 Debian 10 范围，以及仅在 sysfs 确认永久地址未被修改时识别 networkd 的 `PermanentMACAddress`。原脚本未知配置保护仍保留；完整包的新增网卡激活行为不能解释为原脚本单独运行也会全局应用网络。
