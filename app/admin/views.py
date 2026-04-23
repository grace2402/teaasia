# app/main/views.py
from shutil import copyfile
from flask import render_template, session, redirect, url_for, current_app, jsonify, request, flash, app
import hashlib, os, datetime
from .. import db
from .forms import ProductForm, ChangeCatalogForm, ChangeUserForm, StoryForm
from app.admin import admin
from ..models import Product, Order, Order_detail, Catalog, User, Role, Story
from flask_login import login_user, logout_user, login_required, current_user
#import paypalrestsdk
from ..email import send_email
#from werkzeug import secure_filename
#from flask_uploads import UploadSet, IMAGES
from werkzeug.utils import secure_filename
from werkzeug.datastructures import  FileStorage
from sqlalchemy.orm import query
from config import P_IMAGEPATH,S_IMAGEPATH , UPLOADPATH
#images = UploadSet('images', IMAGES)
from app import images

def check_admin():
    """
    Prevent non-admins from accessing the page
    """
    if not current_user.is_admin:
        abort(403)

# Normally, if you refer to an undefined variable in a Jinja template,
# Jinja silently ignores this. This makes debugging difficult, so we'll
# set an attribute of the Jinja environment that says to make this an
# error.

# app.jinja_env.undefined = jinja2.StrictUndefined


@admin.route("/stories/<int:page>", methods=['GET', 'POST'])
@login_required
def stories(page=1):
    """Return page showing all the products has to offer"""
    check_admin()
    per_page = 5
    story_list = Story.query.order_by(Story.post_datetime.desc()).paginate(page,per_page,error_out=False)
    catalogs = Catalog.get_all()
    # pre setting value
    return render_template('admin/stories.html', stories=story_list, catalogs=catalogs)

