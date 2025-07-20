#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

import os

from setuptools import setup, find_packages

PACKAGE = "aiodnsprox"
DESCRIPTION = "A Python-based DNS-over-X proxy based on aiocoap "
AUTHOR = "Martine S. Lenders"
AUTHOR_EMAIL = "m.lenders@fu-berlin.de"
URL = "https://github.com/anr-bmbf-pivot/aiodnsprox"


def get_requirements():
    with open("requirements.txt") as req_file:
        for line in req_file:
            yield line.strip()


def get_version(package):
    """Extract package version without importing file
    Importing cause issues with coverage,
        (modules can be removed from sys.modules to prevent this)
    Importing __init__.py triggers importing rest and then requests too

    Inspired from pep8 setup.py
    """
    with open(os.path.join(package, "__init__.py")) as init_fd:
        for line in init_fd:
            if line.startswith("__version__"):
                return eval(line.split("=")[-1])  # pylint:disable=eval-used
    return None


setup(
    name=PACKAGE,
    version=get_version(PACKAGE),
    description=DESCRIPTION,
    long_description=open("README.rst").read(),
    long_description_content_type="text/x-rst",
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    url=URL,
    license="MIT",
    download_url=URL,
    packages=find_packages(),
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Intended Audience :: End Users/Desktop",
        "Environment :: Console",
        "Topic :: Utilities",
    ],
    install_requires=list(get_requirements()),
    entry_points={
        "console_scripts": [
            "aiodns-proxy = aiodnsprox.cli.proxy:sync_main",
        ],
    },
    python_requires=">=3.7",
)
