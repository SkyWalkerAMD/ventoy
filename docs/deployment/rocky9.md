# Rocky Linux 9：与 fyhocsys 共机部署

目标为现有 Rocky Linux 9.8 管理服务器。以下步骤安装新服务，不重装该服务器。先在独立测试客户端验收；真正被清盘的是任务中指定的客户端磁盘。

## 1. 安装管理端

先运行 `sh deploy/inspect-linux.sh` 做只读检查，确认旧 TFTP / DHCP 和端口占用。替换旧 PXE 前核对服务用途；保留原目录，不把停用 TFTP 扩大为停用已有 DHCP。

使用 CI 的 `ventoy-center-packages` 产物，核对 `SHA256SUMS`，解压 Linux 包，在解压目录执行：

```sh
sudo sh deploy/install-linux.sh ./ventoy-center
```

脚本创建独立 `ventoy-center` 用户和 systemd 服务，保留已有配置。首次安装后配置位于 `/var/lib/ventoy-center/config.json`，管理口令位于同目录 `admin.token`。脚本准备服务但不自动启动；初始化的监听地址只允许本机访问。

## 2. 配置地址和 TLS

将服务证书、私钥和给安装环境使用的 CA 证书放在该用户可读的受限目录，例如 `/var/lib/ventoy-center/tls/`。证书 SAN 必须包含下面 `public_url` 使用的 DNS 名或 IP。

配置示例（全部地址、名称是示例，需替换）：

```json
{
  "listen": "0.0.0.0:26080",
  "public_url": "https://deploy.example.internal:26080",
  "data_dir": "/var/lib/ventoy-center/data",
  "iso_dir": "/var/lib/ventoy-center/iso",
  "package_dir": "/var/lib/ventoy-center/packages",
  "admin_token_file": "/var/lib/ventoy-center/admin.token",
  "tls_cert_file": "/var/lib/ventoy-center/tls/server.crt",
  "tls_key_file": "/var/lib/ventoy-center/tls/server.key",
  "bootstrap_ca_file": "/var/lib/ventoy-center/tls/ca.crt",
  "iventoy_url": "http://deploy.example.internal:26000",
  "fyhocsys_url": ""
}
```

CA 文件仅放公有证书。客户端安装环境能解析该域名、校准时间并访问此 HTTPS 地址；使用 IP 时证书需要 IP SAN。不要使用跳过证书验证的参数。Windows 的初始化下载会把配置的 CA 导入本机信任根，因此这里只能指定你的部署 CA。

新管理端用 TCP 26080，现有 fyhocsys 继续使用 TCP 443。iVentoy 仍使用自己的端口。防火墙仅允许实际的装机和管理网段，不关闭现有防火墙，不更改 fyhocsys 允许网段。

使用 firewalld 时，规则需要同时写入运行配置和永久配置。只执行 `--add-rich-rule` 的临时规则会在服务器重启或防火墙重载后丢失。先用 `firewall-cmd --get-active-zones` 核对管理网卡所属区域；以下仅演示允许示例管理网段访问管理端，按实际地址替换：

```sh
rule='rule family="ipv4" source address="192.168.0.0/23" destination address="192.168.1.2" port port="26080" protocol="tcp" accept'
sudo firewall-cmd --zone=public --add-rich-rule="$rule"
sudo firewall-cmd --permanent --zone=public --add-rich-rule="$rule"
sudo firewall-cmd --zone=public --query-rich-rule="$rule"
sudo firewall-cmd --permanent --zone=public --query-rich-rule="$rule"
sudo firewall-cmd --check-config
```

为 iVentoy 按 [PXE 端口说明](pxe.md)分别配置所需端口和来源网段；ProxyNet 模式尤其需要 UDP 4011。无需为这些新增规则重载整个防火墙，也不要用 `--runtime-to-permanent` 覆盖其他服务的临时配置。规则保存后，从实际管理电脑和测试客户端验证，服务器本机 HTTP 200 不能证明外部访问正常。

```sh
sudo systemctl enable --now ventoy-center
sudo systemctl status ventoy-center
sudo journalctl -u ventoy-center -n 50 --no-pager
```

使用浏览器登录 `public_url`。状态数据库是 `data/state.json`，其中有安装时限内凭据与配置秘密；备份整个私有运行目录，不放进 Git。当前只能运行一个管理端实例。

## 3. 镜像和 iVentoy

1. 把合法持有的 ISO 放到 `iso_dir`。目录和文件名按 iVentoy 要求使用无空格的 ASCII 名称。
2. 单独安装 iVentoy Linux x86-64，专业版授权保存在其 `data` 目录。不要把该目录纳入本项目仓库。
3. 在 iVentoy 的 `iso` 目录建立到镜像的链接，或把管理端的 `iso_dir` 指向 iVentoy 的实际镜像目录。确保两项服务有对应读取权限。当前管理端扫描不递归进入符号链接目录，宜直接配置真实目录。
4. 按[同机文件准备](iventoy-files.md)配置 `iventoy_root`、专用目录权限和 systemd 写目录。
5. 继续按 [PXE 配置](pxe.md) 配合已有 DHCP，先使用正常手工安装镜像验证网卡能引导。

## 4. 准备安装目标

按 [Linux 安装版本](linux-targets.md)选择实际镜像和系统 profile。操作系统安装和 fyhocsys 节点接入可独立部署。生成 Linux setup 或预置包时，将[指定版本的 E610 离线包](manual-linux.md#检查结果和边界)放入 `package_dir`。节点 RPM / DEB 则由 `software_dir` 分发，接入配置见[节点软件分发](node-software.md)。

Debian 模板需要显式配置 `bootstrap_ca_file`，并保证客户端可访问 Debian 镜像源。使用 CentOS/Rocky 完整 DVD ISO，Ubuntu 使用对应版本的 live-server ISO。

## 5. 验收顺序

1. 先验证管理端登录与镜像列表，再验证单台客户端 PXE 进入镜像菜单。
2. 用已备份且允许清空的测试机，核对 MAC、磁盘序列号与固件模式。
3. 新建并授权任务，导入安装包与按 MAC 启动规则，从客户端 Boot 菜单选择网卡。
4. 检查只清空指定盘、安装成功、首次磁盘启动、账号登录、网络连接及管理端 `installed` 回报。
5. 删除本次 MAC 启动规则和 ISO 别名；再验证旧安装包重放被拒绝。
6. 通过后再扩大机器数量并记录带宽、磁盘和 DHCP 压力。单元测试不代替这些硬件测试。

安装中断后不要直接重用旧授权。先确认目标机器已停止安装并保留日志。确认安装已停止后，可在任务操作中选择“结束失败任务”，输入节点名与原因并确认停止，再创建新的任务。结单只结束记录，不能代替停止客户端安装。
