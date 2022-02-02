import os

from flask import send_from_directory
from flask_script import Manager

if __package__ is None:
    import sys

    __package__ = os.path.basename(sys.path[0])

    sys.path.append(os.path.dirname(sys.path[0]))

from .app.main import *


config_name = os.getenv('BOILERPLATE_ENV', 'dev')

app = create_app(config_name)

manager = Manager(app)

host = os.getenv('CF_INSTANCE_INTERNAL_IP', os.getenv('IP_ADDRESS', '127.0.0.1'))
port = int(os.getenv('PORT', 5000))


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )


@manager.command
def run():
    if not (app.debug and os.getenv('WERKZEUG_RUN_MAIN') is None):
        start_scheduler(config_name)

    app.run(host=host, port=port)


if __name__ == '__main__':
    manager.run()
