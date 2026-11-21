package center

import (
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestSoftwareFYHOCTInstallKey(t *testing.T) {
	s := softwareFixture(t)
	url := "/software/v1/fyhoct-install"
	mustCode(t, request(s, "GET", url, "", nil), 401)
	mustCode(t, request(s, "GET", url, s.softwareToken(), nil), 200)
	s.config.FYHOCTInstallKeyFile = filepath.Join(t.TempDir(), "install-key")
	key := strings.Repeat("F", 32)
	for _, tc := range []struct {
		value string
		code  int
	}{{"short", 503}, {key + "\r\n", 200}} {
		if err := os.WriteFile(s.config.FYHOCTInstallKeyFile, []byte(tc.value), 0600); err != nil {
			t.Fatal(err)
		}
		w := request(s, "GET", url, s.softwareToken(), nil)
		mustCode(t, w, tc.code)
		if tc.code == 200 && (!strings.Contains(w.Body.String(), key) || w.Header().Get("Cache-Control") != "no-store") {
			t.Fatal("incorrect FYHOCT response")
		}
	}
	files := map[string][]byte{}
	s.addSoftwareClient(files)
	if strings.Contains(string(files["software-client.json"]), key) || !strings.Contains(string(files["software-client.json"]), `"fyhoct_install": true`) {
		t.Fatal("setup bundles should contain only the FYHOCT enable flag")
	}
}

func TestSoftwareUnlockCredentialIsolationAndRotation(t *testing.T) {
	s := softwareFixture(t)
	url := "/software/v1/fyhoc-unlock"
	for _, token := range []string{"", "wrong", s.admin} {
		mustCode(t, request(s, "GET", url, token, nil), 401)
	}
	w := request(s, "GET", url, s.softwareToken(), nil)
	mustCode(t, w, 200)
	if !strings.Contains(w.Body.String(), `"enabled":false`) {
		t.Fatal("must opt in")
	}
	secret := "test-only-fixture-key"
	s.config.FYHOCUnlockPasswordFile = filepath.Join(t.TempDir(), "key")
	for _, value := range []string{secret, "rotated-fixture-key"} {
		if err := os.WriteFile(s.config.FYHOCUnlockPasswordFile, []byte(value+"\n"), 0600); err != nil {
			t.Fatal(err)
		}
		w = request(s, "GET", url, s.softwareToken(), nil)
		mustCode(t, w, 200)
		if !strings.Contains(w.Body.String(), value) || w.Header().Get("Cache-Control") != "no-store" {
			t.Fatal("credential or cache policy")
		}
		for _, endpoint := range []string{"/api/overview", "/api/software", "/software/v1/manifest?os=ubuntu&version=26.04&arch=amd64"} {
			token := s.admin
			if strings.HasPrefix(endpoint, "/software/") {
				token = s.softwareToken()
			}
			r := request(s, "GET", endpoint, token, nil)
			mustCode(t, r, 200)
			if strings.Contains(r.Body.String(), value) {
				t.Fatal("credential disclosed outside credential endpoint")
			}
		}
	}
	for _, value := range []string{"", "two\nlines", "space key", strings.Repeat("x", 128)} {
		if err := os.WriteFile(s.config.FYHOCUnlockPasswordFile, []byte(value), 0600); err != nil {
			t.Fatal(err)
		}
		mustCode(t, request(s, "GET", url, s.softwareToken(), nil), 503)
	}
	if runtime.GOOS != "windows" {
		os.WriteFile(s.config.FYHOCUnlockPasswordFile, []byte(secret), 0600)
		os.Chmod(s.config.FYHOCUnlockPasswordFile, 0644)
		mustCode(t, request(s, "GET", url, s.softwareToken(), nil), 503)
		link := filepath.Join(t.TempDir(), "link")
		if err := os.Symlink(s.config.FYHOCUnlockPasswordFile, link); err != nil {
			t.Fatal(err)
		}
		s.config.FYHOCUnlockPasswordFile = link
		mustCode(t, request(s, "GET", url, s.softwareToken(), nil), 503)
	}
}
