# models.py

from flask import current_app
from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer as Serializer
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app import db
from . import login_manager
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import ARRAY
from wtforms.fields import DateTimeLocalField


class Car_type(db.Model):
    __tablename__ = 'car_type'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    car_name = db.Column(db.String(30))
    value = db.Column(db.Integer)


class Post(db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    constain = db.Column(db.String(500))
    author = db.Column(db.String(30))
    post_datetime = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
            'id': self.id,
            'author': self.author,
            'contain': self.constain,
            'post_datetime': self.post_datetime
        }

    @classmethod
    def get_last5(cls):
        return Post.query.order_by(Post.id.desc()).limit(5).all()

    @classmethod
    def get_all(cls):
        return Post.query.all()

    @classmethod
    def get_by_id(cls, id):
        return Post.query.get(id)

    def __repr__(self):
        return "<Post: %s>" % (self.constain)


class Order(db.Model):
    __tablename__ = 'order'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(10))
    total = db.Column(db.String(10))
    payment_id = db.Column(db.String(64))
    status = db.Column(db.Boolean, default=False)
    email = db.Column(db.String(30))
    order_datetime = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    orders = db.relationship('Order_detail', backref='order', lazy='dynamic')
    shipout = db.Column(db.Boolean, default=False)
    ship_datetime = db.Column(db.String(10))

    @classmethod
    def get_all(cls):
        return Order.query.all()

    def __repr__(self):
        return "<Order: %s, %s, %s>" % (self.id, self.user_id, self.order_datetime)


class Order_detail(db.Model):
    __tablename__ = 'order_detail'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(10))
    product_id = db.Column(db.String(10))
    product_name = db.Column(db.String(30))
    price = db.Column(db.String(10))
    quantity = db.Column(db.Integer)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))

    @classmethod
    def get_all(cls):
        return Order_detail.query.all()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Story(db.Model):
    __tablename__ = 'story'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(30), unique=True)
    imgurl = db.Column(db.String(30), unique=True)
    description = db.Column(db.String(500))
    location = db.Column(db.String(30))
    author = db.Column(db.String(30))
    hitnumber = db.Column(db.Integer)
    post_datetime = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    available = db.Column(db.Boolean, default=False)

    @classmethod
    def get_all(cls):
        return Story.query.all()

    @classmethod
    def get_top2(cls):
        return Story.query.order_by(Story.hitnumber.desc()).limit(2).all()

    @classmethod
    def get_by_id(cls, id):
        return Story.query.get(id)

    def __repr__(self):
        return "<Story: %s>" % (self.title)


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64), unique=True)
    users = db.relationship('User', backref='role', lazy='dynamic')

    def __repr__(self):
        return '{}'.format(self.name)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(64), unique=True, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    email = db.Column(db.String(64), unique=True, index=True)
    phone = db.Column(db.String(64))
    add = db.Column(db.String(64))
    password_hash = db.Column(db.String(128))
    confirmed = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)

    @classmethod
    def get_role(cls, role_id):
        return Role.query.filter_by(id=role_id).first()

    @classmethod
    def get_all(cls):
        return User.query.all()

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha1")

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_confirmation_token(self, expiration=3600):
        secret = str(current_app.config['SECRET_KEY'])
        s = Serializer(secret)
        return s.dumps({'confirm': self.id})

    def confirm(self, token, expiration=3600):
        secret = str(current_app.config['SECRET_KEY'])
        s = Serializer(secret)
        try:
            data = s.loads(token, max_age=expiration)
        except Exception:
            return False
        if data.get('confirm') != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        return True

    def generate_reset_token(self, expiration=3600):
        secret = str(current_app.config['SECRET_KEY'])
        s = Serializer(secret)
        return s.dumps({'reset': self.id})

    @staticmethod
    def reset_password(token, new_password, expiration=3600):
        secret = str(current_app.config['SECRET_KEY'])
        s = Serializer(secret)
        try:
            data = s.loads(token, max_age=expiration)
        except Exception:
            return False
        user = User.query.get(data.get('reset'))
        if user is None:
            return False
        user.password = new_password
        db.session.add(user)
        return True

    def generate_email_change_token(self, new_email, expiration=3600):
        secret = str(current_app.config['SECRET_KEY'])
        s = Serializer(secret)
        return s.dumps({'change_email': self.id, 'new_email': new_email})

    def change_email(self, token, expiration=3600):
        secret = str(current_app.config['SECRET_KEY'])
        s = Serializer(secret)
        try:
            data = s.loads(token, max_age=expiration)
        except Exception:
            return False
        if data.get('change_email') != self.id:
            return False
        new_email = data.get('new_email')
        if new_email is None:
            return False
        if User.query.filter_by(email=new_email).first() is not None:
            return False
        self.email = new_email
        db.session.add(self)
        return True

    def __repr__(self):
        return '<User %r>' % self.username


