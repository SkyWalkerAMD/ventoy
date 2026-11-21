package center

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"io/fs"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

// Packages are uploaded by an administrator through SFTP/local file operations.
// The service only reads this tree. Standard package filenames at its root form
// automatic groups; optional distribution/version/architecture/default groups
// take precedence. Rename staged files/directories only after upload completes.
const softwareMaxFile = int64(4 << 30)
const softwareMaxGroup = int64(8 << 30)

var softwareVersionRE = regexp.MustCompile(`^[0-9]+(\.[0-9]+){0,2}$`)
var softwareFileRE = regexp.MustCompile(`^[a-zA-Z0-9][a-zA-Z0-9._+~-]{0,240}\.(deb|rpm)$`)
var softwareArchiveRE = regexp.MustCompile(`^[a-zA-Z0-9][a-zA-Z0-9._+~-]{0,240}\.(tar\.gz|tgz|zip)$`)
var softwareCopyRE = regexp.MustCompile(`^[a-zA-Z0-9][a-zA-Z0-9._+~-]{0,247}$`)
var softwareHashRE = regexp.MustCompile(`^[0-9a-f]{64}$`)
var softwareELRE = regexp.MustCompile(`\.el([0-9]+)([._-]|$)`)

// The tools root is a distribution directory. Non-package files are copied
// without execution. Keep upload scratch files and the generated setup out.
func softwareCopyName(name string) bool {
	if !softwareCopyRE.MatchString(name) || softwareArchiveRE.MatchString(name) {
		return false
	}
	lower := strings.ToLower(name)
	if strings.HasPrefix(lower, "ventoy-linux-setup.run") {
		return false
	}
	for _, suffix := range []string{".deb", ".rpm", ".part", ".partial", ".tmp", ".download", ".crdownload", ".swp", ".bak", "~"} {
		if strings.HasSuffix(lower, suffix) {
			return false
		}
	}
	return true
}

// Flat uploads follow standard RPM/DEB filenames. Native package metadata is
// independently checked on the node before installation; extensions alone do
// not establish installability or dependency compatibility.
func (s *Server) softwareFlatMatch(name, id, version, arch string) bool {
	if !softwareFileRE.MatchString(name) {
		return false
	}
	if softwareFamily(id) == "deb" {
		return strings.HasSuffix(name, "_"+arch+".deb") || strings.HasSuffix(name, "_all.deb")
	}
	if !(strings.HasSuffix(name, "."+arch+".rpm") || strings.HasSuffix(name, ".noarch.rpm")) {
		return false
	}
	if m := softwareELRE.FindStringSubmatch(name); m != nil {
		major, _ := strconv.Atoi(strings.Split(version, ".")[0])
		built, _ := strconv.Atoi(m[1])
		if built == major {
			return true
		}
		for packageName, minimum := range s.config.SoftwareRPMMinEL {
			if strings.HasPrefix(name, packageName+"-") && built >= minimum && major >= built {
				return true
			}
		}
		return false
	}
	return true
}

type SoftwareFile struct {
	Path   string `json:"path"`
	Size   int64  `json:"size"`
	SHA256 string `json:"sha256,omitempty"`
}
type SoftwareGroup struct {
	ID       string         `json:"id"`
	OS       string         `json:"os"`
	Version  string         `json:"version"`
	Arch     string         `json:"arch"`
	Files    []SoftwareFile `json:"files"`
	Errors   []string       `json:"errors,omitempty"`
	RPMMinEL map[string]int `json:"rpm_min_el,omitempty"`
}

func softwareFamily(id string) string {
	switch id {
	case "ubuntu", "debian":
		return "deb"
	case "centos", "rocky", "almalinux", "rhel", "ol", "scientific", "anolis":
		return "rpm"
	}
	return ""
}

func softwareTarget(id, version, arch string) bool {
	family := softwareFamily(id)
	return softwareVersionRE.MatchString(version) && ((family == "deb" && (arch == "amd64" || arch == "arm64")) || (family == "rpm" && (arch == "x86_64" || arch == "aarch64")))
}

