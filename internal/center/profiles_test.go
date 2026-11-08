package center

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"testing"
)

func profileRequest(p Profile, machine string) JobRequest {
	return JobRequest{Profile: p.ID, MachineID: machine, ISO: "test.iso", Username: "deployadmin", PasswordHash: "$6$example$" + strings.Repeat("a", 86), Password: "Example-Password-123!", WindowsImage: 1, Locale: "en-US"}
}

func TestProfileSelectionAndCompatibility(t *testing.T) {
	for _, old := range []struct{ os, id string }{{"rocky", "rocky-9"}, {"ubuntu", "ubuntu-24.04"}, {"windows", "windows-server-2022"}} {
		p, err := resolveProfile("", old.os)
		if err != nil || p.ID != old.id {
			t.Fatalf("legacy %s: %+v, %v", old.os, p, err)
		}
	}
	for _, bad := range [][2]string{{"ubuntu-25.10", "ubuntu"}, {"rocky-10", "ubuntu"}, {"", "debian"}} {
		if _, err := resolveProfile(bad[0], bad[1]); err == nil {
			t.Fatal("invalid profile accepted", bad)
		}
	}
	for _, test := range []struct{ path, id string }{
		{"AlmaLinux/AlmaLinux-8.10-x86_64-dvd.iso", "almalinux-8"},
		{"AlmaLinux/AlmaLinux-9.5-x86_64-dvd.iso", "almalinux-9"},
		{"RHEL/rhel-server-7.6-x86_64-dvd.iso", "rhel-7"},
		{"RHEL/rhel-server-7.9-x86_64-dvd.iso", "rhel-7"},
		{"RHEL/rhel-8.10-x86_64-dvd.iso", "rhel-8"},
		{"RHEL/rhel-9.4-x86_64-dvd.iso", "rhel-9"},
		{"Rocky/Rocky-10.2-x86_64-dvd1.iso", "rocky-10"},
		{"CentOS/CentOS-7.9-x86_64-Everything-2009.iso", "centos-7.9"},
		{"CentOS/CentOS-7-x86_64-DVD-2009.iso", "centos-7.9"},
		{"CentOS/CentOS-7-x86_64-Everything-2009.iso", "centos-7.9"},
		{"CentOS/CentOS-7-x86_64-DVD-1810.iso", "centos-7.6"},
		{"CentOS/CentOS-8-x86_64-1905-dvd1.iso", "centos-8.0"},
		{"CentOS/CentOS-8.4.2105-x86_64-dvd1.iso", "centos-8.4"},
		{"CentOS/CentOS-Stream-8-20240101.0-x86_64-dvd1.iso", "centos-stream-8"},
		{"CentOS/CentOS-7.90-x86_64-DVD.iso", ""},
		{"CentOS/CentOS-8.5.2111-x86_64-dvd1.iso", "centos-8.5"},
		{"CentOS/CentOS-Stream-9-latest-x86_64-dvd1.iso", "centos-stream-9"},
		{"CentOS/CentOS-Stream-10-latest-x86_64-dvd1.iso", "centos-stream-10"},
		{"CentOS/CentOS-Stream-100-x86_64-dvd1.iso", ""},
		{"CentOS/CentOS-8.50-x86_64-dvd1.iso", ""},
		{"Ubuntu/ubuntu-20.04.6-live-server-amd64.iso", "ubuntu-20.04"},
		{"Ubuntu/ubuntu-20.04.3-live-server-amd64.iso", "ubuntu-20.04"},
		{"Ubuntu/ubuntu-24.04-live-server-amd64.iso", "ubuntu-24.04"},
		{"Ubuntu/ubuntu-24.10-live-server-amd64.iso", "ubuntu-24.10"},
		{"Ubuntu/ubuntu-25.04-live-server-amd64.iso", "ubuntu-25.04"},
		{"Ubuntu/ubuntu-26.04-live-server-amd64.iso", "ubuntu-26.04"},
		{"Ubuntu/ubuntu-22.04.4-desktop-amd64.iso", "ubuntu-22.04-desktop"},
		{"Ubuntu/ubuntu-26.04-desktop-amd64.iso", "ubuntu-26.04-desktop"},
		{"Debian/debian-10.11.0-amd64-DVD-1.iso", "debian-10"},
		{"Debian/debian-11.4.0-amd64-DVD-1.iso", "debian-11"},
		{"Debian/debian-12.5.0-amd64-DVD-1.iso", "debian-12"},
		{"Debian/debian-13.4.0-amd64-DVD-1.iso", "debian-13"},
		{"Debian/debian-13.7.0-amd64-DVD-1.iso", "debian-13"},
		{"Debian/debian-13.7.0-amd64-netinst.iso", "debian-13"},
		{"Debian/debian-13.1.0-amd64-netinst.iso", "debian-13"},
		{"custom-linux.iso", ""}, {"rocky-100-x86_64.iso", ""},
	} {
		if got := suggestedProfile(test.path); got != test.id {
			t.Errorf("%s: got %s", test.path, got)
		}
	}
	for _, test := range [][2]string{{"rocky-9", "Rocky-8.10-x86_64-dvd1.iso"}, {"ubuntu-24.04", "ubuntu-24.04-desktop-amd64.iso"}, {"debian-13", "debian-live-13-amd64.iso"}, {"rocky-10", "Rocky-10.2-aarch64-dvd1.iso"}, {"centos-7.9", "CentOS-8.5.2111-x86_64-dvd1.iso"}, {"centos-stream-9", "CentOS-Stream-10-latest-x86_64-dvd1.iso"}, {"centos-8.5", "CentOS-8.5.2111-x86_64-boot.iso"}, {"centos-stream-10", "CentOS-Stream-10-latest-aarch64-dvd1.iso"}} {
		p, _ := findProfile(test[0])
		if validateMediaProfile(p, test[1]) == nil {
			t.Fatal("incompatible ISO accepted", test)
		}
	}
}

