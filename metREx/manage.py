import os

from flask import send_from_directory
from flask_script import Manager

from app.main import create_app, init_scheduler, run_scheduler


def register_blueprint():
    global app

    from app import blueprint

    app.register_blueprint(blueprint)


config_name = os.getenv('BOILERPLATE_ENV', 'dev')

app = create_app(config_name)

register_blueprint()

app.app_context().push()

manager = Manager(app)

host = os.getenv('CF_INSTANCE_INTERNAL_IP', os.getenv('IP_ADDRESS', '127.0.0.1'))
port = int(os.getenv('PORT', 5000))


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico',
                               mimetype='image/vnd.microsoft.icon')


@manager.command
def run():
    if not (app.debug and os.getenv('WERKZEUG_RUN_MAIN') is None):
        init_scheduler(config_name)

        run_scheduler()

    app.run(host=host, port=port)


if __name__ == '__main__':
    manager.run()
