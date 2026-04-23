# app/main/errors.py (Blueprint with error handlers)

from flask import render_template
from . import product


@product.app_errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@product.app_errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500