func TestDesktopAndArchivedMediaBoundaries(t *testing.T) {
	for _, test := range []struct {
		profile, iso string
		valid        bool
	}{
		{"ubuntu-22.04-desktop", "ubuntu-22.04.4-desktop-amd64.iso", true},
		{"ubuntu-26.04-desktop", "ubuntu-26.04-desktop-amd64.iso", true},
		{"ubuntu-22.04-desktop", "ubuntu-22.04.4-live-server-amd64.iso", false},
		{"ubuntu-22.04", "ubuntu-22.04.4-desktop-amd64.iso", false},
		{"ubuntu-26.04", "ubuntu-26.04-desktop-amd64.iso", false},
		{"debian-10", "debian-10.11.0-amd64-DVD-1.iso", true},
		{"debian-10", "debian-10.11.0-amd64-netinst.iso", false},
		{"debian-13", "debian-13.7.0-amd64-DVD-1.iso", true},
		{"debian-13", "debian-13.7.0-amd64-netinst.iso", true},
		{"debian-13", "debian-13.7.0-arm64-DVD-1.iso", false},
		{"debian-13", "debian-live-13.7.0-amd64-standard.iso", false},
	} {
		p, _ := findProfile(test.profile)
		if err := validateMediaProfile(p, test.iso); (err == nil) != test.valid {
			t.Errorf("%s / %s: %v", test.profile, test.iso, err)
		}
	}
}

func TestCentOS79MediaSelection(t *testing.T) {
	p, _ := findProfile("centos-7.9")
	for _, name := range []string{"CentOS-7-x86_64-DVD-2009.iso", "CentOS-7-x86_64-Everything-2009.iso", "CentOS-7.9-x86_64-DVD-2009.iso"} {
		if err := validateMediaProfile(p, name); err != nil {
			t.Errorf("full installation media %s rejected: %v", name, err)
		}
		other, _ := findProfile("rocky-9")
		if err := validateMediaProfile(other, name); err == nil {
			t.Errorf("CentOS media %s accepted for Rocky", name)
		}
	}
	for _, name := range []string{"CentOS-7-x86_64-NetInstall-2009.iso", "CentOS-7-x86_64-Minimal-2009.iso", "CentOS-7.9-live-x86_64.iso"} {
		if err := validateMediaProfile(p, name); err == nil {
			t.Errorf("incomplete media %s accepted for DVD-only template", name)
		}
	}
}

