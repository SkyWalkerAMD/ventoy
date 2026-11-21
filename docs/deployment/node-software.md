# 安装后从中心获取软件

从 alpha.29 开始，新版 `ventoy-linux-setup.run` 可以从中心服务器获取 RPM / DEB，在已安装并启动的 Linux 节点上安装或升级。不重新装系统，不改磁盘；软件模式不重设账户、主机名或网络。

公开版 `sckoct-pub`、`sckoct-pub-suite` 的适配 RPM / DEB 仅保存到 `/root/ventoy-tools/`。策略按包内部名称判断。alpha.62 起，中心配置 `fyhoct_install_key_file` 后可自动安装适配的 `sckoct-fyh` 1.2.6 及更新版本。未配置时和低于 1.2.6 的包仍按只下载处理。

将同版发布的 RPM / DEB、`oc-engine-linux.tar.gz.enc` 和 `oc-deps-linux.tar.gz.enc` 放进 tools。安装密钥应为中心软件服务账号可读的私有文件，权限为 0600，路径放在 tools 之外。普通 setup、`--upgrade` 和 `--software` 会校验软件包与组件，先装包，再用官方 `fyhoct install` 初始化组件。安装密钥从鉴权接口读取，仅供该进程使用。`--check-software` 会确认引擎与依赖均已安装。

结果分别记录 `packages`（验收安装）和 `copy_only_packages`（验收文件传输）。已执行组件安装的节点还记录 `fyhoct_components`。仅分发包的旧 RPM 安装脚本失败记录继续显示为 `COPY_ONLY_WARNING`。启用自动安装的包必须通过常规安装脚本验收。

## 服务器目录

本次部署使用用户指定的 `/home/ventoy-center/iventoy/tools/`。管理端 `config.json` 增加：

```json
{
  "software_dir": "/home/ventoy-center/iventoy/tools",
  "software_rpm_min_el": {"fyhocsys-node": 8}
}
```

通过 SFTP 上传 RPM / DEB 到此目录。保留标准文件名，如 `name_version_amd64.deb`、`name-version-release.el9.x86_64.rpm`。先上传成 `.part`，完成后原子改名为 `.deb` / `.rpm`；不要一边下载一边覆盖正在发布的文件。文件应为普通文件，服务账户有目录读取/遍历权限及文件读取权限。服务只读此目录。

打开管理端“软件分发”，查看包清单并下载新版 setup。替换、新增或移除包后无需重启中心、iVentoy，也无需重新下载 setup；节点下一次执行时读取最新清单。

tools 根目录中的压缩包、独立工具和其他普通文件原样保存到目标机的 `/root/ventoy-tools/`，只传输及校验 SHA-256，不解压、编译或执行。例如 `ipmitool-IPMITOOL_1_8_19.tar.gz`、`onload-9.2.1.70.tgz`、`exanic-software.zip`、`centos_opt_static` 和 `ubuntu-optimize.sh.x` 均保留原文件名。不同名称或版本的文件都会传输，用户按系统和硬件选择后手动使用；文件以 root 私有权限 `0600` 保存，执行独立工具前按需赋予执行权限。RPM / DEB 仍按系统匹配并自动安装，原样分发的文件不会被当成已安装软件。

普通文件分发需要 alpha.37 或更新的管理端和 setup。全局预置包更新后，新装节点直接运行预置 `.run` 即可；已有节点需更新一次 `.run`，后续 tools 内容变化自动读取最新清单。`copy_files` 为新增字段，旧客户端继续处理已有软件包和压缩包，不会因独立工具加入而报格式错误。文件名使用 ASCII 字母或数字开头，其余可包含字母、数字、点、下划线、加号、连字符和波浪号，总长不超过 248。仅发布根目录的普通文件；隐藏文件、符号链接、子目录、`.part/.partial/.tmp/.download/.crdownload/.swp/.bak` 和 `~` 临时后缀，以及 `ventoy-linux-setup.run` 本身及其附属文件不作为原样文件分发。此目录专用于向节点分发软件和工具。

未变化的压缩包校验后跳过下载；中心替换同名文件后，下一次运行原子替换节点上由 setup 管理的旧文件。节点文件被用户改动或同名文件不属于 setup 时保留并报错。中心删除文件不会删除节点已有副本。压缩包与软件包合计最多 256 个文件、8 GiB，单文件最多 4 GiB；目录中未完成的 `.part` 文件不发布。`--list-software` 列出文件但不传输，`--check-software` 同时回读软件版本与已分发文件摘要。

