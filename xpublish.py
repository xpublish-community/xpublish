import dask
import numpy as np
import xarray as xr

from flask import Flask, jsonify


@xr.register_dataset_accessor("publish")
class PublishAccessor:
    def __init__(self, xarray_obj):
        self._obj = xarray_obj
        self._app = None
        self._metadata = self.get_zmetadata()

    def get_zmetadata(self):
        metadata = {'zarr_consolidated_format': 1,
                    'metadata': {}}

        metadata['metadata']['.zattrs'] = self.get_zattrs()
        metadata['metadata']['.zgroup'] = self.get_zgroup()

        for key, da in self._obj.variables.items():
            metadata['metadata'][f'{key}/.zattrs'] = extract_zattrs(da)
            metadata['metadata'][f'{key}/.zarray'] = extract_zarray(da)
        return metadata

    def get_zgroup(self):
        return {'zarr_format': 2}
    
    def get_zattrs(self):
        return self._obj.attrs

    def rest_api(self):
        self._app = Flask('lazy_zarr')  # TODO: come up with better name
        
        @self._app.route('/.zgroup', methods=['GET'])
        def get_zgroup():
            return jsonify(self.get_zgroup())
        
        @self._app.route('/.zattrs', methods=['GET'])
        def get_zattrs():
            return jsonify(self.get_zattrs())
        
        @self._app.route('/.zmetadata', methods=['GET'])
        def get_zmetadata():
            return jsonify(self._metadata)

        @self._app.route('/keys', methods=['GET'])
        def list_keys():
            return jsonify(list(self._obj.variables))
        
        @self._app.route('/<var>/<chunk>', methods=['GET'])
        def get_key(var, chunk):
            da = self._obj[var]
            
            index = get_indexes(
                chunk,
                self._metadata['metadata'][f'{var}/.zarray']['chunks'][0]  # FIXME: 0 index is a hack
            )
            print(index)
            # TODO: pass through numcodecs compressors here?
            data_chunk = da.data[index]
            if isinstance(data_chunk, dask.array.Array):
                data_chunk = data_chunk.compute().tolist()
            else:
                data_chunk = data_chunk.tolist()
            return jsonify(data_chunk)

        # app.run(debug=True)
        from werkzeug.serving import run_simple
        run_simple('localhost', 9000, self._app)


def extract_zattrs(da):
    attrs = {}  # FIXME: da.attrs  # neet to sterilize dtypes, xarray must have a utility for this
    attrs['_ARRAY_DIMENSIONS'] = list(da.dims)
    return attrs


def extract_zarray(da):
    meta = {'compressor': None,  # is this okay?
             'dtype': da.dtype.str,
             'fill_value': np.nan,
             'filters': None,
             'order': 'C',
             'shape': list(da.shape),
             'zarr_format': 2
    }
    if da.chunks is not None:
        meta['chunks'] = [c[0] for c in da.chunks],  # assumes uniform chunks
    else:
        meta['chunks'] = list(da.shape)
    return meta


def slice_axis(key, chunk_size):
    return slice(key*chunk_size, (key + 1) * chunk_size)


def get_indexes(key, chunks):
    print(key, chunks)
    ikeys = key.split('.')
    if len(ikeys) > 1:
        return tuple(slice_axis(int(i), c) for i, c in zip(ikeys, chunks))
    else:
        # FIXME: this shouldn't be needed
        return (slice_axis(int(ikeys[0]), chunks), )
