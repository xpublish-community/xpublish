import argparse

import nox
import yaml

with open('./.github/workflows/main.yaml') as f:
    workflow = yaml.safe_load(f)

python_versions = workflow['jobs']['test']['strategy']['matrix']['python-version']
# pydantic_versions = workflow['jobs']['test']['strategy']['matrix']['pydantic-version']

nox.options.default_venv_backend = 'uv'


@nox.session(python=python_versions)
@nox.parametrize('pydantic', ['<2', '>=2'])
def tests(session: nox.Session, pydantic: str):
    """Run py.test."""
    session.install('-r', 'dev-requirements.txt')
    session.install('.')
    session.install(f"pydantic{pydantic}")
    session.run('pytest', '--verbose', '--pdb')


@nox.session
def pre_commit(session: nox.Session):
    """Run pre-commit."""
    session.install('pre-commit')
    session.run('pre-commit', 'run')


@nox.session
def docs(session: nox.Session):
    """Build docs using Sphinx.

    Add --live (nox -s docs -- --live) to run a live server
    Add --clean to clean docs directory first
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--clean', action='store_true', help='Clean the build directory first')
    parser.add_argument('--live', action='store_true', help='Run a live updating server for docs')
    args, posargs = parser.parse_known_args(session.posargs)

    session.install('-r', 'dev-requirements.txt')
    session.install('.')

    session.chdir('docs')
    session.install('-r', 'requirements.txt')
    session.install('sphinx-autobuild')

    BUILDDIR = '_build'

    if args.clean:
        session.run('rm', '-rf', f"{BUILDDIR}/*")

    if args.live:
        session.run('sphinx-autobuild', '-b', 'dirhtml', 'source/', '_build/dirhtml/')
    else:
        session.run(
            'sphinx-build',
            '-b',
            'dirhtml',
            '-d',
            f"{BUILDDIR}/doctrees",
            'source/dirhtml',
        )


nox.options.sessions = ['tests']