func (s *Server) softwareToken() string {
	// Domain-separated read-only capability. It cannot authorize admin/job APIs.
	h := hmac.New(sha256.New, []byte(s.admin))
	h.Write([]byte("ventoy-center/software/read-only/v1"))
	return hex.EncodeToString(h.Sum(nil))
}

func (s *Server) softwareAuth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !sameToken(bearer(r), s.softwareToken()) {
			fail(w, 401, "Software download credential required")
			return
		}
		if s.config.SoftwareDir == "" {
			fail(w, 409, "Software library is not configured")
			return
		}
		next(w, r)
	}
}

func (s *Server) addSoftwareClient(files map[string][]byte) {
	c := map[string]any{"schema": 1, "enabled": s.config.SoftwareDir != ""}
	if s.config.SoftwareDir != "" {
		c["url"], c["token"] = s.config.PublicURL, s.softwareToken()
		// Capability only: private join settings are fetched at execution time,
		// so key rotation never requires rebuilding setup or installer media.
		c["node_join"] = true
		c["fyhoct_install"] = s.config.FYHOCTInstallKeyFile != ""
		if len(s.ca) > 0 {
			files["software-ca.crt"] = s.ca
			c["ca_file"] = "software-ca.crt"
		}
	}
	files["software-client.json"], _ = json.MarshalIndent(c, "", "  ")
}

func (s *Server) softwareGroups() ([]SoftwareGroup, []string, error) {
	groups := []SoftwareGroup{}
	warnings := []string{}
	if s.config.SoftwareDir == "" {
		return groups, warnings, nil
	}
	byID := map[string]*SoftwareGroup{}
	count := 0
	err := filepath.WalkDir(s.config.SoftwareDir, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		count++
		if count > 20000 {
			return fmt.Errorf("software tree exceeds 20000 entries")
		}
		rel, err := filepath.Rel(s.config.SoftwareDir, p)
		if err != nil {
			return err
		}
		if rel == "." {
			return nil
		}
		rel = filepath.ToSlash(rel)
		parts := strings.Split(rel, "/")
		if strings.HasPrefix(d.Name(), ".") {
			if d.IsDir() {
				return fs.SkipDir
			}
			return nil
		}
		if d.IsDir() {
			if len(parts) > 4 {
				return fs.SkipDir
			}
			return nil
		}
		if filepath.Ext(rel) != ".deb" && filepath.Ext(rel) != ".rpm" {
			return nil
		}
		if len(parts) == 1 && softwareFileRE.MatchString(rel) {
			return nil
		}
		if len(parts) != 5 || parts[3] != "default" || !softwareTarget(parts[0], parts[1], parts[2]) {
			warnings = append(warnings, "未发布（目录应为 系统/版本/架构/default）："+rel)
			return nil
		}
		id := strings.Join(parts[:4], "/")
		g := byID[id]
		if g == nil {
			g = &SoftwareGroup{ID: id, OS: parts[0], Version: parts[1], Arch: parts[2], Files: []SoftwareFile{}}
			byID[id] = g
		}
		info, err := d.Info()
		if err != nil {
			return err
		}
		if !info.Mode().IsRegular() || !softwareFileRE.MatchString(d.Name()) || filepath.Ext(rel) != "."+softwareFamily(g.OS) || info.Size() <= 0 || info.Size() > softwareMaxFile {
			g.Errors = append(g.Errors, "无效文件、格式或大小："+rel)
			return nil
		}
		g.Files = append(g.Files, SoftwareFile{Path: rel, Size: info.Size()})
		return nil
	})
	if err != nil {
		return nil, nil, err
	}
	for _, g := range byID {
		var total int64
		for _, f := range g.Files {
			total += f.Size
		}
		if len(g.Files) > 256 || total > softwareMaxGroup {
			g.Errors = append(g.Errors, "软件组超过 256 个包或 8 GiB")
		}
		groups = append(groups, *g)
	}
	sort.Slice(groups, func(i, j int) bool { return groups[i].ID < groups[j].ID })
	return groups, warnings, nil
}

