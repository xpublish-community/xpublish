import json
from pathlib import Path

from sphinx.util import logging
import xpublish

logger = logging.getLogger(__name__)


def generate_openapi_spec(sphinxapp):
    """Generate OpenAPI specification from xpublish.Rest."""
    spec_path = Path(sphinxapp.confdir) / 'api' / 'openapi.json'

    rest = xpublish.Rest({})
    app = rest.app
    openapi_spec = app.openapi()

    with spec_path.open('w') as f:
        json.dump(openapi_spec, f)

    logger.info(f'Generated OpenAPI spec at {spec_path}')


def setup(sphinxapp):
    """Register this extension with Sphinx.

    This extension generates the OpenAPI spec during the builder-inited event to ensure
    the openapi.json file exists before sphinxcontrib.openapi extension runs.
    """
    sphinxapp.connect('builder-inited', generate_openapi_spec)

    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
