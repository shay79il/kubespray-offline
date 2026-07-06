#!/bin/bash

# Exit on any error
set -e

. config.sh

KUBESPRAY_DIR=./cache/kubespray-${KUBESPRAY_VERSION}
PATCH_DIR=/target-scripts/patches/${KUBESPRAY_VERSION}

# Copy igz_patches to target-scripts/patches
if [[ -d "./igz_patches/${KUBESPRAY_VERSION}" ]]; then
  mkdir -p ${PATCH_DIR}
  find ./igz_patches/${KUBESPRAY_VERSION}/ -type f -exec cp {} $PATCH_DIR/ \;
else
  echo "[INFO]: No igz patches provided for the current release ${KUBESPRAY_VERSION}"
fi

# Run the flow
./precheck.sh
./prepare-pkgs.sh
./prepare-py.sh
./get-kubespray.sh

# Custom Ansible modules live in igz_files/library (not in the kubespray patch bundle)
if [[ -d ./library ]]; then
  mkdir -p "${KUBESPRAY_DIR}/library"
  cp ./library/*.py "${KUBESPRAY_DIR}/library/"
  KUBESPRAY_TARBALL="kubespray-${KUBESPRAY_VERSION}.tar.gz"
  if [[ -f "outputs/files/${KUBESPRAY_TARBALL}" ]]; then
    tar czf "outputs/files/${KUBESPRAY_TARBALL}" -C ./cache "kubespray-${KUBESPRAY_VERSION}"
  fi
fi

./pypi-mirror.sh
./download-kubespray-files.sh
./create-repo.sh
./copy-target-scripts.sh
#./download-additional-containers.sh

echo "===> Fetch requirements.txt"
cp $KUBESPRAY_DIR/requirements.txt .

echo "===> Fetch Iguazio scripts"
find . -path './proc' -prune -o -path './sys' -prune -o -type f -name "igz_*" -exec cp {} /outputs/ \;

if [[ -d ./library ]]; then
  cp -r ./library /outputs/
fi

chown -R 1000:1000 /outputs

echo "<=== Kubespray $KUBESPRAY_VERSION is ready for offline deployment ===>"
exit 0
