#!/bin/bash
set -e

# install wheeltools
pip install wheeltools auditwheel patchelf

# Empty dist dir and build dir
rm -r dist/ _skbuild/

# Create source distribution separately to avoid including binary files
python setup.py sdist
# Create binary distribution
# pass the -- -- install arguments to tell ninja to install the bins in the wheel
python setup.py bdist_wheel -- --

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
