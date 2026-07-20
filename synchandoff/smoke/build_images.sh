#!/bin/bash
# Build the local xuehang/<prefix>:3.11-git images the harness uses.
#
# Upstream xuehang images ship /usr/bin/git as an EMPTY executable and a
# gutted dpkg database (SyncMind anti-cheat / stripping). Consequences in the
# raw images: editable installs fail (setuptools-scm/hatch-vcs need git),
# sphinx dies at import (subprocess git -> ENOEXEC), our git-diff bookkeeping
# silently no-ops (bash runs the empty file as a no-op script, exit 0), and
# apt can't reinstall anything (corrupt /var/lib/dpkg/info/format).
#
# The strip goes beyond git: ~587 files are truncated to zero bytes,
# including system SHARED LIBRARIES (libexpat, libsqlite3, libssl, ...) that
# python's own stdlib imports — which breaks `pip install -e` everywhere
# (setuptools -> plistlib -> expat) and test collection on scrapy/pylint/
# sympy/seaborn. Fix: transplant git + every zeroed *.so* from
# python:3.11-bookworm (same Debian base). Only zero-length files are
# overwritten; stripped network BINARIES (curl/gpg/ssh/hg/svn) stay dead,
# preserving the sandbox spirit. Usage: ./build_images.sh PREFIX...
set -e
docker pull --platform linux/amd64 -q python:3.11-bookworm
docker rm -f gitdonor 2>/dev/null || true
docker run -d --platform linux/amd64 --name gitdonor python:3.11-bookworm sleep infinity
docker exec gitdonor bash -c "tar -C / -cf /tmp/gitpack.tar usr/bin/git usr/lib/git-core usr/share/git-core"
docker cp gitdonor:/tmp/gitpack.tar /tmp/gitpack.tar

for prefix in "$@"; do
  docker pull --platform linux/amd64 -q "xuehang/$prefix:3.11"
  docker rm -f "fix_$prefix" 2>/dev/null || true
  docker run -d --platform linux/amd64 --name "fix_$prefix" "xuehang/$prefix:3.11" sleep infinity
  # 1. real git (skip if the image's git already works)
  if ! docker exec "fix_$prefix" git --version >/dev/null 2>&1; then
    docker cp /tmp/gitpack.tar "fix_$prefix:/tmp/gitpack.tar"
    docker exec -u root "fix_$prefix" bash -c "rm -f /usr/bin/git && tar -C / -xf /tmp/gitpack.tar && rm /tmp/gitpack.tar"
  fi
  docker exec "fix_$prefix" git --version
  # 2. restore zero-length shared libraries from the donor (only zeroed ones)
  docker exec "fix_$prefix" bash -c \
    "find /lib /lib64 /usr/lib -xdev -type f -size 0 2>/dev/null | grep -E '\.so(\.|\$)'" \
    > /tmp/solist.txt || true
  if [ -s /tmp/solist.txt ]; then
    docker exec gitdonor bash -c "tar -C / -cf /tmp/libpack.tar \$(sed 's|^/||' <<'EOF' | tr '\n' ' '
$(cat /tmp/solist.txt)
EOF
)"
    docker cp gitdonor:/tmp/libpack.tar /tmp/libpack.tar
    docker cp /tmp/libpack.tar "fix_$prefix:/tmp/libpack.tar"
    docker cp /tmp/solist.txt "fix_$prefix:/tmp/solist.txt"
    docker exec -u root "fix_$prefix" bash -c '
      while read -r f; do
        [ -f "$f" ] && [ ! -s "$f" ] && tar -C / -xf /tmp/libpack.tar "${f#/}"
      done < /tmp/solist.txt
      rm -f /tmp/libpack.tar /tmp/solist.txt; ldconfig 2>/dev/null || true'
    echo "  restored $(wc -l < /tmp/solist.txt) zeroed libs"
  fi
  # 3. requests only: the repo's mtls client cert (2-year validity, README)
  #    expired 2026-03-13, so test_different_connection_pool_for_mtls_settings
  #    fails in GOLD state. Re-sign the shipped CSR with the shipped CA key —
  #    the exact command from tests/certs/mtls/client/Makefile — on the host
  #    (the image's openssl binary is one of the stripped zero-byte files).
  if [[ "$prefix" == 4_requests_* ]]; then
    certdir=$(mktemp -d)
    for f in certs/expired/ca/ca.crt certs/expired/ca/ca-private.key certs/mtls/client/client.csr; do
      docker cp "fix_$prefix:/workspace/test_repo/tests/$f" "$certdir/$(basename $f)"
    done
    (cd "$certdir" && \
     openssl x509 -req -CA ca.crt -CAkey ca-private.key -in client.csr \
       -outform PEM -out client.pem -days 730 -CAcreateserial && \
     openssl x509 -in ca.crt -outform PEM >> client.pem)
    docker cp "$certdir/client.pem" "fix_$prefix:/workspace/test_repo/tests/certs/mtls/client/client.pem"
    rm -rf "$certdir"
    echo "  renewed mtls client cert"
  fi
  docker commit "fix_$prefix" "xuehang/$prefix:3.11-git"
  docker rm -f "fix_$prefix"
  echo "FIXED $prefix"
done
docker rm -f gitdonor