func (s *Server) softwareOverview(w http.ResponseWriter, r *http.Request) {
	groups, warnings, err := s.softwareGroups()
	if err != nil {
		fail(w, 500, "无法读取软件目录，请检查目录和服务账户权限")
		return
	}
	flat, err := s.flatSoftware()
	if err != nil {
		fail(w, 500, "Cannot read flat software directory")
		return
	}
	archives, err := s.softwareArchives()
	if err != nil {
		fail(w, 500, "Cannot read software archive directory")
		return
	}
	copies, err := s.softwareCopies()
	if err != nil {
		fail(w, 500, "Cannot read software copy directory")
		return
	}
	respond(w, 200, map[string]any{"enabled": s.config.SoftwareDir != "", "directory": s.config.SoftwareDir, "groups": groups, "flat_files": flat, "archive_files": archives, "copy_files": copies, "warnings": warnings})
}

func (s *Server) flatSoftware() ([]SoftwareFile, error) {
	return s.softwareRootFiles(softwareFileRE.MatchString)
}

// Root-level tar.gz, tgz and zip files are distributed unchanged to every supported Linux
// target. They are not installable packages and are never extracted/executed.
func (s *Server) softwareArchives() ([]SoftwareFile, error) {
	return s.softwareRootFiles(softwareArchiveRE.MatchString)
}

func (s *Server) softwareCopies() ([]SoftwareFile, error) {
	return s.softwareRootFiles(softwareCopyName)
}

func (s *Server) softwareRootFiles(match func(string) bool) ([]SoftwareFile, error) {
	files := []SoftwareFile{}
	if s.config.SoftwareDir == "" {
		return files, nil
	}
	entries, err := os.ReadDir(s.config.SoftwareDir)
	if err != nil {
		return nil, err
	}
	for _, entry := range entries {
		if entry.IsDir() || !match(entry.Name()) {
			continue
		}
		info, err := entry.Info()
		if err != nil {
			return nil, err
		}
		if !info.Mode().IsRegular() || info.Size() <= 0 || info.Size() > softwareMaxFile {
			return nil, fmt.Errorf("invalid software file: %s", entry.Name())
		}
		files = append(files, SoftwareFile{Path: entry.Name(), Size: info.Size()})
	}
	return files, nil
}

func (s *Server) sendSoftwareManifest(w http.ResponseWriter, target map[string]string, group *SoftwareGroup) {
	archives, err := s.softwareArchives()
	if err != nil {
		fail(w, 409, "Cannot read software archives")
		return
	}
	copies, err := s.softwareCopies()
	if err != nil {
		fail(w, 409, "Cannot read software copy files")
		return
	}
	var total int64
	count := len(archives) + len(copies)
	for _, f := range append(append([]SoftwareFile{}, archives...), copies...) {
		total += f.Size
	}
	if group != nil {
		group.RPMMinEL = s.config.SoftwareRPMMinEL
		count += len(group.Files)
		for _, f := range group.Files {
			total += f.Size
		}
		if len(group.Errors) > 0 {
			fail(w, 409, "Default software group is invalid or too large")
			return
		}
	}
	if count > 256 || total > softwareMaxGroup {
		fail(w, 409, "Software packages and copy files exceed 256 files or 8 GiB")
		return
	}
	lists := [][]SoftwareFile{archives, copies}
	if group != nil {
		lists = append(lists, group.Files)
	}
	for _, files := range lists {
		for i := range files {
			f, err := openSoftwareFile(s.config.SoftwareDir, files[i].Path)
			if err != nil {
				fail(w, 409, "Software changed while reading manifest")
				return
			}
			h := sha256.New()
			n, err := io.Copy(h, io.LimitReader(f, softwareMaxFile+1))
			f.Close()
			if err != nil || n != files[i].Size {
				fail(w, 409, "Software changed while reading manifest")
				return
			}
			files[i].SHA256 = hex.EncodeToString(h.Sum(nil))
		}
	}
	// Additive field: older clients continue receiving an unchanged package group.
	respond(w, 200, map[string]any{"schema": 1, "target": target, "group": group, "archives": archives, "copy_files": copies})
}

