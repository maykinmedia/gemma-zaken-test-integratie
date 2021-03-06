import os
import shutil
import subprocess
import tempfile
from urllib.parse import urljoin

import requests
import yaml

from .schema import get_operation_url

BASE_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    os.path.pardir,
    os.path.pardir,
))

CONFIG_FILE = os.path.join(BASE_DIR, 'config.yml')

CONFIG = {}


def load_config() -> dict:
    """
    Read the configuration of the services from the config file.

    .. todo:: allow overrides from environment variables
    """
    if CONFIG == {}:
        with open(CONFIG_FILE, 'r') as _config:
            CONFIG.update(yaml.safe_load(_config))

    return CONFIG


class Swagger2OpenApi:
    """
    Wrapper around node swagger2openapi
    """

    def __init__(self, swagger: bytes):
        self.swagger = swagger

    def convert(self) -> dict:
        tempdir = tempfile.mkdtemp()

        infile = os.path.join(tempdir, 'swagger2.0.yaml')
        outfile = os.path.join(tempdir, 'openapi.yaml')

        try:
            with open(infile, 'wb') as _infile:
                _infile.write(self.swagger)

            cmd = f'node_modules/.bin/swagger2openapi {infile} --outfile {outfile}'
            subprocess.call(cmd, shell=True, cwd=BASE_DIR)

            with open(outfile, 'rb') as _outfile:
                return yaml.safe_load(_outfile)

        finally:
            shutil.rmtree(tempdir)


class Client:

    _schema = None

    def __init__(self, service: str, base_path: str='/api/v1/'):
        self.service = service
        self.base_path = base_path

    @property
    def base_url(self) -> str:
        config = load_config()[self.service]
        return f"{config['scheme']}://{config['host']}:{config['port']}{self.base_path}"

    @property
    def schema(self):
        if self._schema is None:
            self.fetch_schema()
        return self._schema

    def request(self, path, method='GET', **kwargs):
        url = urljoin(self.base_url, path)
        headers = kwargs.pop('headers', {})
        headers.setdefault('Accept', 'application/json')
        headers.setdefault('Content-Type', 'application/json')
        kwargs['headers'] = headers
        return requests.request(method, url, **kwargs)

    def fetch_schema(self):
        url = urljoin(self.base_url, 'schema/openapi.yaml')
        response = requests.get(url)
        swagger2openapi = Swagger2OpenApi(response.content)
        self._schema = swagger2openapi.convert()

    def retrieve(self, resource: str, **path_kwargs):
        operation_id = f'{resource}_read'
        url = get_operation_url(self.schema, operation_id, **path_kwargs)
        response = self.request(url)
        assert response.status_code == 200, response.json()
        return response.json()

    def create(self, resource: str, data: dict, **path_kwargs):
        operation_id = f'{resource}_create'
        url = get_operation_url(self.schema, operation_id, **path_kwargs)
        response = self.request(url, method='POST', json=data)
        assert response.status_code == 201, response.json()
        return response.json()
