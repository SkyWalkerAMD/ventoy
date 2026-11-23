# 日常装机与发布维护

本文说明当前操作。旧测试记录中的 `ventoy-center/PXE-Auto` 是历史入口；现在从发行版目录选择同一个 ISO，再选择手动或自动安装脚本。

## 装机与 setup

1. BIOS/UEFI 从网卡启动，进入 iVentoy，选择发行版目录中的系统版本。
2. 不选择自动脚本时进入原安装器手动安装；选择自动脚本时进入本机安装流程。
3. 自动安装可选 ext4/XFS：红帽系默认 XFS，Ubuntu/Debian 默认 ext4。多盘、旧 LVM/软件 RAID 在本机选盘或 RAID1，核对分区容量后输入 `yes`；跨未选盘的存储仍会停止。
4. 系统正常重启到硬盘后，在带外确认登录提示、主机名和 IP，通过 SSH 实际登录。
5. 手动安装保留安装器的账户和网络；预置文件不等于已运行完整配置。以 root 执行 `./ventoy-linux-setup.run`，按提示设置主机名、可选 root 新密码，并检查 SSH、DHCP、内核/更新策略、E610 状态及中心软件结果。自动安装后同样可以运行 setup 获取 tools 最新软件。

setup 的各阶段有 `SETUP_STAGE` 标记。退出 0 表示本次请求完成；3 表示 DHCP/驱动/固件仍待处理；4 表示软件步骤失败，不能因为 RPM 数据库里有包记录就视为成功。详细日志在 `/var/log/ventoy-manual-init.log`，软件结果在 `/var/lib/ventoy-center/software/last-result.json`。`--check` 不重新安装，`--software` 单独重试软件。

已有系统无需重装即可升级 setup 并应用新增功能。alpha.50 起执行：

```bash
./ventoy-linux-setup.run --version
./ventoy-linux-setup.run --check-version
./ventoy-linux-setup.run --upgrade
```

`--upgrade` 使用原包中的中心 HTTPS 信任和软件读取凭据，验证长度及 SHA-256，保留 `.previous-摘要` 旧文件后原子替换，然后运行新版完整配置和检查。即使文件已是最新版，也会应用尚未执行的新配置、同步 tools、安装或升级匹配软件。下载失败停止，不用旧包继续冒充升级成功。已完成过 setup 的账户密码、现有主机名和已配置网络会保留；仍可在提示中主动改主机名或 root 密码。内核保持锁定，P95 仍是独立脚本，不自动执行。

alpha.49 的旧文件第一次升级使用下面两步（使用 `bash` 也可处理传输后丢失执行权限的文件）：

```bash
bash ventoy-linux-setup.run --update-setup
./ventoy-linux-setup.run
```

alpha.48 及更早的旧包不能识别 `--upgrade` 或 `--update-setup`。从中心 tools 目录取得 `ventoy-setup-upgrade.sh`，放在旧 setup 同目录，以 root 执行一次：

```bash
bash ventoy-setup-upgrade.sh
```

助手只解析旧包内的中心地址、读取凭据和 CA，不执行旧安装脚本；通过原有 HTTPS 信任校验下载，备份旧文件，修复执行权限和 `.sha256`，再运行新版 `--upgrade --keep-passwords`。主机名和现有密码保留，交互运行仍可主动修改。之后直接使用 `./ventoy-linux-setup.run --upgrade`。可用 `--runner /完整路径/ventoy-linux-setup.run` 指定文件，`--check-version` 只查看，`--update-setup` 只更新不应用。没有中心配置的更早包仍需从管理端下载新版一次。不要把本机的旧 setup 上传回中心 tools 覆盖已发布文件。

从 alpha.52 起，即使文件内容已经是最新版，使用 `bash ventoy-linux-setup.run --update-setup` 或 `--upgrade` 也会修复执行权限并同步校验文件。

`--update-setup` 保持“只下载替换、不执行”；`--check-version` 分别显示当前文件、中心版本及上次通过系统配置检查的版本。新版按内容摘要迁移旧配置和服务，修复旧 `configured` 标记跳过新策略的问题；失败保留重试条件，正常重启不反复迁移同一版本。不创建后台自动升级任务，不要求重装或自动重启。退出 3/4 的待办或失败须继续处理，下载完成不等于所有功能验收通过。

## 版本发布与回退

管理端“版本与维护”显示版本、全部入口预置版本、setup 校验值、依赖缓存与维护快照。“校验全部入口文件”执行只读内容校验；版本文字一致不能替代文件校验。

在中心 Linux 服务器以 root 运行源码包中的维护工具，配置中的路径必须是绝对路径。程序包和源码放在菜单外；所有临时配置、凭据、备份保存在 root 专属目录，不能放入 Git 或 tools。

```bash
python3 deploy/release.py stage --releases /home/ventoy-center/releases \
  --name alpha49 --candidate /path/to/new/ventoy-center --commit COMMIT_SHA
python3 deploy/release.py verify --releases /home/ventoy-center/releases --name alpha49
python3 deploy/release.py activate --releases /home/ventoy-center/releases --name alpha49
python3 deploy/release.py activate --releases /home/ventoy-center/releases --name alpha49 --apply
```

