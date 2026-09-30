#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["nox", "pyyaml"]
# ///

import argparse
import dataclasses
import os

import nox
import yaml

nox.needs_version = '>= 2025.10.14'
nox.options.default_venv_backend = 'uv|virtualenv'

with open('./.github/workflows/main.yaml') as f:
    workflow = yaml.safe_load(f)

python_versions = workflow['jobs']['test']['strategy']['matrix']['python-version']

# Oldest supported interpreter, compared numerically so e.g. '3.9' sorts before
# '3.14' (a plain string min() would compare lexicographically and get it wrong).
min_python_version = min(python_versions, key=lambda v: tuple(int(p) for p in v.split('.')))

with open('.readthedocs.yml') as f:
    rtd_config = yaml.safe_load(f)
docs_python_version = rtd_config['build']['tools']['python']


@nox.session(python=python_versions, default=True)
def tests(session: nox.Session):
    """Run py.test."""
    session.install('--group', 'dev')
    session.install('.')
    session.run(
        'pytest',
        '--verbose',
        # '--pdb'
    )


@nox.session(python=min_python_version, name='min-deps', default=True)
def min_deps(session: nox.Session):
    """Run py.test against the minimum supported Python and dependency versions.

    The test tooling (the ``dev`` group) is installed at its usual latest
    versions; uv's ``lowest-direct`` resolution is applied only to the package
    itself, pinning each runtime dependency to the floor of its version
    specifier. This catches lower bounds that have drifted out of date, e.g.
    using an API added after the minimum pinned version.
    """
    session.install('--group', 'dev')
    session.install('--resolution', 'lowest-direct', '.')
    session.run('pytest', '--verbose')


@nox.session(default=False)
def pre_commit(session: nox.Session):
    """Run pre-commit."""
    session.install('prek')
    session.run('prek', 'run')


