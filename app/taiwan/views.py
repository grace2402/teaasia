# app/main/views.py

from flask import render_template, session, redirect, url_for, current_app, jsonify, request, flash, app
from datetime import datetime
from .. import db
# from forms import ProductForm
from app.taiwan import taiwan
from ..models import Story, Catalog
from flask_login import login_user, logout_user, login_required, current_user
#import paypalrestsdk

# Normally, if you refer to an undefined variable in a Jinja template,
# Jinja silently ignores this. This makes debugging difficult, so we'll
# set an attribute of the Jinja environment that says to make this an
# error.

# app.jinja_env.undefined = jinja2.StrictUndefined


@taiwan.route("/stories/<int:page>")
# @login_required
def list_stories(page=1):
    """Return page showing all the products has to offer"""
    per_page=4
    catalogs = Catalog.get_all()
    stories = Story.query.order_by(Story.post_datetime.desc()).filter_by(available = True).paginate(page,per_page,error_out=False)
    return render_template("taiwan/all_stories.html",
                           story_list=stories, catalogs=catalogs)


@taiwan.route("/show_story/<int:id>")
#@login_required
def show_story(id):
    """Return page showing the details of a given product.

    Show all info about a product. Also, provide a button to buy that product.
    """
    catalogs = Catalog.get_all()
    story = Story.get_by_id(id)
    return render_template("taiwan/story_details.html",
                           display_story=story, catalogs=catalogs)

@taiwan.route("/hit_story/<int:id>")
#@login_required
def hit_story(id):
    """Return page showing the details of a given product.

    Show all info about a product. Also, provide a button to buy that product.
    """
    catalogs = Catalog.get_all()
    story = Story.get_by_id(id)
    hitnumber = story.hitnumber + 1
    story.hitnumber = hitnumber
    db.session.commit
    return jsonify({'value' : str(hitnumber)})