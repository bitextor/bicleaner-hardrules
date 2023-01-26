#!/bin/bash
set -e

# install wheeltools
pip install -U "wheel<0.38" wheeltools auditwheel patchelf build twine

# Empty dist dir and build dir
rm -rf dist/ _skbuild/

# Build source and binary distributions
python -m build

# Convert the platform-specific wheel to generic
python scripts/convert_to_generic_platform_wheel.py dist/bicleaner_hardrules-*.whl
# convert to manylinux platform
auditwheel repair -w dist dist/bicleaner_hardrules-*-py3-none-linux_x86_64.whl

# Remove unneeded wheels (not manylinux)
# THEY MUST BE DELETED OR TO AVOUD UPLOADING THEM
rm dist/*-linux_x86_64.whl

# Check files
twine check dist/*
# Upload only source and generic binary file
#CAUTION WITH THE NAMES!
twine upload dist/*.tar.gz dist/*manylinux1_x86_64.whl