class Catalog(db.Model):
    __tablename__ = 'catalog'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    catalog_name = db.Column(db.String(30))
    products = db.relationship('Product', backref='catalog', lazy=True)

    @classmethod
    def get_by_id(cls, id):
        return Catalog.query.get(id)

    @classmethod
    def get_all(cls):
        return Catalog.query.all()

    def __repr__(self):
        return '{}'.format(self.catalog_name)


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    common_name = db.Column(db.String(30), unique=True)
    price = db.Column(db.String(10))
    imgurl = db.Column(db.String(30), unique=True)
    color = db.Column(db.String(30))
    size = db.Column(db.String(30))
    available = db.Column(db.Boolean, default=False)
    catalog_id = db.Column(db.Integer, db.ForeignKey('catalog.id'))

    def price_str(self):
        return "%s" % self.price

    def __repr__(self):
        return "<Product: %s, %s, %s>" % (self.id, self.common_name, self.price_str())

    @classmethod
    def get_all(cls):
        return Product.query.all()

    @classmethod
    def get_last3(cls):
        return Product.query.order_by(Product.id.desc()).limit(3).all()

    @classmethod
    def get_by_id(cls, id):
        return Product.query.get(id)


# -------------------------------
# 以下為需要記錄 user_id 的模型
# -------------------------------

class MaintenanceRecord(db.Model):
    __tablename__ = 'maintenance_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    datetime = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=False)
    jira_link = db.Column(db.String(256), nullable=True)
    performer = db.Column(db.String(64))
    # 新增：記錄建立該筆紀錄的使用者
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    history = db.relationship('RecordHistory', backref='record', lazy='dynamic')

    def __init__(self, datetime, location, description, jira_link, performer=None, user_id=None):
        self.datetime = datetime
        self.location = location
        self.description = description
        self.jira_link = jira_link
        self.performer = performer
        self.user_id = user_id


class RecordHistory(db.Model):
    __tablename__ = 'record_histories'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    maintenance_record_id = db.Column(db.Integer, db.ForeignKey('maintenance_records.id'))
    datetime = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=False)
    jira_link = db.Column(db.String(256))
    performer = db.Column(db.String(64))
    edited_at = db.Column(db.DateTime, default=func.now())


class TravelRecord(db.Model):
    __tablename__ = 'travel_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    datetime = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=False)
    jira_link = db.Column(db.String(256), nullable=True)
    performer = db.Column(db.String(64))
    operation_log = db.Column(db.Text, nullable=True)
    # 新增：記錄建立該筆紀錄的使用者
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def __init__(self, datetime, location, description, jira_link=None, performer=None, operation_log=None, user_id=None):
        self.datetime = datetime
        self.location = location
        self.description = description
        self.jira_link = jira_link
        self.performer = performer
        self.operation_log = operation_log
        self.user_id = user_id


