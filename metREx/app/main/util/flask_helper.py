from flask import make_response


def format_response(data, content_type):
    response = make_response(data)
    response.headers['content-type'] = content_type

    return response
