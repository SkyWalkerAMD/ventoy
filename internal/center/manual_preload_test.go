package center

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"fmt"
	"io"
	"strings"
	"testing"
)

func TestManualPreloadPackage(t *testing.T) {
	payload := []byte("#!/bin/bash\necho not-executed-during-preload\n")
	b, err := manualPreloadInjection(payload)
	if err != nil {
		t.Fatal(err)
	}
	z, err := gzip.NewReader(bytes.NewReader(b))
	if err != nil {
		t.Fatal(err)
	}
	defer z.Close()
	tr := tar.NewReader(z)
	files := map[string][]byte{}
	for {
		h, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatal(err)
		}
		if h.Typeflag != tar.TypeReg || strings.HasPrefix(h.Name, "/") || strings.Contains(h.Name, "..") {
			t.Fatal("unsafe injection path", h.Name)
		}
		files[h.Name], err = io.ReadAll(tr)
		if err != nil {
			t.Fatal(err)
		}
	}
	for _, name := range []string{
		"live_injection_7ed136ec_7a61_4b54_adc3_ae494d5106ea/hook.sh",
		"usr/lib/dracut/hooks/pre-pivot/99-ventoy-manual-preload.sh",
		"usr/lib/finish-install.d/93ventoy-manual-preload",
		"usr/lib/post-base-installer.d/93ventoy-update-policy",
		"ventoy-manual-preload/linux-update-policy.sh",
		"ventoy-manual-preload/bmc-display-target.sh",
		"ventoy-manual-preload/ubuntu-kernel.py",
		"ventoy-manual-preload/finish-anaconda.ks",
		"ventoy-manual-preload/finish-subiquity",
		"ventoy-manual-preload/finish-ubiquity",
	} {
		if len(files[name]) == 0 {
			t.Fatal("missing installer hook", name)
		}
	}
	if !bytes.Equal(files["ventoy-manual-preload/ventoy-linux-setup.run"], payload) {
		t.Fatal("package bytes changed")
	}
	if string(files["ventoy-manual-preload/setup.sha256"]) != fmt.Sprintf("%x  ventoy-linux-setup.run\n", sha256.Sum256(payload)) {
		t.Fatal("payload checksum mismatch")
	}
	reboot, err := templates.ReadFile("templates/ubuntu-reboot.sh")
	if err != nil || !bytes.Equal(files["ventoy-manual-preload/ubuntu-reboot.sh"], bytes.ReplaceAll(reboot, []byte("\r\n"), []byte("\n"))) {
		t.Fatal("manual and automatic installers must share the live ISO shutdown helper", err)
	}
	// An injection must not add unattended answers or run the configuration.
	for name, b := range files {
		if strings.HasSuffix(name, "/README.txt") {
			continue
		}
		if strings.Contains(name, "cmdline.d") || strings.HasSuffix(name, "/preseed.cfg") || strings.HasSuffix(name, "/autoinstall.yaml") {
			t.Fatal("preload forces installation", name)
		}
		for _, line := range strings.Split(string(b), "\n") {
			if strings.HasPrefix(line, "exec ") && strings.Contains(line, "ventoy-linux-setup.run") {
				t.Fatal("configuration executed during preload")
			}
		}
	}
}