# -------------------------------
# Material 與 Client 關聯
# -------------------------------
class Material(db.Model):
    __tablename__ = 'materials'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_model = db.Column(db.String(64))
    pid = db.Column(db.String(64))
    pn = db.Column(db.String(64))
    status = db.Column(db.String(64))
    keeper = db.Column(db.String(64))
    remark = db.Column(db.String(64))
    sim_info = db.Column(db.String(64))
    netsuite_dept = db.Column(db.String(64))
    eis_program = db.Column(db.String(64))
    eg_account = db.Column(db.String(64))
    location = db.Column(db.String(64))
    firmware = db.Column(db.String(64))
    connection_method = db.Column(db.String(64))
    note = db.Column(db.String(64))
    updated_by = db.Column(db.String(64))
    updated_date = db.Column(db.String(64))
    is_deleted = db.Column(db.Boolean, default=False)
    pickup_person = db.Column(db.String(64))
    pickup_order_number = db.Column(db.String(64))

    # 保留舊文字欄位 client (存 "ETC"、"中美粉" 等)
    client = db.Column(db.String(64))

    # 外鍵欄位，關聯到 clients.id
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    # 與 Client 的雙向關係：這裡命名為 client_obj，避免跟上面文字欄位 client 衝突
    client_obj = db.relationship('Client', back_populates='materials')


class Spot(db.Model):
    __tablename__ = 'spots'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    site_name = db.Column(db.String(128), nullable=True)       # 改為 nullable=True
    description = db.Column(db.String(256), nullable=True)       # 改為 nullable=True
    longitude = db.Column(db.Float, nullable=True)               # 改為 nullable=True
    latitude = db.Column(db.Float, nullable=True)                # 改為 nullable=True
    gw_list = db.Column(ARRAY(db.String), nullable=True)
    project_code = db.Column(db.String(128), nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    # 與 Client 的雙向關聯：對應 Client.spots
    client = db.relationship('Client', back_populates='spots', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'site_name': self.site_name,
            'description': self.description,
            'longitude': self.longitude,
            'latitude': self.latitude,
            'gw_list': self.gw_list or [],
            'project_code': self.project_code or '',
            'client': self.client.name if self.client else '',
            'client_id': self.client.id if self.client else None
        }


class RMARecord(db.Model):
    __tablename__ = 'rma_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pid_mac = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(64), nullable=False)
    note = db.Column(db.String(256))
    jira_link = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # 新增：記錄建立該筆紀錄的使用者
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)


class GWMonitor(db.Model):
    __tablename__ = 'gw_monitor'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    gw_id = db.Column(db.String(64), nullable=False, unique=True)
    pid = db.Column(db.String(64), nullable=False)
    frequency = db.Column(db.Integer, nullable=False, default=10)
    webhook_url = db.Column(db.String(256), nullable=True)


# -------------------------------
# Client 模型 (含與 Material, Spot 的關聯)
# -------------------------------
class Client(db.Model):
    __tablename__ = 'clients'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    website_url = db.Column(db.String(512), nullable=True)
    contact_name = db.Column(db.String(255), nullable=True)
    contact_email = db.Column(db.String(255), nullable=True)
    contact_phone = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

    # 與 Spot 的雙向關聯：用 back_populates 指定對應關聯
    spots = db.relationship('Spot', back_populates='client', lazy=True)

    # 與 Material 的雙向關聯：這裡命名為 materials，Material 裡對應的關聯名稱為 client_obj
    materials = db.relationship('Material', back_populates='client_obj', lazy=True)

    def __repr__(self):
        return f"<Client id={self.id}, name={self.name}>"
    

class Contract(db.Model):
    __tablename__ = 'contracts'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    warranty_start = db.Column(db.String(64), nullable=True)
    warranty_end = db.Column(db.String(64), nullable=True)
    warranty_amount = db.Column(db.String(64), nullable=True)  # 新增保固金額欄位
    maintenance_start = db.Column(db.String(64), nullable=True)
    maintenance_end = db.Column(db.String(64), nullable=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('spots.id'), nullable=False)
    site_name = db.Column(db.String(128), nullable=True)
    link = db.Column(db.String(256), nullable=True)  # 新增連結欄位

    spot = db.relationship('Spot', backref=db.backref('contracts', lazy=True))

    def __repr__(self):
        return f"<Contract id={self.id} spot_id={self.spot_id}>"



