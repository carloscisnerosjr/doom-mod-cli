#!/usr/bin/env python

from setuptools import setup, find_packages
import glob

setup(
    name='doomcli',
    version='0.6.0',
    description='An interactive command-line toolkit and Python library for Doom WAD files',
    url='https://github.com/devinacker/omgifol',
    author='Devin Acker, Fredrik Johansson',
    author_email='d@revenant1.net',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Operating System :: OS Independent',
    ],
    python_requires=">=3.9",
    packages=find_packages(exclude=['demo']),
    extras_require={
        'graphics': ['Pillow', 'numpy'],
        'audio': ['soundfile', 'numpy'],
        'bgremove': ['rembg', 'Pillow'],
    },
    entry_points={
        'console_scripts': [
            'doomcli=doomcli.__main__:main',
            'png2wad=scripts.png2wad:main',
        ],
    },
    scripts=glob.glob("demo/*.py") + glob.glob("scripts/*.py"),
)
