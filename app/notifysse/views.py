# app/main/views.py
from flask_sse import sse
from app.notifysse import notifysse
from flask import render_template
#import paypalrestsdk

# Normally, if you refer to an undefined variable in a Jinja template,
# Jinja silently ignores this. This makes debugging difficult, so we'll
# set an attribute of the Jinja environment that says to make this an
# error.

# app.jinja_env.undefined = jinja2.StrictUndefined


@notifysse.route("/hello")
# @login_required
def hello():
    sse.publish({"message": "Hello!"}, type='greeting')
    return "Message sent!"


@notifysse.route("/index")
# @login_required
def index():

    return render_template('notifysse/index.html')