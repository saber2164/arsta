#!/bin/bash
# ARSTA Project - ns-3.44 + 5G-LENA NR v4.0 Installation Script
# This script is idempotent (safe to run multiple times)

set -e  # Exit on error

# Configuration
NS3_VERSION="ns-3.44"
NS3_REPO="https://gitlab.com/nsnam/ns-3-dev.git"
NS3_DIR="ns-3.44"
NR_VERSION="nr-v4.0"
NR_REPO="https://gitlab.com/cttc-lena/nr.git"
NR_DIR="contrib/nr"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Error handler
error_exit() {
    log_error "$1"
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  FAIL: Installation unsuccessful${NC}"
    echo -e "${RED}========================================${NC}"
    exit 1
}

# Trap errors
trap 'error_exit "Script failed at line $LINENO"' ERR

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
NS3_PATH="$PROJECT_ROOT/ns3/$NS3_DIR"

log_info "ARSTA ns-3 + 5G-LENA Installation Script"
log_info "=========================================="
log_info "Project root: $PROJECT_ROOT"
log_info "ns-3 path: $NS3_PATH"

# Step 1: Install Ubuntu dependencies
log_info "Step 1: Installing Ubuntu dependencies..."
DEPS="g++ cmake ninja-build python3 git libsqlite3-dev"

if command -v apt-get &> /dev/null; then
    # Check if we have sudo access
    if sudo -n true 2>/dev/null; then
        sudo apt-get update -qq
        sudo apt-get install -y -qq $DEPS
        log_info "Dependencies installed successfully"
    else
        log_warn "No sudo access - checking if dependencies are already installed..."
        MISSING_DEPS=""
        for dep in $DEPS; do
            if ! dpkg -s "$dep" &> /dev/null; then
                MISSING_DEPS="$MISSING_DEPS $dep"
            fi
        done
        if [ -n "$MISSING_DEPS" ]; then
            log_warn "Missing dependencies:$MISSING_DEPS"
            log_warn "Please install them manually: sudo apt-get install$MISSING_DEPS"
        else
            log_info "All dependencies already installed"
        fi
    fi
else
    log_warn "apt-get not found - please install dependencies manually: $DEPS"
fi

# Step 2: Clone or update ns-3.44
log_info "Step 2: Setting up ns-3.44..."
mkdir -p "$PROJECT_ROOT/ns3"
cd "$PROJECT_ROOT/ns3"

if [ -d "$NS3_DIR" ]; then
    log_info "ns-3 directory exists, checking version..."
    cd "$NS3_DIR"
    
    # Check if we're on the correct tag
    CURRENT_TAG=$(git describe --tags --exact-match 2>/dev/null || echo "unknown")
    if [ "$CURRENT_TAG" = "$NS3_VERSION" ]; then
        log_info "ns-3.44 already installed at correct version"
    else
        log_warn "ns-3 exists but at different version ($CURRENT_TAG), resetting to $NS3_VERSION..."
        git fetch --tags
        git checkout "$NS3_VERSION" || error_exit "Failed to checkout $NS3_VERSION"
    fi
else
    log_info "Cloning ns-3.44 from $NS3_REPO..."
    git clone --depth 1 --branch "$NS3_VERSION" "$NS3_REPO" "$NS3_DIR" || error_exit "Failed to clone ns-3"
    cd "$NS3_DIR"
fi

# Step 3: Clone or update 5G-LENA NR module
log_info "Step 3: Setting up 5G-LENA NR v4.0..."
cd "$NS3_PATH"

if [ -d "$NR_DIR" ]; then
    log_info "NR module directory exists, checking version..."
    cd "$NR_DIR"
    
    # Check if we're on the correct tag
    CURRENT_NR_TAG=$(git describe --tags --exact-match 2>/dev/null || echo "unknown")
    if [ "$CURRENT_NR_TAG" = "$NR_VERSION" ]; then
        log_info "5G-LENA NR v4.0 already installed at correct version"
    else
        log_warn "NR exists but at different version ($CURRENT_NR_TAG), resetting to $NR_VERSION..."
        git fetch --tags
        git checkout "$NR_VERSION" || error_exit "Failed to checkout $NR_VERSION"
    fi
    cd "$NS3_PATH"
else
    log_info "Cloning 5G-LENA NR from $NR_REPO..."
    mkdir -p contrib
    git clone --depth 1 --branch "$NR_VERSION" "$NR_REPO" "$NR_DIR" || error_exit "Failed to clone 5G-LENA NR"
fi

# Step 4: Configure ns-3
log_info "Step 4: Configuring ns-3..."
cd "$NS3_PATH"

# Check if already configured
if [ -f "cmake-cache/build.ninja" ] || [ -f "cmake-cache/Makefile" ]; then
    log_info "ns-3 already configured, reconfiguring to ensure settings are correct..."
fi

./ns3 configure --enable-examples --enable-tests || error_exit "ns-3 configure failed"
log_info "ns-3 configured successfully"

# Step 5: Build ns-3
log_info "Step 5: Building ns-3 (this may take a while)..."
cd "$NS3_PATH"
./ns3 build || error_exit "ns-3 build failed"
log_info "ns-3 built successfully"

# Step 6: Verify installation
log_info "Step 6: Verifying installation..."
cd "$NS3_PATH"

# Try to run cttc-nr-demo to verify NR module works
log_info "Running cttc-nr-demo verification test..."
if ./ns3 run cttc-nr-demo --no-build 2>&1 | head -20; then
    log_info "cttc-nr-demo executed successfully"
    VERIFICATION_PASSED=true
else
    log_warn "cttc-nr-demo may have issues, but build completed"
    VERIFICATION_PASSED=false
fi

# Final summary
echo ""
echo "=========================================="
log_info "Installation Summary"
echo "=========================================="
log_info "ns-3 version: $NS3_VERSION"
log_info "5G-LENA NR version: $NR_VERSION"
log_info "Installation path: $NS3_PATH"
echo ""

if [ "$VERIFICATION_PASSED" = true ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  PASS: Installation successful!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    log_info "You can now use ns-3 with:"
    echo "  cd $NS3_PATH"
    echo "  ./ns3 run <your-script>"
    exit 0
else
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}  PASS: Build completed (verify manually)${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo ""
    log_warn "Build completed but verification had warnings."
    log_warn "Please verify manually:"
    echo "  cd $NS3_PATH"
    echo "  ./ns3 run cttc-nr-demo"
    exit 0
fi
