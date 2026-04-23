# app/auth/__init__.py

from flask import Blueprint

taiwan = Blueprint('taiwan', __name__)

from . import views
