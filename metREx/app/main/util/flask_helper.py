from flask import make_response


def format_response(data, content_type):
    response = make_response(data)

    response.headers['Content-Type'] = content_type
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response
