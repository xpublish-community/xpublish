"""Utility functions for printing version information, adapted from xarray/util/print_versions.py."""

import locale
import os
import platform
import struct
import subprocess
import sys
from typing import (
    Any,
    List,
    Tuple,
    Union,
)


def get_sys_info() -> List[Tuple[str, Any]]:
    """Returns system information.

    Returns:
        A list of (key, value) tuples.
    """
    blob = []

    # get full commit hash
    if os.path.isdir('.git') and os.path.isdir('xpublish'):
        commit = None
        try:
            pipe = subprocess.Popen(
                'git log --format="%H" -n 1'.split(' '),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            so, _ = pipe.communicate()
        except Exception:  # pragma: no cover
            pass
        else:
            if pipe.returncode == 0:
                commit = so
                try:
                    commit = so.decode('utf-8')
                except ValueError:  # pragma: no cover
                    pass
                commit = commit.strip().strip('"')

        blob.append(('commit', commit))

    uname = platform.uname()
    blob.extend(
        [
            ('python', sys.version),
            ('python-bits', struct.calcsize('P') * 8),
            ('OS', '%s' % (uname.system)),
            ('OS-release', '%s' % (uname.release)),
            ('Version', '%s' % (uname.version)),
            ('machine', '%s' % (uname.machine)),
            ('processor', '%s' % (uname.processor)),
            ('byteorder', '%s' % sys.byteorder),
            ('LC_ALL', '%s' % os.environ.get('LC_ALL', 'None')),
            ('LANG', '%s' % os.environ.get('LANG', 'None')),
            ('LOCALE', '%s.%s' % locale.getlocale()),
        ]
    )

    return blob


def netcdf_and_hdf5_versions() -> list[tuple[str, Union[str, None]]]:
    """Returns netCDF and HDF5 version information.

    Returns:
        A list of (library, version) tuples.
    """
    libhdf5_version = None
    libnetcdf_version = None
    try:
        import netCDF4

        libhdf5_version = netCDF4.__hdf5libversion__
        libnetcdf_version = netCDF4.__netcdf4libversion__
    except ImportError:  # pragma: no cover
        try:
            import h5py

            libhdf5_version = h5py.version.hdf5_version
        except ImportError:
            pass
    return [('libhdf5', libhdf5_version), ('libnetcdf', libnetcdf_version)]
