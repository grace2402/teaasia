# app/main/__init__.py  (Blueprint creation)

from flask import Blueprint

notifysse = Blueprint('notifysse', __name__)

# can use from main import views
from . import views
