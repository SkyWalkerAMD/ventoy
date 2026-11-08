package center

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

const Version = "0.3.0-alpha.58"

type Config struct {
	Listen                    string         `json:"listen"`
	PublicURL                 string         `json:"public_url"`
	DataDir                   string         `json:"data_dir"`
	ISODir                    string         `json:"iso_dir"`
	PackageDir                string         `json:"package_dir"`
	SoftwareDir               string         `json:"software_dir,omitempty"`
	InstallerCacheDir         string         `json:"installer_cache_dir,omitempty"`
	InstallerCacheListen      string         `json:"installer_cache_listen,omitempty"`
	InstallerCacheURL         string         `json:"installer_cache_url,omitempty"`
	InstallerCacheMaxBytes    int64          `json:"installer_cache_max_bytes,omitempty"`
	InstallerCacheConcurrency int            `json:"installer_cache_concurrency,omitempty"`
	SoftwareRPMMinEL          map[string]int `json:"software_rpm_min_el,omitempty"`
	FYHOCUnlockPasswordFile   string         `json:"fyhoc_unlock_password_file,omitempty"`
	NodeJoinConfigFile        string         `json:"node_join_config_file,omitempty"`
	LinuxSetupPreload         bool           `json:"linux_setup_preload,omitempty"`
	AdminTokenFile            string         `json:"admin_token_file"`
	TLSCert                   string         `json:"tls_cert_file"`
	TLSKey                    string         `json:"tls_key_file"`
	BootstrapCA               string         `json:"bootstrap_ca_file"`
	IVentoyURL                string         `json:"iventoy_url"`
	IVentoyRoot               string         `json:"iventoy_root,omitempty"`
	FYHOCSYSURL               string         `json:"fyhocsys_url"`
	LinuxInitialPasswordHash  string         `json:"linux_initial_password_hash,omitempty"`
	LinuxAdminUsername        string         `json:"linux_admin_username,omitempty"`
}

func randomID(n int) string {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	return hex.EncodeToString(b)
}

func Initialize(dir string) error {
	abs, err := filepath.Abs(dir)
	if err != nil {
		return err
	}
	if err = os.MkdirAll(abs, 0700); err != nil {
		return err
	}
	path := filepath.Join(abs, "config.json")
	if _, err = os.Stat(path); err == nil {
		return errors.New("configuration already exists; retained")
	}
	tokenPath := filepath.Join(abs, "admin.token")
	if err = writeNew(tokenPath, []byte(randomID(32)+"\n")); err != nil {
		return err
	}
	c := Config{Listen: "127.0.0.1:26080", PublicURL: "http://127.0.0.1:26080", DataDir: filepath.Join(abs, "data"), ISODir: filepath.Join(abs, "iso"), PackageDir: filepath.Join(abs, "packages"), AdminTokenFile: tokenPath, IVentoyURL: "http://127.0.0.1:26000"}
	for _, p := range []string{c.DataDir, c.ISODir, c.PackageDir} {
		if err = os.MkdirAll(p, 0700); err != nil {
			return err
		}
	}
	b, _ := json.MarshalIndent(c, "", "  ")
	return writeNew(path, append(b, '\n'))
}

func writeNew(path string, data []byte) error {
	f, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return err
	}
	_, err = f.Write(data)
	if err == nil {
		err = f.Sync()
	}
	e := f.Close()
	if err != nil {
		return err
	}
	return e
}