func TestLinuxAdministratorName(t *testing.T) {
	for _, p := range profiles {
		r := profileRequest(p, "fixture-machine")
		r.OS = p.OS
		if err := validateJob(r); err != nil {
			t.Fatalf("default administrator rejected for %s: %v", p.ID, err)
		}
		r.Username = "operator"
		err := validateJob(r)
		if p.OS == "windows" {
			if err != nil {
				t.Fatalf("Windows account unexpectedly rejected: %v", err)
			}
		} else if err == nil || !strings.Contains(err.Error(), "内置系统账户") {
			t.Fatalf("reserved Linux account accepted for %s: %v", p.ID, err)
		}
	}
}

func TestInstallationOnlyAndDebianCA(t *testing.T) {
	s := fixture(t)
	for _, p := range profiles {
		r := profileRequest(p, "missing")
		r.Enroll = true
		w := request(s, "POST", "/api/jobs", s.admin, r)
		mustCode(t, w, 400)
		if !strings.Contains(w.Body.String(), "当前阶段仅提供系统安装") {
			t.Fatal(w.Body.String())
		}
	}
	p, _ := findProfile("debian-12")
	w := request(s, "POST", "/api/jobs", s.admin, profileRequest(p, "missing"))
	mustCode(t, w, 400)
	if !strings.Contains(w.Body.String(), "bootstrap_ca_file") {
		t.Fatal("missing CA accepted")
	}
	s.ca = []byte("fixture CA")
	w = request(s, "POST", "/api/jobs", s.admin, profileRequest(p, "missing"))
	mustCode(t, w, 409)
	if len(s.store.snapshot().Jobs) != 0 {
		t.Fatal("rejected requests created tasks")
	}
}

func TestDebianDVDUsesOnlyInstallationMedia(t *testing.T) {
	s := fixture(t)
	s.ca = []byte("fixture CA")
	for _, id := range []string{"debian-11", "debian-12", "debian-13"} {
		p, _ := findProfile(id)
		for _, medium := range []string{"DVD-1", "netinst"} {
			iso := "Debian/" + id + ".0-amd64-" + medium + ".iso"
			want := medium == "DVD-1"
			d := renderData{Target: p, OfflineMedia: debianDVD(p, iso)}
			for _, name := range []string{"preseed.cfg", "pxe-preseed.cfg"} {
				cfg, err := render(name, d)
				if err != nil {
					t.Fatal(err)
				}
				if strings.Contains(cfg, "apt-setup/use_mirror boolean false") != want || strings.Contains(cfg, "apt-setup/services-select multiselect\n") != want {
					t.Fatalf("%s %s mirror policy mismatch", iso, name)
				}
			}
		}
	}
}

