import re

from cfenv import AppEnv

from flask import Blueprint, url_for
from flask_restx import Api

from .main.controller.metrics_controller import api as metrics_ns
from .main.controller.scheduler_controller import api as scheduler_ns

__title__ = 'metREx'
__version__ = '0.7.0'
__description__ = 'SQL query and monitoring system metrics exporter for Prometheus'

blueprint = Blueprint('api', __name__)
blueprint.config = {}


@blueprint.record
def record_config(setup_state):
    app = setup_state.app
    blueprint.config = dict([(key, value) for (key, value) in app.config.items()])


class MyApi(Api):
    '''
    Extension of the main entry point for the application.
    Need to modify Swagger API behavior to support running in HTTPS when deployed to PCF
    '''
    @property
    def specs_url(self):
        '''
        The Swagger specifications absolute url (ie. `swagger.json`)

        :rtype: str
        '''
        return url_for(self.endpoint('specs'), _external=False)


env = AppEnv()

kwargs_api = {
    'title': __title__,
    'version': __version__,
    'description': __description__
}

if env.name is not None:
    pattern = re.compile(
        r"""
            (?P<title>.*)(?=-v[0-9.+]+$)
            (?:
                -v(?P<version>[0-9.+]+)$
            )
        """,
        re.X
    )

    m = pattern.match(env.name)

    if m is not None:
        components = m.groupdict()

        kwargs_api.update(components)
    else:
        kwargs_api['title'] = env.name

api = MyApi(blueprint, **kwargs_api)

api.add_namespace(metrics_ns, path='/metrics')
api.add_namespace(scheduler_ns, path='/scheduler')


@api.errorhandler
def default_error_handler(error):
    '''
    Default error handler
    '''
    message = str(error)

    if 'ERROR_INCLUDE_MESSAGE' in api.app.config.keys():
        if not api.app.config['ERROR_INCLUDE_MESSAGE']:
            message = 'Internal Server Error'

    return {'message': message}, 500