@admin.route("/edit_story/<int:id>", methods=['GET', 'POST'])
@login_required
def edit_story(id):
    check_admin()
    add_story= True
    story = Story.query.get_or_404(id)
    form = StoryForm(obj=story)
    if form.validate_on_submit():
        filename = secure_filename(form.upload.data.filename)
        src = UPLOADPATH + filename
        form.upload.data.save(src)
        filemd5 = hashlib.md5()

        with open(UPLOADPATH + filename,'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                filemd5.update(chunk)
        if form.available.data :
            available = True
        else:    
            available = False
        dst = S_IMAGEPATH + filemd5.hexdigest()+'.'+filename.split('.')[1]        
        if  Story.query.filter_by(imgurl = filemd5.hexdigest()+'.'+filename.split('.')[1]).first() == None :

            copyfile(src, dst)
            os.remove(src)
            story.title=form.title.data
            story.author=form.author.data
            story.imgurl=filemd5.hexdigest()+'.'+filename.split('.')[1]
            story.location=form.location.data
            story.description=form.description.data
            story.available=available
            #db.session.add(story)
            db.session.commit()
            flash('Add story successfull.')
        else:
            os.remove(src)
            flash('Upload image file was in used.')
        # redirect to the departments page
        return redirect(url_for('admin.stories', page = 1))

    # form.common_name.data = product.common_name
    # form.price.data = product.price
    catalogs = Catalog.get_all()
    stories = Story.get_all()
    return render_template('admin/story.html', action="Edit",
                           add_story=add_story, form=form,
                           stories=stories, title="Edit Story", catalogs=catalogs)

@admin.route("/add_story", methods=['GET', 'POST'])
@login_required
def add_story():
    check_admin()
    add_story= True
    form = StoryForm()
    if form.validate_on_submit():
        filename = secure_filename(form.upload.data.filename)
        src = UPLOADPATH + filename
        form.upload.data.save(src)
        filemd5 = hashlib.md5()

        with open(UPLOADPATH + filename,'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                filemd5.update(chunk)
        if form.available.data :
            available = True
        else:    
            available = False
        dst = S_IMAGEPATH + filemd5.hexdigest()+'.'+filename.split('.')[1]
        if  Story.query.filter_by(imgurl = filemd5.hexdigest()+'.'+filename.split('.')[1]).first() == None :

            copyfile(src, dst)
            os.remove(src)
            story = Story(title=form.title.data,
            author=form.author.data,
            imgurl=filemd5.hexdigest()+'.'+filename.split('.')[1],
            location=form.location.data,
            description=form.description.data,
            hitnumber = 0,
            available=available)
            db.session.add(story)
            db.session.commit()
            flash('Add story successfull.')
        else:
            os.remove(src)
            flash('Upload image file was in used.')
        # redirect to the departments page
        return redirect(url_for('admin.stories', page = 1))

    # form.common_name.data = product.common_name
    # form.price.data = product.price
    catalogs = Catalog.get_all()
    stories = Story.get_all()
    return render_template('admin/story.html', action="Add",
                           add_story=add_story, form=form,
                           stories=stories, title="Add Story", catalogs=catalogs)

@admin.route("/delete_story/<int:id>", methods=['GET', 'POST'])
@login_required
def delete_story(id):
    check_admin()
    story = Story.query.get_or_404(id)
    os.remove(S_IMAGEPATH + story.imgurl)
    db.session.delete(story)
    db.session.commit()
    flash('Story was deleted successfull.')
    catalogs = Catalog.get_all()    
    stories = Story.get_all()
    return redirect(url_for('admin.stories', page = 1))
    #return render_template("taiwan/all_stories.html",stories=stories, catalogs=catalogs)




@admin.route("/users/<int:page>", methods=['GET', 'POST'])
@login_required
def users(page=1):
    """Return page showing all the products has to offer"""
    check_admin()
    per_page = 5
    users = User.query.filter_by().paginate(page,per_page,error_out=False)
    catalogs = Catalog.get_all()
    # pre setting value
    return render_template('admin/users.html', users=users, catalogs=catalogs)


@admin.route("/user/<int:id>", methods=['GET', 'POST'])
@login_required
def user(id):
    """Return page showing all the products has to offer"""
    check_admin()
    from_order = True
    page = 1
    per_page = 1
    users = User.query.filter_by(id=id).paginate(page,per_page,error_out=False)
    catalogs = Catalog.get_all()
    # pre setting value
    return render_template('admin/users.html', from_order=from_order, users=users, catalogs=catalogs)


@admin.route("/edit_user/<int:id>", methods=['GET', 'POST'])
@login_required
def edit_user(id):
    """Return page showing all the catalog"""
    check_admin()
    add_user = False
    user = User.query.get_or_404(id)
    form = ChangeUserForm(obj=user)
    if form.validate_on_submit():
        user.username = form.name.data
        role_name = form.role.data
        user.role_id = Role.query.filter_by(name=str(form.role.data)).first().id
        user.add = form.add.data
        user.confirmed = form.confirmed.data
        db.session.commit()
        # redirect to the departments page
        return redirect(url_for('admin.users',page = 1))
    # pre setting value
    form.name.data = user.username
    catalogs = Catalog.get_all()
    return render_template('admin/user.html', action="Edit", form=form,
                            add_user=add_user, catalogs=catalogs, title="Edit User")  


@admin.route("/shipout_order/<int:id>", methods=['GET', 'POST'])
@login_required
def shipout_order(id):
    """Update shipout -> True"""
    check_admin()
    order = Order.query.filter_by(id=id).first()
    if order.shipout == False :
        order.shipout = True
        order.ship_datetime = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        #db.session.add(order)
        db.session.commit()
        user = User.query.filter_by(id=order.user_id).first()
        #send_email(user.email, 'Confirm Your Shipping', 'admin/email/ship', user=user, order=order)
        flash('Order was ship out and send email to user.')
    page = 1
    per_page = 1
    orders = Order.query.filter_by(id=id).paginate(page,per_page,error_out=False)
    catalogs = Catalog.get_all()

    return render_template("admin/orders.html", catatlogs=catalogs, orders=orders)


@admin.route("/orders/<int:page>")
@login_required
def orders(page = 1):
    """Return page showing all the products has to offer"""
    check_admin()
    per_page = 5
    orders = Order.query.order_by(Order.order_datetime.desc()).paginate(page,per_page,error_out=False)
    catalogs = Catalog.get_all()
    return render_template("admin/orders.html", catalogs=catalogs, orders=orders)

# @admin.route("/edit_order/<int:id>",methods=['GET', 'POST'])
# @login_required
# def edit_order(id):
#     """Return page showing all the products has to offer"""
#     check_admin()
#    
#     #pre setting value
#     return render_template('admin/order.html', action="Edit",
#                            add_order0=add_order, form=form,
#                            order=order, title="Edit Order")


@admin.route("/catalogs")
@login_required
def catalogs():
    """Return page showing all the products has to offer"""
    check_admin()
    catalogs = Catalog.get_all()
    return render_template("admin/catalogs.html", catalogs=catalogs)    


@admin.route("/add_catalogs", methods=['GET', 'POST'])
@login_required
def add_catalog():
    """Return page showing all the products has to offer"""
    check_admin()
    add_catalog = True
    form = ChangeCatalogForm()
    if form.validate_on_submit():
        catalog = Catalog(catalog_name=form.name.data)
        db.session.add(catalog)
        db.session.commit()
        # redirect to the departments page
        return redirect(url_for('admin.catalogs'))
    # pre setting value
    catalogs = Catalog.get_all()
    return render_template('admin/catalog.html', action="Add", form=form,
                            add_catalog=add_catalog, catalogs=catalogs, title="Add Catalog")  


@admin.route("/edit_catalog/<int:id>", methods=['GET', 'POST'])
@login_required
def edit_catalog(id):
    """Return page showing all the catalog"""
    check_admin()
    add_catalog = False
    catalog = Catalog.query.get_or_404(id)
    form = ChangeCatalogForm(obj=catalog)
    if form.validate_on_submit():

        catalog.catalog_name = form.name.data
        db.session.commit()
        # redirect to the departments page
        return redirect(url_for('admin.catalogs'))
    # pre setting value
    form.name.data = catalog.catalog_name
    catalogs = Catalog.get_all()
    return render_template('admin/catalog.html', action="Edit", form=form,
                            add_catalog=add_catalog, catalogs=catalogs, title="Edit Catalog")  


@admin.route("/add_product", methods=['GET', 'POST'])
@login_required
def add_product():
    """Return page showing all the products has to offer"""
    check_admin()
    add_product = True
    form = ProductForm()
    if form.validate_on_submit():
        filename = secure_filename(form.upload.data.filename)
        src = UPLOADPATH + filename
        form.upload.data.save(src)
        filemd5 = hashlib.md5()

        with open(UPLOADPATH + filename,'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                filemd5.update(chunk)
        if form.available.data :
            in_stock = True
        else:    
            in_stock = False
        dst = P_IMAGEPATH + filemd5.hexdigest()+'.'+filename.split('.')[1]        
        if  Product.query.filter_by(imgurl = filemd5.hexdigest()+'.'+filename.split('.')[1]).first() == None :

            copyfile(src, dst)
            os.remove(src)
            product = Product(common_name=form.common_name.data,
            price=form.price.data,
            imgurl=filemd5.hexdigest()+'.'+filename.split('.')[1],
            color=form.color.data,
            size=form.size.data,
            available=in_stock,
            catalog_id=Catalog.query.filter_by(catalog_name=str(form.catalog_id.data)).first().id
            )
            db.session.add(product)
            db.session.commit()
            flash('Add product successfull.')
        else:
            os.remove(src)
            flash('Upload image file was in used.')
        # redirect to the departments page
        return redirect(url_for('admin.products', page = 1))

    # form.common_name.data = product.common_name
    # form.price.data = product.price
    catalogs = Catalog.get_all()
    products = Product.get_all()
    return render_template('admin/product.html', action="Add",
                           add_product=add_product, form=form,
                           products=products, title="Edit Product", catalogs=catalogs)


@admin.route("/delete_product/<int:id>", methods=['GET', 'POST'])
@login_required
def delete_product(id):
    """Return page showing all the products has to offer"""
    check_admin()
    product = Product.query.get_or_404(id)
    os.remove(P_IMAGEPATH + product.imgurl)
    db.session.delete(product)
    db.session.commit()
    per_page = 5
    page = 1
    flash('Product was deleted successfull.')
    catalogs = Catalog.get_all()    
    products = Product.query.order_by(Product.id.desc()).paginate(page,per_page,error_out=False)
    return render_template("admin/products.html",
                           products=products, catalogs=catalogs)
    

    
@admin.route("/edit_product/<int:id>", methods=['GET', 'POST'])
@login_required
def edit_product(id):
    """Return page showing all the products has to offer"""
    check_admin()
    add_product = False
    product = Product.query.get_or_404(id)
    form = ProductForm(obj=product)
    if form.validate_on_submit():
        filename = secure_filename(form.upload.data.filename)
        src = UPLOADPATH + filename
        form.upload.data.save(src)
        filemd5 = hashlib.md5()

        with open(UPLOADPATH + filename,'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                filemd5.update(chunk)
        if form.available.data :
            in_stock = True
        else:    
            in_stock = False
        dst = P_IMAGEPATH + filemd5.hexdigest()+'.'+filename.split('.')[1]        
        if  Product.query.filter_by(imgurl = filemd5.hexdigest()+'.'+filename.split('.')[1]).first() == None :

            product = Product.query.filter_by(id = id).first()
            product.common_name = form.common_name.data
            product.price=form.price.data
            orgfilename = P_IMAGEPATH+product.imgurl
            product.imgurl=filemd5.hexdigest()+'.'+filename.split('.')[1]
            product.color=form.color.data
            product.size=form.size.data
            product.available=in_stock
            product.catalog_id=Catalog.query.filter_by(catalog_name=str(form.catalog_id.data)).first().id
            db.session.commit()
            flash('Update product successfull.')
            copyfile(src, dst)
            os.remove(src)
            os.remove(orgfilename)
        else:
            os.remove(src)
            flash('Upload image file was in used.')
        #os.remove(os.getcwd() + '\\static\\product\\images\\'+orgfilename)
        # redirect to the departments page
        return redirect(url_for('admin.products', page = 1))
    # pre setting value
    form.catalog_id.data = product.product_type
    catalogs = Catalog.get_all()    
    return render_template('admin/product.html', action="Edit",
                           add_product=add_product, form=form,
                           product=product, catalogs=catalogs, title="Edit Product")


@admin.route("/products/<int:page>")
@login_required
def products(page):
    """Return page showing all the products has to offer"""
    check_admin()
    per_page = 5
    catalogs = Catalog.get_all()
    products = Product.query.order_by(Product.id.desc()).paginate(page,per_page,error_out=False)
    return render_template("admin/products.html",
                           products=products, catalogs=catalogs)