2026-10-29 未发布改动：匹配组内的 DEB/RPM 也以原文件名保存在 `/root/ventoy-tools/`（`0600`），安装直接复用已校验的副本。专属目录的软件包在目标机按文件名保存；只保留本机匹配组，不把其他系统的软件包下载过来。软件已装好但旧 setup 已清理包文件的，第一次运行新版会补传；之后校验一致就跳过下载。安装或节点接入失败时仍保留文件供重试，`--check-software` 会检查副本丢失或变化。依赖解析从系统源额外获取的依赖包仍由系统包管理器管理。

## 节点执行

alpha.31 的预置流程在普通手动安装和 PXE 自动安装结束时，将新版文件放在 `/root/ventoy-linux-setup.run`，无需另行下载。安装器只复制并校验文件，不执行软件安装。已安装的旧系统不会被远程改写，可从管理端下载新版后替换一次。

```bash
# 无参数：完整系统配置 + 匹配的软件安装 / 升级 + 自动检查
sudo /root/ventoy-linux-setup.run

# 仅安装软件；不重设账户、主机名、网络
sudo ./ventoy-linux-setup.run --software

# 查看当前候选包；不安装
sudo bash ventoy-linux-setup.run --list-software

# 检查上次成功软件组是否仍已安装到要求版本或更新版本
sudo bash ventoy-linux-setup.run --check-software

# 完整配置并指定主机名；--apply 保留兼容但无需填写
sudo ./ventoy-linux-setup.run --hostname server01
```

`--offline` 不连接软件库。从 alpha.32 起，附加网卡等待 DHCP、驱动等待重启等 `PENDING` 检查不会跳过用户请求的软件安装；已有网络可用时继续下载、安装并验证。软件失败明确报错并保留请求，用户再次运行或配置恢复服务可以重试；成功后清除请求，正常后续重启不再从软件库更新。新增软件、升级软件都由用户主动再次运行 setup 触发。

## 长期密钥自动接入节点（alpha.45）