class MaterialJP(db.Model):
    __tablename__ = 'materials_jp'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_model = db.Column(db.String(64))
    pid = db.Column(db.String(64))
    pn = db.Column(db.String(64))
    status = db.Column(db.String(64))
    keeper = db.Column(db.String(64))
    remark = db.Column(db.String(64))
    sim_info = db.Column(db.String(64))
    netsuite_dept = db.Column(db.String(64))
    eis_program = db.Column(db.String(64))
    eg_account = db.Column(db.String(64))
    location = db.Column(db.String(64))
    firmware = db.Column(db.String(64))
    connection_method = db.Column(db.String(64))
    note = db.Column(db.String(64))
    updated_by = db.Column(db.String(64))
    updated_date = db.Column(db.String(64))
    is_deleted = db.Column(db.Boolean, default=False)
    pickup_person = db.Column(db.String(64))
    pickup_order_number = db.Column(db.String(64))

class SimCardStatus(db.Model):
    __tablename__ = 'sim_card_status'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pid = db.Column(db.String(64))
    iccid = db.Column(db.String(64))
    status = db.Column(db.String(30))
    group = db.Column(db.String(64))
    
    # 關聯到編輯紀錄
    edit_records = db.relationship('SimCardEditRecord', backref='sim_card_status', lazy='dynamic')

    def __repr__(self):
        return f"<SimCardStatus id={self.id} pid={self.pid} iccid={self.iccid}>"

class SimCardEditRecord(db.Model):
    __tablename__ = 'sim_card_edit_record'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # 此欄位作為外鍵連結到 SimCardStatus 的 id
    sim_card_status_id = db.Column(db.Integer, db.ForeignKey('sim_card_status.id'), nullable=False)
    original_pid = db.Column(db.String(64), nullable=False, default="")
    original_iccid = db.Column(db.String(64), nullable=False, default="")
    original_status = db.Column(db.String(30), nullable=False, default="")
    original_group = db.Column(db.String(64), nullable=False, default="")
    updated_by = db.Column(db.String(64))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SimCardEditRecord id={self.id} sim_card_status_id={self.sim_card_status_id}>"
    
class TaipowerExcelRecord(db.Model):
    __tablename__ = 'taipower_excel_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    TPC_number = db.Column(db.String(64), nullable=True)          # 電號
    username = db.Column(db.String(128), nullable=True)       # 戶名
    case_number = db.Column(db.String(64), nullable=True)     # 案件受理號碼
    guk_h = db.Column(db.String(64), nullable=True)           # GUK_H
    ak_h = db.Column(db.String(64), nullable=True)            # AK_H
    meter_brand = db.Column(db.String(64), nullable=True)     # 電表品牌
    meter_number = db.Column(db.String(64), nullable=True)    # 表號
    multiplier = db.Column(db.String(32), nullable=True)      # 倍數
    full_meter_number = db.Column(db.String(128), nullable=True)  # 完整表號
    request_date = db.Column(db.String(32), nullable=True)    # 申請日期
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<TaipowerExcelRecord id={self.id} TPC_number={self.TPC_number}>"
    
class TaipowermeterApply(db.Model):
    __tablename__ = 'taipowermeter_applies'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tpc_number = db.Column(db.String(64), nullable=False)           # 新增：台電編號 (tpcNo)
    hems_no = db.Column(db.String(64), nullable=False, unique=True)
    submitted_by = db.Column(db.String(32), nullable=False, default='ND')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<TaipowermeterApply hems_no={self.hems_no} submitted_by={self.submitted_by}>"