// Callers validate names against a package group or the flat distribution rules.
// The extension may be empty; safeOpen still confines access to the open root.
func openSoftwareFile(dir, name string) (*os.File, error) {
	info, err := os.Lstat(filepath.Join(dir, filepath.FromSlash(name)))
	if err != nil {
		return nil, err
	}
	if !info.Mode().IsRegular() {
		return nil, fmt.Errorf("not a regular software file")
	}
	return safeOpen(dir, name, filepath.Ext(name))
}

func (s *Server) softwareManifest(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	id, version, arch := q.Get("os"), q.Get("version"), q.Get("arch")
	if !softwareTarget(id, version, arch) {
		fail(w, 400, "Unsupported software target")
		return
	}
	groups, _, err := s.softwareGroups()
	if err != nil {
		fail(w, 500, "Cannot read software library")
		return
	}
	target := map[string]string{"os": id, "version": version, "arch": arch}
	candidates := []string{version}
	// EL/Debian VERSION_ID may include a minor release. Ubuntu groups always
	// match the exact release (22.04 must never borrow 22.10 packages).
	if id != "ubuntu" && strings.Contains(version, ".") {
		candidates = append(candidates, strings.Split(version, ".")[0])
	}
	for _, v := range candidates {
		for _, g := range groups {
			if g.OS != id || g.Version != v || g.Arch != arch {
				continue
			}
			if len(g.Errors) > 0 {
				fail(w, 409, "Default software group contains invalid files; review software library")
				return
			}
			s.sendSoftwareManifest(w, target, &g)
			return
		}
	}
	flat, err := s.flatSoftware()
	if err != nil {
		fail(w, 409, "Cannot read flat software library")
		return
	}
	g := SoftwareGroup{ID: "auto/" + id + "/" + version + "/" + arch + "/default", OS: id, Version: version, Arch: arch}
	for _, f := range flat {
		if s.softwareFlatMatch(f.Path, id, version, arch) {
			g.Files = append(g.Files, f)
		}
	}
	if len(g.Files) > 0 {
		s.sendSoftwareManifest(w, target, &g)
	} else {
		s.sendSoftwareManifest(w, target, nil)
	}
}

func (s *Server) softwarePackage(w http.ResponseWriter, r *http.Request) {
	name, expected := r.URL.Query().Get("path"), r.URL.Query().Get("sha256")
	parts := strings.Split(name, "/")
	flat := len(parts) == 1 && (softwareFileRE.MatchString(name) || softwareArchiveRE.MatchString(name) || softwareCopyName(name))
	nested := len(parts) == 5 && parts[3] == "default" && softwareTarget(parts[0], parts[1], parts[2]) && softwareFileRE.MatchString(parts[4]) && filepath.Ext(name) == "."+softwareFamily(parts[0])
	if (!flat && !nested) || !softwareHashRE.MatchString(expected) {
		fail(w, 400, "Invalid software package request")
		return
	}
	f, err := openSoftwareFile(s.config.SoftwareDir, name)
	if err != nil {
		fail(w, 404, "Software package not found")
		return
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil || info.Size() <= 0 || info.Size() > softwareMaxFile {
		fail(w, 409, "Invalid software package size")
		return
	}
	h := sha256.New()
	_, err = io.Copy(h, f)
	if err != nil || hex.EncodeToString(h.Sum(nil)) != expected {
		fail(w, 409, "Software package changed; rerun setup to obtain a fresh manifest")
		return
	}
	if _, err = f.Seek(0, io.SeekStart); err != nil {
		fail(w, 500, "Cannot read software package")
		return
	}
	w.Header().Set("Content-Type", "application/octet-stream")
	w.Header().Set("X-Content-SHA256", expected)
	http.ServeContent(w, r, filepath.Base(name), info.ModTime(), f)
}