func TestDebian137SharedInstallationEntry(t *testing.T) {
	s := stagingFixture(t)
	s.config.PublicURL = "https://deploy.example:26080"
	s.config.LinuxAdminUsername = "user"
	s.config.LinuxInitialPasswordHash = "$6$example$" + strings.Repeat("a", 86)
	s.ca = []byte("fixture CA, not valid for deployment")
	s.config.LinuxSetupPreload = true
	var err error
	s.manualBundle, err = packManualSetup(map[string][]byte{
		"install.sh": []byte("#!/bin/sh\necho inert Debian 13.7 fixture\n"),
		"VERSION":    []byte(Version + "\n"),
	})
	if err != nil {
		t.Fatal(err)
	}
	const iso = "Debian/debian-13.7.0-amd64-DVD-1.iso"
	source := filepath.Join(s.config.ISODir, filepath.FromSlash(iso))
	if err := os.MkdirAll(filepath.Dir(source), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(source, []byte("Debian 13.7 fixture, not bootable"), 0600); err != nil {
		t.Fatal(err)
	}
	w := request(s, "POST", "/api/pxe/entries", s.admin, map[string]string{
		"label": "Debian 13.7 DVD", "profile": "debian-13", "iso": iso,
		"username": "user", "password_hash": "$6$example$" + strings.Repeat("a", 86),
	})
	mustCode(t, w, 201)
	var created PXEEntry
	if err := json.Unmarshal(w.Body.Bytes(), &created); err != nil {
		t.Fatal(err)
	}
	endpoint := "/api/pxe/entries/" + created.ID
	mustCode(t, request(s, "POST", endpoint+"/prepare", s.admin, nil), 200)
	mustCode(t, request(s, "POST", endpoint+"/enabled", s.admin, map[string]bool{"enabled": true}), 200)
	st := s.store.snapshot()
	e := *findPXEEntry(&st, created.ID)
	if e.Preparation.ISOPath != "iso/"+iso || e.Preparation.SetupSHA256 == "" {
		t.Fatal("Debian 13.7 must share its original ISO and record the current setup")
	}
	files, err := s.renderPXEFiles(e)
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"mirror/suite string trixie", "apt-setup/use_mirror boolean false", "apt-setup/services-select multiselect\n", "/dev/ventoy-center-not-authorized"} {
		if !strings.Contains(files["preseed.cfg"], want) {
			t.Fatal("Debian 13.7 automatic selection lost DVD/offline or disk authorization policy", want)
		}
	}
	archive, err := readInjection([]byte(files[debianInjectionName]))
	if err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{
		"usr/lib/finish-install.d/93ventoy-manual-preload",
		"usr/lib/post-base-installer.d/93ventoy-update-policy",
		"usr/lib/pre-pkgsel.d/93ventoy-installer-cache",
		"lib/debian-installer-startup.d/S99ventoy-diagnostics",
		"ventoy-manual-preload/target-update-policy.sh",
		"ventoy-manual-preload/copy-to-target.sh",
	} {
		if len(archive[name].Data) == 0 || archive[name].Mode&0111 == 0 {
			t.Fatal("manual and automatic Debian 13.7 need an executable installer hook", name)
		}
	}
	if string(archive["ventoy-manual-preload/ventoy-linux-setup.run"].Data) != string(manualSetupLauncher(s.manualBundle)) {
		t.Fatal("Debian 13.7 preload differs from the current downloadable setup")
	}
	// The shared injection also runs on the manual branch. Only choosing the
	// separate preseed answer may activate automatic installation or disk writes.
	for name := range archive {
		if strings.HasSuffix(name, "preseed.cfg") || strings.Contains(name, "cmdline.d/") {
			t.Fatal("shared Debian 13.7 injection must not force automatic installation", name)
		}
	}
	ticket := pxeTicket(t, s, e, pxeInventory())
	w = request(s, "POST", "/pxe/"+e.ID+"/install", e.Token, map[string]string{
		"ticket": ticket["ticket"], "disk_serial": "DISK-DEMO-001", "confirmation": "ERASE DISK-DEMO-001",
	})
	mustCode(t, w, 200)
	var payload map[string]string
	if err := json.Unmarshal(w.Body.Bytes(), &payload); err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"apt-setup/use_mirror boolean false", "pkgsel/upgrade select none", "copy-to-target.sh", "passwd/root-login boolean true"} {
		if !strings.Contains(payload["config"], want) {
			t.Fatal("authorized Debian 13.7 install lost required policy", want)
		}
	}
}

