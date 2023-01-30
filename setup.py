#!/usr/bin/env python
from skbuild import setup

#TODO remove setup.py when scikit-build supports these parameters in pyproject
setup(
    cmake_source_dir="./kenlm",
    cmake_args=[
        "-DKENLM_MAX_ORDER=7",
        "-DFORCE_STATIC=ON",
        "-DENABLE_INTERPOLATE=OFF",
    ]
)
