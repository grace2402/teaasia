# manage.py

#!/usr/bin/env python
import os
from app import create_app, db
from app.models import User, Role, Catalog, Story
from flask_script import Manager, Shell, Server
from flask_migrate import Migrate, MigrateCommand
from flask_uploads import configure_uploads, patch_request_class
from app import images
from werkzeug.security import generate_password_hash
from sqlalchemy.orm.dynamic import CollectionHistory
#from flask_uploads import UploadSet, IMAGES
app = create_app(os.getenv('FLASK_CONFIG') or 'default')
#images = UploadSet('images', IMAGES)

configure_uploads(app, images)
patch_request_class(app)

manager = Manager(app)
migrate = Migrate(app, db)


# server = Server(host="0.0.0.0", port=5000 , debug = True, ssl_context=context)
def make_shell_context():
    return dict(app=app, db=db, User=User, Role=Role, Catalog=Catalog)


manager.add_command("shell", Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)
manager.add_command("http", Server(host="0.0.0.0", use_debugger=True, port=5000, use_reloader=True))
manager.add_command("http8", Server(host="0.0.0.0", use_debugger=True, port=8000, use_reloader=True))
manager.add_command("https", Server(host="0.0.0.0", port=8100, ssl_crt='openssl/server.crt', ssl_key='openssl/server.key'))
# manager.add_command("https", Server(host="0.0.0.0",use_debugger=True,port = 443, use_reloader=True, ssl_context='adhoc'))


@manager.command
def rebuild():
    db.drop_all()
    db.create_all()
    db.session.commit()
    db.session.add(Role(name='Admin'))
    db.session.add(Role(name='User'))
    db.session.add(Role(name='Provider'))
    db.session.add(Catalog(catalog_name="Tea package"))
    db.session.add(Catalog(catalog_name="Tea set"))
    db.session.add(Catalog(catalog_name="Tea food"))
    db.session.commit()

@manager.command
def story():
    story1 = Story(title = 'Elephone1', imgurl = 'elephone1.jpg',location = 'AAA', description = 'daassdfsdfkjfksljfklsjfljsdlfjsd', author = 'Tim',hitnumber = 0 , available = True)
    story2 = Story(title = 'Montain1', imgurl = 'images_11.jpg',location= 'BBB', description = 'dsfdfdaaskjfksljfklsjfljsdlfjsd', author = 'Grace' ,hitnumber = 0 , available = True)
    story3 = Story(title = 'Sea1', imgurl = 'images1.jpg',location = 'CCC', description = '13232daaskjfksljfklsjfljsdlfjsd', author = 'Tony',hitnumber = 3 , available = True)
    story4 = Story(title = 'Sea2', imgurl = 'images2.jpg',location = 'CCC', description = '13232daaskjfksljfklsjfljsdlfjsd', author = 'Tony',hitnumber = 2 , available = True)
    story5 = Story(title = 'Sea3', imgurl = 'images3.jpg',location = 'CCC', description = '13232daaskjfksljfklsjfljsdlfjsd', author = 'Tony',hitnumber = 1 , available = True)
    db.session.add(story1)
    db.session.add(story2)
    db.session.add(story3)
    db.session.add(story4)
    db.session.add(story5)
    db.session.commit()

@manager.command
def admin():
    user = User()
    user.username = 'Tim'
    user.role_id = 1
    user.email = 'yr6703@yahoo.com.tw'
    user.phone = '0921111111'
    user.add = 'sdfdsfsdfsdfsd'
    user.password_hash = generate_password_hash('1111', method="pbkdf2:sha1")
    user.is_admin = True
    user.confirmed = True
    db.session.add(user)
    db.session.commit()

@manager.command
def user():
    user = User()
    user.username = 'test'
    user.role_id = 2
    user.email = 'test@test.com'
    user.phone = '0921111111'
    user.add = 'sfsfsdfsafsdfsfasfsfa'
    user.password_hash = generate_password_hash('1111', method="pbkdf2:sha1")
    user.is_admin = False
    user.confirmed = True
    db.session.add(user)
    db.session.commit()   

@manager.command
def test():
    """Run the unit tests."""
    import unittest
    tests = unittest.TestLoader().discover('tests')
    unittest.TextTestRunner(verbosity=2).run(tests)


if __name__ == '__main__':
    manager.run()
