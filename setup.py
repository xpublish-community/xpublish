#!/usr/bin/env python

"""The setup script."""

from os.path import exists

from setuptools import find_packages, setup

with open('requirements.txt') as f:
    install_requires = f.read().strip().split('\n')

if exists('README.rst'):
    with open('README.rst') as f:
        long_description = f.read()
else:
    long_description = ''

CLASSIFIERS = [
    'Development Status :: 4 - Beta',
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent',
    'Intended Audience :: Science/Research',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.9',
    'Programming Language :: Python :: 3.10',
    'Topic :: Scientific/Engineering',
]

setup(
    name='xpublish',
    description='Publish Xarray Datasets via a REST API.',
    long_description=long_description,
    python_requires='>=3.8',
    maintainer='Joe Hamman',
    maintainer_email='jhamman@ucar.edu',
    classifiers=CLASSIFIERS,
    url='https://github.com/xpublish-community/xpublish',
    packages=find_packages(exclude=('tests',)),
    package_dir={'xpublish': 'xpublish'},
    include_package_data=True,
    install_requires=install_requires,
    license='MIT',
    zip_safe=False,
    keywords=['xarray', 'zarr', 'api'],
    use_scm_version={'version_scheme': 'post-release', 'local_scheme': 'dirty-tag'},
    setup_requires=['setuptools_scm>=3.4', 'setuptools>=42'],
    entry_points={
        'xpublish.plugin': [
            'dataset_info = xpublish.plugins.included.dataset_info:DatasetInfoPlugin',
            'zarr = xpublish.plugins.included.zarr:ZarrPlugin',
            'module_version = xpublish.plugins.included.module_version:ModuleVersionPlugin',
            'plugin_info = xpublish.plugins.included.plugin_info:PluginInfoPlugin',
        ]
    },
)