func loadConfig(path string) (Config, error) {
	var c Config
	b, err := os.ReadFile(path)
	if err != nil {
		return c, err
	}
	if err = json.Unmarshal(b, &c); err != nil {
		return c, err
	}
	if c.LinuxInitialPasswordHash != "" && !hashRE.MatchString(c.LinuxInitialPasswordHash) {
		return c, errors.New("linux_initial_password_hash must be a SHA-512 crypt hash")
	}
	for name, major := range c.SoftwareRPMMinEL {
		if !regexp.MustCompile(`^[a-zA-Z0-9][a-zA-Z0-9+_.-]{0,120}$`).MatchString(name) || major < 7 || major > 99 {
			return c, errors.New("invalid software_rpm_min_el compatibility rule")
		}
	}
	if c.LinuxAdminUsername != "" && (!userRE.MatchString(c.LinuxAdminUsername) || c.LinuxAdminUsername == "root" || c.LinuxAdminUsername == "operator") {
		return c, errors.New("linux_admin_username must be a valid non-root administrator name")
	}
	base, _ := filepath.Abs(filepath.Dir(path))
	if c.InstallerCacheMaxBytes < 0 {
		return c, errors.New("installer_cache_max_bytes must not be negative")
	}
	if c.InstallerCacheConcurrency < 0 || c.InstallerCacheConcurrency > 16 {
		return c, errors.New("installer_cache_concurrency must be 1–16, or 0 for default 4")
	}
	for _, p := range []*string{&c.DataDir, &c.ISODir, &c.PackageDir, &c.SoftwareDir, &c.InstallerCacheDir, &c.FYHOCUnlockPasswordFile, &c.NodeJoinConfigFile, &c.AdminTokenFile, &c.TLSCert, &c.TLSKey, &c.BootstrapCA, &c.IVentoyRoot} {
		if *p != "" && !filepath.IsAbs(*p) {
			*p = filepath.Join(base, *p)
		}
	}
	if c.NodeJoinConfigFile != "" {
		if c.SoftwareDir == "" {
			return c, errors.New("node_join_config_file requires software_dir")
		}
		if !nodeJoinFileOutsideSoftware(c.NodeJoinConfigFile, c.SoftwareDir) {
			return c, errors.New("node_join_config_file must be outside software_dir")
		}
	}
	if c.FYHOCUnlockPasswordFile != "" && c.SoftwareDir != "" {
		rel, err := filepath.Rel(c.SoftwareDir, c.FYHOCUnlockPasswordFile)
		if err == nil && rel != ".." && !strings.HasPrefix(rel, ".."+string(filepath.Separator)) && !filepath.IsAbs(rel) {
			return c, errors.New("fyhoc_unlock_password_file must be outside software_dir")
		}
	}
	c.PublicURL = strings.TrimRight(c.PublicURL, "/")
	u, err := url.Parse(c.PublicURL)
	if err != nil || u.Host == "" || u.User != nil || u.RawQuery != "" || u.Fragment != "" || u.Path != "" || (u.Scheme != "http" && u.Scheme != "https") {
		return c, errors.New("public_url must be an HTTP(S) origin without a path or credentials")
	}
	if c.InstallerCacheListen != "" || c.InstallerCacheURL != "" {
		cu, ce := url.Parse(c.InstallerCacheURL)
		ch, cp, le := net.SplitHostPort(c.InstallerCacheListen)
		ip := net.ParseIP(u.Hostname())
		if ce != nil || le != nil || c.InstallerCacheDir == "" || cu.Scheme != "http" || cu.Hostname() != u.Hostname() || cu.Port() != cp || cu.User != nil || cu.Path != "" || cu.RawQuery != "" || cu.Fragment != "" || ip == nil || ip.To4() == nil || !(ip.IsPrivate() || ip.IsLoopback()) || (ch != u.Hostname() && ch != "0.0.0.0" && ch != "::") {
			return c, errors.New("installer cache requires a dedicated HTTP listener on the private controller address, matching URL and a cache directory")
		}
	}
	host, _, err := net.SplitHostPort(c.Listen)
	if err != nil {
		return c, fmt.Errorf("listen: %w", err)
	}
	loopback := func(h string) bool { ip := net.ParseIP(h); return ip != nil && ip.IsLoopback() }
	if u.Scheme != "https" && !(loopback(host) && loopback(u.Hostname())) {
		return c, errors.New("LAN deployment requires HTTPS; HTTP is only allowed on loopback")
	}
	if (c.TLSCert == "") != (c.TLSKey == "") {
		return c, errors.New("both TLS certificate and key are required")
	}
	if !loopback(host) && c.TLSCert == "" {
		return c, errors.New("non-loopback listener requires a TLS certificate and key")
	}
	if c.DataDir == "" || c.ISODir == "" || c.PackageDir == "" || c.AdminTokenFile == "" {
		return c, errors.New("data, ISO, package and admin-token paths are required")
	}
	for _, v := range []string{c.IVentoyURL, c.FYHOCSYSURL} {
		if v == "" {
			continue
		}
		p, e := url.Parse(v)
		if e != nil || p.Host == "" || p.User != nil || (p.Scheme != "http" && p.Scheme != "https") {
			return c, errors.New("invalid service URL")
		}
	}
	return c, nil
}

// Snapshot the configured policy when issuing a task. Changing the service
// configuration must not change credentials in an already issued installer.
func (c Config) applyLinuxAccounts(r *JobRequest) {
	if r.OS == "windows" {
		return
	}
	if c.LinuxAdminUsername != "" {
		r.Username = c.LinuxAdminUsername
	}
	if c.LinuxInitialPasswordHash != "" {
		r.PasswordHash = c.LinuxInitialPasswordHash
		r.RootPasswordHash = c.LinuxInitialPasswordHash
	}
}
