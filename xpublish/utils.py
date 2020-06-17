"""Utility functions for internal use only.

The utility functions for printing version information have been adapted from
xarray/util/print_versions.py

"""

import locale
import os
import platform
import struct
import subprocess
import sys
import time


def get_sys_info():
    'Returns system information as a dict'

    blob = []

    # get full commit hash
    commit = None
    if os.path.isdir('.git') and os.path.isdir('xarray'):
        try:
            pipe = subprocess.Popen(
                'git log --format="%H" -n 1'.split(' '),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            so, serr = pipe.communicate()
        except Exception:
            pass
        else:
            if pipe.returncode == 0:
                commit = so
                try:
                    commit = so.decode('utf-8')
                except ValueError:
                    pass
                commit = commit.strip().strip('"')

    blob.append(('commit', commit))

    try:
        (sysname, nodename, release, version, machine, processor) = platform.uname()
        blob.extend(
            [
                ('python', sys.version),
                ('python-bits', struct.calcsize('P') * 8),
                ('OS', '%s' % (sysname)),
                ('OS-release', '%s' % (release)),
                # ("Version", "%s" % (version)),
                ('machine', '%s' % (machine)),
                ('processor', '%s' % (processor)),
                ('byteorder', '%s' % sys.byteorder),
                ('LC_ALL', '%s' % os.environ.get('LC_ALL', 'None')),
                ('LANG', '%s' % os.environ.get('LANG', 'None')),
                ('LOCALE', '%s.%s' % locale.getlocale()),
            ]
        )
    except Exception:
        pass

    return blob


def netcdf_and_hdf5_versions():
    libhdf5_version = None
    libnetcdf_version = None
    try:
        import netCDF4

        libhdf5_version = netCDF4.__hdf5libversion__
        libnetcdf_version = netCDF4.__netcdf4libversion__
    except ImportError:
        try:
            import h5py

            libhdf5_version = h5py.version.hdf5_version
        except ImportError:
            pass
    return [('libhdf5', libhdf5_version), ('libnetcdf', libnetcdf_version)]


class CostTimer:
    """ Context manager to measure wall time """

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        end = time.perf_counter()
        self.time = end - self._start