@nox.session(python=docs_python_version, default=False)
def docs(session: nox.Session):
    """Build docs using Sphinx.

    Add --live (nox -s docs -- --live) to run a live server
    Add --clean to clean docs directory first
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--clean', action='store_true', help='Clean the build directory first')
    parser.add_argument('--live', action='store_true', help='Run a live updating server for docs')
    args, posargs = parser.parse_known_args(session.posargs)

    session.install('--group', 'dev')
    session.install('.')

    session.install('--group', 'docs')
    session.install('sphinx-autobuild')

    session.cd('docs')

    BUILDDIR = '_build'

    if args.clean:
        session.run('rm', '-rf', f'{BUILDDIR}/*')

    session.run('python', 'source/_ext/generate_openapi.py')

    if args.live:
        session.run('sphinx-autobuild', '-b', 'dirhtml', 'source/', '_build/dirhtml/')
    else:
        session.run(
            'sphinx-build',
            '-b',
            'dirhtml',
            '-d',
            f'{BUILDDIR}/doctrees',
            'source/dirhtml',
        )


@dataclasses.dataclass(frozen=True)
class Downstream:
    """Where a downstream plugin lives and how to install it for testing."""

    repo: str  # GitHub 'owner/name'
    ref: str = 'main'
    groups: tuple[str, ...] = ()  # PEP 735 groups, from the plugin's pyproject.toml
    requirements: tuple[str, ...] = ()  # requirement files, relative to the plugin's root
    extras: str = ''  # e.g. '[all]', appended to the plugin's own install
    deps: tuple[str, ...] = ()  # extra packages needed beyond groups/requirements
    pytest_args: tuple[str, ...] = ()


DOWNSTREAM_PLUGINS = {
    'zarr': Downstream('xpublish-community/xpublish-zarr', groups=('dev',)),
    'ogc-core': Downstream(
        'xpublish-community/xpublish-ogc-core',
        groups=('dev',),
        pytest_args=('-m', 'not cite'),
    ),
    'edr': Downstream(
        'xpublish-community/xpublish-edr',
        groups=('dev',),
        pytest_args=('-m', 'not cite', '-n', 'auto'),
    ),
    'tiles': Downstream(
        'earth-mover/xpublish-tiles',
        groups=('dev',),
        pytest_args=('tests', '-n', 'auto'),
    ),
    'wms': Downstream(
        # Its base deps come from requirements.txt via setuptools dynamic
        # metadata, so installing the package already covers those.
        'xpublish-community/xpublish-wms',
        requirements=('requirements-dev.txt',),
        pytest_args=('tests',),
    ),
    # 'opendap': Downstream(
    #     'xpublish-community/xpublish-opendap',
    #     requirements=('requirements-dev.txt',),
    #     # pytest-flake8 is lint tooling, and breaks collection on modern pytest.
    #     pytest_args=('-p', 'no:flake8'),
    # ),
    'intake-provider': Downstream(
        'xpublish-community/xpublish-intake-provider',
        requirements=('requirements-dev.txt',),
    ),
    # axiom-data-science/xpublish-intake is deliberately left out: its tests
    # do `from xpublish.plugins.included.zarr import ZarrPlugin`, a module
    # removed in xpublish #333. Installing xpublish-zarr doesn't fix this --
    # it only exposes `xpublish_zarr.plugin:ZarrPlugin`, not the old import
    # path -- so this is a genuine, pre-existing break in the plugin itself,
    # not something to install around.
    #
    # Also excluded: xpublish-host (stale, capped at Python <3.12, a host
    # rather than a plugin) and the local scaffold repos (catalog, stac,
    # ckan).
}


@nox.session(python='3.13', default=False, tags=['downstream'])
@nox.parametrize(
    'plugin_name', [nox.param(plugin_name, id=plugin_name) for plugin_name in DOWNSTREAM_PLUGINS]
)
def downstream(session: nox.Session, plugin_name: str):
    """Run a downstream plugin's test suite against this xpublish checkout.

    Add --src PATH to test against an existing local checkout instead of
    cloning, e.g. ``nox -s "downstream(edr)" -- --src ../xpublish-edr``.
    Anything else after ``--`` is passed on to pytest.
    """
    plugin_config = DOWNSTREAM_PLUGINS[plugin_name]

    parser = argparse.ArgumentParser()
    parser.add_argument('--src', help='Use an existing local checkout instead of cloning')
    args, extra = parser.parse_known_args(session.posargs)

    if args.src:
        src = os.path.normpath(os.path.join(session.invoked_from, args.src))
    else:
        src = str(session.cache_dir / 'downstream' / plugin_name)
        url = f'https://github.com/{plugin_config.repo}'
        if os.path.isdir(os.path.join(src, '.git')):
            session.run(
                'git',
                '-C',
                src,
                'fetch',
                '--depth',
                '1',
                'origin',
                plugin_config.ref,
                external=True,
            )
            session.run('git', '-C', src, 'reset', '--hard', 'FETCH_HEAD', external=True)
        else:
            session.run(
                'git',
                'clone',
                '--depth',
                '1',
                '--branch',
                plugin_config.ref,
                url,
                src,
                external=True,
            )

    # One resolution, so the local xpublish checkout wins over PyPI's xpublish.
    install_args = []
    for group in plugin_config.groups:
        install_args += ['--group', f'{src}/pyproject.toml:{group}']
    for req in plugin_config.requirements:
        install_args += ['-r', f'{src}/{req}']
    install_args.append(f'{src}{plugin_config.extras}')
    install_args.extend(plugin_config.deps)
    install_args.append(session.invoked_from)
    session.install(*install_args)

    # Run from the plugin's own directory, keeps `xpublish/` from shadowing
    # the installed package when run from the workspace root.
    session.chdir(src)
    # Pin the config file explicitly. The clone lives under this repo's own
    # .nox/.cache, so without -c, a plugin with no pytest config of its own
    # (e.g. it keeps test settings in setup.cfg instead) has pytest walk
    # upward past its directory and pick up *this* repo's pyproject.toml,
    # inheriting xpublish's own strict `filterwarnings = ["error", ...]`.
    session.run('pytest', '-c', 'pyproject.toml', *plugin_config.pytest_args, *extra)


if __name__ == '__main__':
    nox.main()
