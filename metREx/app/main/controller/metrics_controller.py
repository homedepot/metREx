from flask import request
from flask_restx import Resource

from prometheus_client import CONTENT_TYPE_LATEST

from ...main import *

from ..service.metrics_service import Metrics

from ..util.dto import MetricsDto
from ..util.flask_helper import format_response

api = MetricsDto.api


def get_parser():
    parser = api.parser()
    parser.add_argument('job_id',
                        type=str,
                        help='The registered job name',
                        location='path')

    return parser


_parser = get_parser()


@api.route('')
class ApplicationMetrics(Resource):
    @api.doc('export_application_metrics')
    @metrics.do_not_track()
    def get(self):
        """Export application metrics"""
        if prometheus_multiproc_dir is None and request.environ.get('wsgi.multiprocess', False):
            api.abort(501, "Running in multiprocess mode but 'prometheus_multiproc_dir' env var not set.")

        result = Metrics.read_prometheus_metrics(app_registry_name)

        return format_response(result, CONTENT_TYPE_LATEST)


@api.route('/<job_id>')
@api.expect(_parser)
class JobMetrics(Resource):
    @api.doc('export_job_metrics')
    def get(self, job_id):
        """Export job metrics"""
        if prometheus_multiproc_dir is None and request.environ.get('wsgi.multiprocess', False):
            api.abort(501, "Running in multiprocess mode but 'prometheus_multiproc_dir' env var not set.")

        if job_id in get_jobs():
            result = Metrics.read_prometheus_metrics(job_id)

            return format_response(result, CONTENT_TYPE_LATEST)
        else:
            api.abort(404)
