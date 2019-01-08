import re
import sys

pkg_file = open("lineup_remote/__init__.py").read()
metadata = dict(re.findall("__([a-z]+)__\s*=\s*'([^']+)'", pkg_file))
description = open('README.md').read()

from setuptools import setup, find_packages

install_requires = []

setup(
    name='lineup-remote',
    description='lineup',
    packages=find_packages(),
    author=metadata['author'],
    author_email=metadata['authoremail'],
    version=metadata['version'],
    url='https://github.com/lineupjs/lineup_remote',
    license="MIT",
    long_description=description,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],

    install_requires=[
        'setuptools',
        ] + install_requires
)
