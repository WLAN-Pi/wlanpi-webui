#!/bin/bash
#
# Build wlanpi-webui Debian package in a container (podman or docker)
#
# Usage: ./build-package-native.sh [SUITE]
#   SUITE defaults to trixie.
#
# The container engine is auto-detected (podman preferred, then docker).
# Override it explicitly with CONTAINER_ENGINE.
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Debian release to build for
SUITE="${1:-trixie}"

# Detect container engine (override with CONTAINER_ENGINE)
if [ -n "$CONTAINER_ENGINE" ]; then
    ENGINE="$CONTAINER_ENGINE"
elif command -v podman &> /dev/null; then
    ENGINE="podman"
elif command -v docker &> /dev/null; then
    ENGINE="docker"
else
    echo "ERROR: no container engine found!"
    echo "Please install podman or docker (or set CONTAINER_ENGINE)."
    exit 1
fi

if ! command -v "$ENGINE" &> /dev/null; then
    echo "ERROR: container engine '$ENGINE' not found!"
    exit 1
fi

IMAGE="wlanpi-webui-builder:${SUITE}"

# Clean up old build manifest, stale build trees, and previously built
# packages. Without this, setuptools reuses build/lib and repackages files that
# were deleted or renamed in the source tree, and stale .deb files in the repo
# root get picked up by the manifest and deployed.
rm -f .build-manifest.txt
rm -rf build .pybuild
rm -f wlanpi-webui*.deb

echo "========================================="
echo "Building wlanpi-webui Debian Package"
echo "  engine: $ENGINE"
echo "  suite:  $SUITE"
echo "========================================="

echo "Step 1: Building container image..."
"$ENGINE" build -f Dockerfile.build --build-arg SUITE="$SUITE" -t "$IMAGE" .

echo ""
echo "Step 2: Building Debian package in container..."
echo "(This may take several minutes...)"
echo ""

"$ENGINE" run --rm \
    -v "$(pwd)":/work:Z \
    -w /work \
    "$IMAGE" \
    bash -c '
set -e

echo "Installing package build dependencies..."
mk-build-deps --install --remove --tool "apt-get -y --no-install-recommends" debian/control || true

echo ""
echo "Building package..."
dpkg-buildpackage -us -uc -b

echo ""
echo "Copying packages from container to host..."
cp -v ../*.deb /work/ 2>/dev/null || echo "No .deb files found"

echo ""
echo "Creating build manifest..."
ls -1 ../*.deb 2>/dev/null | grep -v dbgsym | xargs -r -n1 basename > /work/.build-manifest.txt || true

echo ""
echo "Build complete!"
'

echo ""
echo "========================================="
echo "Package Build Complete!"
echo "========================================="
echo ""
echo "Generated packages:"
ls -lh wlanpi-webui*.deb 2>/dev/null || echo "No wlanpi-webui .deb files found"
echo ""
echo "To install the package:"
echo "  sudo dpkg -i wlanpi-webui*.deb"
echo "  sudo apt-get install -f  # if there are dependency issues"
echo ""
