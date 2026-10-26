#!/bin/bash
set -e

if [ "${1:-trixie}" != "trixie" ]; then
    echo "ERROR: Debian trixie is the only suite." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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

IMAGE="wlanpi-webui-builder:trixie"

rm -f .build-manifest.txt
rm -rf build .pybuild
rm -f wlanpi-webui*.deb

echo "========================================="
echo "Building wlanpi-webui Debian Package"
echo "  engine: $ENGINE"
echo "  suite:  trixie"
echo "========================================="

echo "Step 1: Building container image..."
"$ENGINE" build -f Dockerfile.build -t "$IMAGE" .

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