func TestEveryProfileProducesInstallationBundle(t *testing.T) {
	for _, p := range profiles {
		for _, firmware := range []string{"uefi", "bios"} {
			t.Run(p.ID+"/"+firmware, func(t *testing.T) {
				s := fixture(t)
				s.ca = []byte("fixture CA, not valid for deployment")
				w := request(s, "POST", "/api/machines", s.admin, Machine{Name: "LAB-001", MAC: "02:00:00:00:01:01", Serial: "ASSET-001", DiskSerial: "DISK-001", Firmware: firmware})
				mustCode(t, w, 201)
				var m Machine
				json.Unmarshal(w.Body.Bytes(), &m)
				w = request(s, "POST", "/api/jobs", s.admin, profileRequest(p, m.ID))
				if p.ID == "windows-11" && firmware == "bios" {
					mustCode(t, w, 409)
					return
				}
				mustCode(t, w, 201)
				var public Job
				json.Unmarshal(w.Body.Bytes(), &public)
				st := s.store.snapshot()
				j := arm(t, s, *findJob(&st, public.ID))
				if j.Profile != p.ID || j.OS != p.OS || j.Enroll {
					t.Fatalf("wrong profile snapshot: %+v", j.Job)
				}
				files, err := s.renderFiles(j)
				if err != nil {
					t.Fatal(err)
				}
				main := map[string]string{"kickstart": "kickstart.cfg", "autoinstall": "user-data", "preseed": "preseed.cfg", "ubiquity": "preseed.cfg", "unattend": "autounattend.xml"}[p.Installer]
				if files[main] == "" {
					t.Fatal("missing installation entry", main)
				}
				if p.OS != "windows" {
					policy := files[main]
					if p.OS == "debian" || p.Installer == "ubiquity" {
						policy, err = render("debian-late.sh", renderData{Target: p, PrivateJob: j})
						if err != nil {
							t.Fatal(err)
						}
					}
					if !strings.Contains(policy, "systemctl set-default multi-user.target") {
						t.Fatal("CLI installation must boot to the console target")
					}
				}
				if (files[centosInjectionName] != "") != (p.ID == "centos-7.9" || p.ID == "centos-7.6") {
					t.Fatal("CentOS 7 compatibility archive must be limited to that profile")
				}
				if (files[rockyInjectionName] != "") != (p.Installer == "kickstart" && p.ID != "centos-7.9" && p.ID != "centos-7.6") {
					t.Fatal("Kickstart compatibility archive must cover the remaining Anaconda profiles")
				}
				if (files[ubuntuInjectionName] != "") != (p.OS == "ubuntu") {
					t.Fatal("Ubuntu compatibility archive must be limited to 22.04")
				}
				if p.ID == "centos-7.9" && (!strings.Contains(files[main], "\n@^minimal\n@core\n") || strings.Contains(files[main], "@^minimal-environment")) {
					t.Fatal("package environment does not exist in the CentOS 7.9 DVD comps metadata")
				}
				for name, content := range files {
					if name != "SHA256SUMS" && !strings.Contains(files["SHA256SUMS"], fmt.Sprintf("%x  %s", sha256.Sum256([]byte(content)), name)) {
						t.Fatal("bad checksum", name)
					}
				}
				if p.OS != "windows" {
					d := renderData{PrivateJob: j, Target: p, Base: s.config.PublicURL + "/bootstrap/" + j.ID, CA: string(s.ca)}
					d.VersionCheck, err = render("version-check.sh", d)
					if err != nil {
						t.Fatal(err)
					}
					guard := "guard.sh"
					if p.OS == "debian" {
						guard = "debian-guard.sh"
					}
					for _, name := range []string{guard, "bootstrap.sh"} {
						content, e := render(name, d)
						if e != nil {
							t.Fatal(e)
						}
						if strings.Contains(content, "fyhocsys-node") || strings.Contains(content, "PRIVATE-FYH") {
							t.Fatal("OS-only bundle includes integration")
						}
						checkShell(t, name, content)
					}
					if p.OS == "debian" {
						if !strings.Contains(files[main], "mirror/suite string "+p.Suite) || strings.Contains(files[main], "\nd-i partman/confirm boolean true") {
							t.Fatal("unconditional erase or wrong suite")
						}
						// Check the actual embedded hooks, including their nested first-boot script.
						encoded := regexp.MustCompile(`printf '%s' '([A-Za-z0-9+/=]+)' \| base64 -d`).FindAllStringSubmatch(files[main], -1)
						if p.ID == "debian-10" || p.ID == "debian-11" {
							if strings.Count(files[main], "printf '%b'") != 2 {
								t.Fatal("missing legacy installer hooks")
							}
						} else if len(encoded) != 2 {
							t.Fatal("missing preseed hooks")
						}
						for _, match := range encoded {
							checkShell(t, "preseed-hook.sh", decodeTemplateScript(t, match[1]))
						}
					}
				}
				if output := os.Getenv("VENTOY_TEST_OUTPUT"); output != "" {
					for name, content := range files {
						path := filepath.Join(output, p.ID, firmware, filepath.FromSlash(name))
						if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
							t.Fatal(err)
						}
						if err := os.WriteFile(path, []byte(content), 0600); err != nil {
							t.Fatal(err)
						}
					}
				}
				mustCode(t, request(s, "POST", "/bootstrap/"+j.ID+"/event", j.Token, map[string]string{"state": "installing"}), 200)
				mustCode(t, request(s, "POST", "/bootstrap/"+j.ID+"/event", j.Token, map[string]string{"state": "installed"}), 200)
			})
		}
	}
}

func checkShell(t *testing.T, name, content string) {
	t.Helper()
	if runtime.GOOS == "windows" {
		return
	}
	cmd := exec.Command("bash", "-n")
	cmd.Stdin = strings.NewReader(content)
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("%s syntax: %v: %s", name, err, out)
	}
}
