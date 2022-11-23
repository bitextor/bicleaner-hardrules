#!/usr/bin/env python

from skbuild import setup
import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()
with open("requirements.txt") as rf:
    requirements = rf.read().splitlines()

setup(
    name="bicleaner-hardrules",
    version="2.5",
    license="GNU General Public License v3.0",
    author="Prompsit Language Engineering",
    author_email="info@prompsit.com",
    maintainer="Jaume Zaragoza",
    maintainer_email="jzaragoza@prompsit.com",
    description="Pre-filtering step for obvious noise based on rules, poor language based on general language modelling and vulgar language based on specific language modelling",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bitextor/bicleaner-hardrules",
    packages=setuptools.find_packages(),
    package_data={"hardrules": ["../requirements.txt"]},
    python_requires=">=3.7",
    install_requires=requirements,
    setup_requires=[
        "setuptools",
        "cmake",
        "scikit-build",
        "ninja",
    ],
    cmake_source_dir="./kenlm",
    cmake_args=[
        "-DKENLM_MAX_ORDER=7",
        "-DFORCE_STATIC=ON",
        "-DENABLE_INTERPOLATE=OFF",
    ],
    classifiers=[
        "Environment :: Console",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3.7",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: POSIX :: Linux",
        "Topic :: Text Processing :: Linguistic",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Text Processing :: Filters"
    ],
    project_urls={
        "Hardrules on GitHub": "https://github.com/bitextor/bicleaner-hardrules",
        "Prompsit Language Engineering": "http://www.prompsit.com",
        "Paracrawl": "https://paracrawl.eu/"
         },
    scripts=[
         "scripts/bicleaner-hardrules"
     ]
)
