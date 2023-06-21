import json
from pathlib import Path

import xpublish

rest = xpublish.Rest({})
app = rest.app
openapi_spec = app.openapi()

script_path = Path(__file__)
spec_path = script_path.parent / 'openapi.json'

with spec_path.open('w') as f:
    json.dump(openapi_spec, f)