`stage` 不停止生产服务。它通过隔离管理进程生成所有已绑定入口及 setup，校验 ISO 身份、入口文件、各预置包中的 setup 字节一致性。当前仅支持已经共用 ISO、文件名及绑定不变的发布；新增或改变绑定需单独迁移。

`activate` 默认只核对；`--apply` 才发布。它检查活动任务及网络镜像连接，备份原二进制、setup、入口配置，短暂停止服务后原子替换。失败会恢复旧版本。任务记录不会被历史快照覆盖。服务健康与文件一致性属于软件验证，不代表所有硬件安装成功。

tools 中的 setup 保持 root 所有，给予管理数据所属组只读权限（0740），供管理服务核对实际文件。发布完成前还会用管理服务身份校验全部入口和 tools 文件；无法读取或内容不一致都会回退。回退恢复原来的文件权限。

发布与回退均保存并恢复 iVentoy 的网络运行状态、接口和地址参数；检查原生 PXE 状态，不能仅以 systemd 进程在线判断已恢复。原先正在服务的中心必须回到 `running`，原先主动停止的中心保持 `ready`。

iVentoy 1.0.50 的启动信息可以同时选择 IPv4 和 IPv6。发布工具读取原生页面已选中的两个地址，并在恢复后核对。双栈部署还需在防火墙和 iVentoy systemd 服务的地址白名单中允许实际装机网段；从同网段客户端分别验证两个协议的引导文件。

iVentoy 的原生 `data/config.dat` 同样单独备份并校验，停止服务后原子恢复，再启动。这样可避免原生配置保存被中断，重启后默默回到默认 DHCP/Secure Boot 设置或丢失安装脚本绑定。运行中的中心会对全部镜像绑定及全局设置逐项回读；差异导致发布失败并回退。备份期间若检测到操作员修改原生配置，发布停止。

```bash
python3 deploy/release.py rollback --releases /home/ventoy-center/releases --name alpha49
python3 deploy/release.py rollback --releases /home/ventoy-center/releases --name alpha49 --apply
```

只允许回退当前发布，或恢复中断于 `activating` 的发布。仍要求没有安装客户端；若备份完整性或入口清单改变则停止。磁盘损坏、断电等无法自动恢复时，保留发布目录和 transaction.json 供恢复，不要覆盖其中内容。

## 依赖预热与缓存

缓存默认最多 4 个并行下载（`installer_cache_concurrency` 可设 1–16）；同一文件合并请求。下载体开始前预留空间，失败和不完整内容不发布。容量默认 8 GiB，受限对象最大 256 MiB。APT 仍验证官方签名与包哈希；缓存不改变原始内容、不放宽过期检查。

预热在独立、可丢弃的 Linux 根目录执行，不在中心系统安装 APT 包。根目录需已有 apt-get、对应官方 keyring 和可用 DNS；需准备其正常运行所需的 `/dev`、`/proc`，并建议用私有 mount namespace。不要使用中心根目录或正在运行的目标机根目录。确认后在隔离根目录建立 `.ventoy-cache-disposable` 标记。

```bash
python3 deploy/warm-installer-cache.py --apt-root /path/to/disposable-apt-root \
  --origin ubuntu --suite jammy --keyring /usr/share/keyrings/ubuntu-archive-keyring.gpg \
  --cache-url http://192.168.1.2:26081/installer-cache \
  --output /var/lib/ventoy-center/data/cache-warm/ubuntu-jammy.json
```

该工具使用空的包状态和独立源配置下载 SSH/UEFI 引导程序及其依赖，不安装软件、不执行系统升级。Debian 使用 `--origin debian --suite bookworm` 和 Debian 官方 keyring。EL 安装仍优先使用本地 DVD。预热完成是带时间的依赖验证，不能据此承诺所有版本完全离线安装；管理页面保留各次预热结果。报告文件需要允许管理服务账户读取。

## 磁盘与备份

```bash
python3 deploy/maintenance.py --releases /home/ventoy-center/releases --report
python3 deploy/maintenance.py --releases /home/ventoy-center/releases --apply --report
```

默认只列出占用和候选。只清理新发布工具标记的版本目录，保留当前版本、最近两个版本及至少七天历史。挂载、符号链接、最后一份 ISO、未知历史构建目录均不清理。不会删除原始镜像、工具软件或机器任务记录。发布目录中的 ISO 是硬链接，目录逻辑大小不等于可释放空间。

管理端显示快照时间，以及 85%/95% 用量提示；目录占用可现场重新核对，实际文件系统余量由维护命令更新。没有默认周期删除任务。

## 验收记录

“实机验收”按系统、手动/自动、Intel/AMD/VM、单盘/硬 RAID/软件 RAID1+LVM 保存操作员确认。登记实际 setup 版本，不能用新管理端版本冒充旧安装的验收版本。通过需确认首次硬盘启动、再次重启、SSH、带外登录、DHCP、内核/更新策略、分区和 setup 八项。

安装报告会带 machine ID、安装 attempt ID、boot ID、版本和平台等观察信息；两次不同 boot ID 的报告便于核对重启。报告可关联，但不会自动变成实机验收通过。可导出 JSON；新版本缺少记录时显示待验收，历史通过单独标识。本轮实机验收由操作员执行。
