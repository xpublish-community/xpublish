#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["nox", "pyyaml"]
# ///

import argparse

import nox
import yaml

nox.needs_version = '>= 2025.10.14'
nox.options.default_venv_backend = 'uv|virtualenv'

with open('./.github/workflows/main.yaml') as f:
    workflow = yaml.safe_load(f)

python_versions = workflow['jobs']['test']['strategy']['matrix']['python-version']

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


@nox.session
def pre_commit(session: nox.Session):
    """Run pre-commit."""
    session.install('pre-commit')
    session.run('pre-commit', 'run')


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


if __name__ == '__main__':
    nox.main()