已核对 [sckocstp 0.8.6](https://github.com/SkyWalkerAMD-org/sckocst-pub/blob/1d6310c50341cf3e07e4aef67e3f0ca79502196b/docs/releases/0.8.6.md) 和 [fyhocsys 0.8.6](https://github.com/SkyWalkerAMD-org/fyhocsys/blob/c66dc8febdbaeda81ee144c9afacbe2e02bfb13d/docs/releases/0.8.6.md)。两者支持同一条长期密钥命令在多台机器自动登记；中心和节点都需要 0.8.6 或更新。

在相应节点中心“部署与操作 → 自动接入”生成长期密钥，取命令中的 `url`、`pin`、`key`。在 Ventoy Center 的 `config.json` 增加：

```json
{
  "software_dir": "/home/ventoy-center/iventoy/tools",
  "node_join_config_file": "/home/ventoy-center/private/node-join.json"
}
```

私有文件内容如下（占位值必须替换成中心生成的实际值）：

```json
{
  "schema": 1,
  "nodes": [
    {
      "program": "fyhocsys",
      "url": "https://CENTER_ADDRESS",
      "pin": "CENTER_CERTIFICATE_SHA256_64_HEX",
      "key": "LONG_TERM_JOIN_KEY"
    }
  ]
}
```

文件设为服务账户所有、权限 `0600`，放在 `software_dir` 外的私有目录；不能放进源码、tools、ISO 或 setup。`program` 可选 `fyhocsys`、`sckocstp`，按需要填写其中一个或各一个，各用对应中心的密钥。未列出的程序不会自动接入。把需要安装的 0.8.6+ 节点 DEB/RPM 放进匹配的软件组。首次新增配置字段需要重启 Ventoy Center，并更新已有节点及安装入口使用的 setup；之后只修改私有 JSON 即可轮换密钥、地址和指纹，无需重打包。

节点开机后执行普通 `setup` / `ventoy-linux-setup.run`，或 `--software`：安装完成后通过 HTTPS 的独立鉴权接口读取接入参数，调用官方 `join --key-file`，临时密钥文件仅 root 可读、用后删除。下载凭证也授予读取接入密钥的权限，应按节点凭证保管。结果只保存程序名、地址和证书指纹。`--list-software` 不读取密钥，`--offline` 不做在线接入。从 alpha.54 起，`--check-software` 除本地配置、worker 和服务状态外，还发一次鉴权心跳确认中心接受凭据；不登记、不领取任务、不启动压测。离线时不能报告绑定验收通过。

setup 的固定顺序是：输入/确认唯一主机名 → 应用并回读运行值和 `/etc/hostname` → 安装软件 → 绑定节点。主机名修改失败（包括命令返回成功但名称实际未改变）、仍有 `hostname-pending`、运行值与持久值不一致时，不执行绑定；首次接入遇到 `ubuntu`、`debian`、`rocky` 等常见默认名称也会拒绝，先运行完整 `setup --hostname 唯一名称`。启动恢复先完成上次的主机名请求，再重试软件和接入。`--software` 使用已有主机名；不能带 `--hostname` 让该参数被静默忽略，需要改名时先走完整 setup。

资产编号使用节点程序读取的 DMI 序列号；读不到有效编号时明确失败，需在该机器上用官方命令加 `--serial` 指定资产编号，再运行 setup。中心仍接受凭据的节点重复执行不重复登记，也不重启运行中的节点服务；绑定其他中心或改名造成不一致时保留原配置并停止接入。

重装后要保留原卡片，请在 setup 的主机名步骤填写原卡片名称。官方中心按主机名查找旧节点，再核对 DMI UUID；不同名称会作为新节点处理，setup 不猜测或修改其他卡片。中心和节点 0.8.6+ 已记录 DMI UUID 的同一台机器，使用有效长期密钥可重新绑定。刚重装时旧心跳未满 5 分钟，alpha.54 每 15 秒自动重试，最多等待 330 秒，显示 `NODE_JOIN_WAIT`；若旧实例一直在线、UUID 不匹配或没有旧 UUID 记录，则明确停止，保留官方保护。旧版本从未上报 UUID 的节点需在中心使用一次“重新绑定”。

若中心已重新绑定/撤销旧凭据，但节点仍留有 `connection.json`，alpha.54 不再相信上游命令的本地 “Already joined” 提示。仅当固定证书指纹的中心明确返回 HTTP 401 时，setup 才通过官方 `join --config <临时文件> --start=false` 取新连接。验证新连接后，在原配置目录保留 root `0600` 的 `connection.before-setup-*.json` 备份、停止旧凭据服务、原子替换配置并启动服务。网络故障、证书变化及其他 HTTP 错误不会触发替换。最后必须收到中心的鉴权心跳响应，才输出 `NODE_JOIN_VERIFIED`。上游保留原卡片和历史；SSH 主机密钥按其重装规则重新确认。

接入失败返回软件失败，完整 setup 的开机恢复服务保留重试请求；已经完成的包安装及文件副本可复用。成功后检查官方节点配置/worker、证书指纹、启用且运行中的 `fyhocsys-node.service` / `sckocstp-node.service`，以及中心接受的鉴权心跳。日常开机由节点自身服务连接中心。这不是压测功能验收，不会运行压测任务。FYHOC 的解锁口令是下面另一项独立功能。

其他软件包失败时，alpha.54 仍独立尝试已安装节点的接入与检查，避免例如 `sckoct-fyh` 的 `%post` 失败挡住 fyhocsys 的重新绑定。输出 `NODE_JOIN_CONTINUE`，成功的接入记录写入结果文件；原软件错误及总体失败状态保留，不会把有问题的软件包标成成功。节点包缺失、版本不符或 worker 检查失败仍明确报错；同一次执行不会反复调用失败的接入步骤。

## FYHOC 每次开机自动解锁（alpha.42）

中心可在私有配置中设置 `fyhoc_unlock_password_file`，指向 tools 目录以外、仅服务账户可读的 `0600` 普通文件。文件只保存解锁口令；口令不写入公开源码、ISO、setup 包或软件清单。节点使用已有软件下载凭证，通过 HTTPS 的独立接口获取；因此持有该凭证的节点也有权获取解锁口令。更新中心文件后，下一次运行 setup 会验证并保存新口令。

匹配的软件包安装并校验成功后，setup 对已安装的 `fyhoc` 执行真实 `fyhoc unlk`，通过关闭回显的专用终端输入口令，不把口令放进命令参数或环境变量。节点把凭据保存为 root 所有的 `/etc/ventoy-center/fyhoc-unlock.key`（`0600`），启用 `ventoy-fyhoc-unlock.service` 并立即检查。每次开机重新认证，不依赖中心联网，不修改或伪造 FYHOC 的临时授权文件。软件升级后再执行 setup 也会重新验证。

`--check-software` 同时检查本次开机的解锁状态和开机服务；口令错误、认证超时、服务失败均返回错误，不报告解锁成功。服务日志仅记录成功/失败，不输出口令或认证终端内容。中心未配置该功能时明确显示 `FYHOC_UNLOCK_SKIPPED`。这只处理 FYHOC 解锁，不替代 fyhocsys-node 的入网注册。

CentOS 7.9 与 Ubuntu Desktop 26.04 隔离系统已分别用真实 `fyhoc 1.1.24-1` RPM / DEB 完成安装、立即解锁和正常重启后的自动解锁；内核分别保持 `3.10.0-1160.el7.x86_64`、`7.0.0-14-generic`。同次动态选择并安装 `fyhocsys-node 0.8.5`，9 个工具文件传输和摘要检查通过。完整范围和发布状态见[进度记录](../development/progress.md)。

## 自动选择与升级

### 手动运行的 P95 优先级助手（alpha.47）

P95 修复不再集成到 `ventoy-linux-setup.run`。将仓库的 `tools/p95-priority-setup.sh` 放到中心 `/home/ventoy-center/iventoy/tools/`；节点执行 setup 时只把它复制到 `/root/ventoy-tools/` 并校验 SHA-256，不安装、启停、修复或检查 P95 助手服务。需要时由管理员手动执行：

```bash
bash /root/ventoy-tools/p95-priority-setup.sh
# 只检查已安装的独立助手：
bash /root/ventoy-tools/p95-priority-setup.sh --check
```

独立脚本安装后将源码、测试、构建脚本及说明保留在 `/usr/local/share/p95-priority-helper/1.0.2/`，仓库源码在 `tools/p95-priority-helper/`。助手每秒把受管 mprime 线程默认的 nice 19 调到 nice 0；不修改 fyhocsys/sckocstp 项目文件或 prime.txt，也不启动压测。相同版本且检查正常时保持助手运行；缺失/停止时再次手动运行独立脚本可补装/恢复。完整 setup 的 `--check-software` 只检查下载的脚本文件，不检查 P95 服务；读取 alpha.46 的旧结果记录也不会恢复 P95 检查。

CentOS 7.9 的 systemd 219 已加入适配：使用旧版支持的 systemctl 参数，由助手维护 root 所有的 `0700` 运行目录，在助手崩溃或重启后保留优先级撤销日志；235+ 使用 `RuntimeDirectoryPreserve=yes`。工具识别增加固定的 `workloads/0.1.0-el7/mprime/mprime` 和 `workloads/extra-0.2.0/memtester/memtester`，仍核对服务 cgroup、工作目录、启动参数和进程/线程启动时间。依据 [systemd 219 服务执行配置](https://raw.githubusercontent.com/systemd/systemd/v219/man/systemd.exec.xml) 生成兼容单元。

独立脚本要求 Linux x86_64 和 systemd 219+，平台不满足时明确报错。中心替换独立脚本后，再运行新版完整 setup 会更新受管副本，不自动运行；已被用户修改的副本会保留并报错。`--offline` 跳过 tools 同步；独立 P95 脚本自身可以离线安装。已有节点需要更新至 alpha.47 或更新版完整 setup，旧版仍有原来的自动 P95 步骤；新版不会自动卸载已经安装的助手。

运行混合测试时在节点执行 `/usr/local/sbin/p95-priority-fyhocsys status --seconds 10`，检查线程 nice、两种工具实际消耗的 CPU 核数及 cgroup/autogroup 信息。看到进程或少量 CPU 时间增长不足以证明负载充分，更不代表算法测试通过。停用时先执行 `systemctl stop p95-priority-fyhocsys.service`，再执行 `systemctl disable p95-priority-fyhocsys.service`；正常停止会恢复本工具记录的原优先级。sckocstp 使用对应产品名，并给状态命令加 `--product sckocstp`。

发布状态与实机验收范围见[当前进度](../development/progress.md)。助手安装/自检通过不等于真实 AMD 混合负载已验收。

- Ubuntu / Debian 选择本机架构的 DEB；EL 系列选择本机架构的 RPM。`all` / `noarch` 包也可使用。默认根据 RPM 的 EL 大版本匹配；例如 `.el9` 不发给 EL8。
- 名称、版本、Epoch、Release、架构以包内元数据为准。不同发行版之间的依赖兼容性由本机包管理器检查。
- 同一软件存在多个兼容版本时，使用原生 dpkg / RPM 比较选择最高版本。已安装相同或更新版本时跳过，不降级；新旧文件可暂时同时保留。同名、同版本、同架构但内容不同的重复包会停止并提示清理冲突。
- 清单和文件 SHA-256 未变化、已安装版本检查通过时，不重复下载或安装。请正确提高包版本号；原地重打同版本包不视作升级。
- 从服务器移除文件不会卸载节点已安装的软件，也不会设置后台定期软件更新。
- `software_rpm_min_el` 是带 `.elN` 标签 RPM 的向上兼容规则。原 `fyhocsys-node` EL8 构建包允许用于 EL8 及以上，不向 EL7 分发。用户于 2026-10-27 确认新版 `fyhocsys-node-0.8.4-1.x86_64.rpm` 已适配 EL7 及以上；这个通用包的文件名和包内版本均无 `.elN` 标签，现有分发与 setup 检查已允许 EL7 获取和安装，不受旧 EL8 标签规则限制。依赖仍由目标机包管理器检查；此声明不会扩大 `sckoct-fyh` 等其他包的适用范围。

需要专属软件组时，可使用 `系统/版本/架构/default/`：如 `ubuntu/22.04/amd64/default/`、`debian/12/amd64/default/`、`rocky/9/x86_64/default/`。专属组优先于根目录自动组。Ubuntu 精确匹配 `VERSION_ID`；EL / Debian 优先精确版本，其次大版本。不自动借用另一个 Ubuntu 版本的软件组。

## 依赖与结果

先下载并校验整组软件，读取包内信息，再做依赖和安装事务预检查。优先使用已安装的依赖和同时上传的依赖包；缺少依赖时从节点已配置的软件源获取。APT 仅在本次明确执行的安装需要时刷新索引；不会启用 APT 定时刷新或无人值守升级。普通依赖库可能随安装事务更新；不执行全系统 `upgrade` / `distro-sync`，不添加未知软件源或强制忽略依赖。

内核包不能通过软件分发安装；APT 事务中发现内核修改/软件删除会停止，RPM 依赖解析排除 `kernel*`。安装后再次对比内核包集合，并在已有策略时检查内核锁定和禁用自动更新。失败保留错误记录，不把部分完成标记为成功。包的维护脚本以 root 执行，应上传自己信任的软件；脚本失败后的部分改动不能保证自动回滚。

setup 会输出系统配置检查、APT 事务预演、实际安装及复查日志，因此同一清单可能出现两次。`apt update` 下载的是软件源索引；依赖事务中出现 `upgraded` 则确实表示对应依赖包升级，应按包名核对。登录页的 `New release ... available` 仅为发行版升级提示，不能当作已经升级的证据。以实际运行内核、已安装内核包集合和 APT 历史为准。

校验、下载、架构/EL 不匹配、依赖和安装错误返回非零。没有匹配软件时显示 `SKIPPED`。日志：`/var/log/ventoy-software.log`；最近事务：`/var/lib/ventoy-center/software/last-result.json`。完整配置流程中的日志也进入 `/var/log/ventoy-manual-init.log`。

RPM / DNF 即使报告 `%post` 等安装脚本失败，也可能以 0 退出且保留已安装包记录。setup 同时检查这类错误输出，并在 `rpm-scriptlet-failures.json` 保存受影响的包和版本；相同版本再次运行或执行软件检查仍报失败。发布并成功安装修正后的新版本可解除该版本对应的失败状态。无法确定所属包的脚本错误需要人工核查，不能仅凭 `rpm -q` 查到包就认定安装完整成功。

客户端内置中心 HTTPS 地址、公开 CA 和只读下载凭证，不含管理口令或安装任务凭证。管理口令轮换会使既有只读凭证失效，需要重新下载 setup。下载凭证不授予管理、上传、删除或远程执行权限。

依赖解析参考 [APT 官方手册](https://manpages.ubuntu.com/manpages/noble/man8/apt-get.8.html) 与 [DNF 官方命令参考](https://dnf.readthedocs.io/en/latest/command_ref.html)。

## 验证范围

2026-10-27，在 `.235` 普通 ISO 手动安装的 Rocky 10.0、双盘 RAID1 + LVM / XFS 上实际执行预置 setup，并指定 `--hostname s4-2495x1`。主机名持久配置与运行值一致，外部 root/user 密码 SSH、现有 DHCP、内核锁定和自动更新禁用检查通过；运行内核与全部 7 个内核包保持 `6.12.0-55.12.1.el10_0.x86_64`。`fyhoc -V` 返回 1.1.24，`fyhocsys-node --version` 返回 0.8.4，9 个压缩包及独立文件与中心摘要一致。安装依赖更新了 15 个非内核包（包括 OpenSSL、OpenSSH 等），未执行全系统或内核升级。

同次事务发现 `sckoct-fyh-1.1.8-1.el10` 的 `%post` 运行其自带 Python/Cython 模块时发生 `__Pyx_GetCurrentInterpreterId failed`，旧 setup 错误地报告软件组成功。修复后的检测已通过隔离 RPM/DNF 的失败脚本、重复运行、修正版升级测试，并在 `.235` 根据原日志恢复真实失败记录，重新运行明确返回失败；这不是该软件包本身已经修复。原生事务回归使用独立 Rocky 9 测试根；Rocky 10 实机验证使用本次实际错误日志及已安装包状态。该修复纳入 alpha.40，中心下载与全部 Linux 手动/PXE 预置包使用同一软件检查实现。

2026-10-25，用户在 `.235` 新装 Ubuntu 22.04.3 后无参数运行 setup。现场只读核对确认 `fyhoc 1.1.24-1`、`fyhocsys-node 0.8.3-1`、`sckoct-fyh 1:1.1.8-1` 均已安装；为补齐依赖，APT 新装 ipmitool/libatomic1 等包，并将 `gcc-12-base`、`libgcc-s1`、`libstdc++6` 从 `12.3.0-1ubuntu1~22.04` 升到 `12.3.0-1ubuntu1~22.04.3`。未执行全系统升级，运行内核及唯一已安装内核仍为 `5.15.0-78-generic`（包版本 `5.15.0-78.85`），hold 保留，五个 APT/无人值守更新单元全部 masked/inactive，APT 周期配置均为 0。软件请求完成；附加网卡 `enp188s0f1` 的 IPv4 DHCP 租约仍待获取，因此系统总状态是 `PENDING`，不等于软件安装失败或内核已更新。

alpha.32 在 Ubuntu 24.04.3 双盘 RAID1/LVM 实机上直接无参数运行 setup，安装并检查 `fyhoc 1.1.24-1`、`fyhocsys-node 0.8.2-1`、`sckoct-fyh 1:1.1.8-1`；`fyhoc -V` 与依赖 `ipmitool -V` 实际执行成功。`ipmitool-IPMITOOL_1_8_19.tar.gz` 原样传到 `/root/ventoy-tools/`，与中心摘要一致且未解压。重复运行不再下载软件包或压缩包；SSH、DHCP、内核锁定及禁用自动更新复查通过，内核保持 `6.8.0-71-generic`。所有 54 个普通 Linux 入口及 52 个 PXE 入口已更新预置包并核对摘要；此处不代表全部发行版都重新做过实机安装。

alpha.29 在 Ubuntu 24.04.3 隔离虚拟机中实际安装了 `fyhoc 1.1.24-1`、`fyhocsys-node 0.8.2-1`、`sckoct-fyh 1:1.1.8-1`，验证缺失依赖获取、第二次运行跳过、已安装版本回读及原有内核/更新策略。RPM 在隔离的 Rocky 9 根文件系统中使用真实 RPM / DNF 验证整组事务、仓库补齐依赖、原生版本排序、升级、不降级及失败时不进入安装事务。

这些结果验证分发机制；不代表所有软件在全部发行版或真实硬件上的运行功能均已验收。软件自身的接入配置和硬件功能仍按其要求执行。
