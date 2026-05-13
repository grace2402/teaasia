# app/admin/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, TextAreaField, URLField, FloatField, DecimalField, DateTimeField, SelectField
from wtforms.validators import DataRequired, URL, Optional, Length, Email
from wtforms_sqlalchemy.fields import QuerySelectField
from flask_wtf.file import FileField, FileRequired, FileAllowed
from ..models import Catalog, Role
from app import images
from wtforms.fields import DateTimeLocalField

# 自定義 CommaSeparatedListField
class CommaSeparatedListField(StringField):
    def _value(self):
        if self.data:
            # 將列表轉換為逗號分隔的字串
            return ', '.join(self.data)
        else:
            return ''

    def process_formdata(self, valuelist):
        if valuelist:
            # 將輸入的字串按逗號分割，並去除多餘空白與空項
            self.data = [x.strip() for x in valuelist[0].split(',') if x.strip()]
        else:
            self.data = []

# 故事表單
class StoryForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=100)])
    author = StringField('Author', validators=[DataRequired(), Length(max=50)])
    location = StringField('Location', validators=[DataRequired(), Length(max=100)])
    upload = FileField('Image', validators=[Optional(), FileAllowed(images, 'Images only!')])
    description = TextAreaField('Description', validators=[DataRequired(), Length(max=500)])
    available = BooleanField('Available', default=False)
    submit = SubmitField('Submit')

# 更改目錄表單
class ChangeCatalogForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('Submit')

# 產品表單
class ProductForm(FlaskForm):
    common_name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    price = DecimalField('Price', validators=[DataRequired()])
    upload = FileField('Image', validators=[Optional(), FileAllowed(images, 'Images only!')])
    color = StringField('Color', validators=[Optional(), Length(max=50)])
    size = StringField('Size', validators=[Optional(), Length(max=50)])
    catalog_id = QuerySelectField(query_factory=lambda: Catalog.query.all(), get_label="catalog_name", allow_blank=True)
    available = BooleanField('Available', default=True)
    submit = SubmitField('Submit')

# 更改用戶表單
class ChangeUserForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    role = QuerySelectField(query_factory=lambda: Role.query.all(), get_label="name", allow_blank=True)
    address = StringField('Address', validators=[DataRequired(), Length(max=200)])
    confirmed = BooleanField('Confirmed', default=True)
    is_admin_user = BooleanField('Admin', default=False)
    submit = SubmitField('Submit')

# 維運紀錄表單
class MaintenanceRecordForm(FlaskForm):
    datetime = DateTimeLocalField('日期時間', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    location = StringField('位置', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('描述', validators=[DataRequired(), Length(max=500)])
    jira_link = URLField('JIRA 連結', validators=[Optional(), URL()])
    performer = StringField('執行人', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('提交')

# 訂單表單
class OrderForm(FlaskForm):
    submit = SubmitField('Submit')

# 訂單詳情表單
class OrderdetailForm(FlaskForm):
    submit = SubmitField('Submit')

# 出差紀錄表單
class TravelRecordForm(FlaskForm):
    datetime = DateTimeLocalField('日期時間', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    location = StringField('地點', validators=[DataRequired()])
    description = TextAreaField('描述', validators=[DataRequired()])
    jira_link = StringField('JIRA 連結')
    performer = StringField('執行人', validators=[DataRequired()])
    operation_log = TextAreaField('現場操作/紀錄')
    submit = SubmitField('提交')

# Spot 表單
class AddSpotForm(FlaskForm):
    site_name = StringField('案場名稱', validators=[Optional()])
    description = TextAreaField('描述', validators=[Optional()])
    longitude = FloatField('經度', validators=[Optional()])
    latitude = FloatField('緯度', validators=[Optional()])
    gw_list = CommaSeparatedListField('GW清單（用逗號分隔）', validators=[Optional()])
    project_code = StringField('專案代碼', validators=[Optional()])
    pcs_uuid = CommaSeparatedListField('PCS UUID (MQTT KEY)', validators=[Optional()])
    enable_monitoring = BooleanField('啟用多案場監控')
    submit = SubmitField('提交')

class DeleteForm(FlaskForm):
    submit = SubmitField('刪除')

class MaterialForm(FlaskForm):
    device_model = StringField('設備型號', validators=[DataRequired()])
    pid = StringField('PID', validators=[DataRequired()])
    pn = StringField('PN', validators=[DataRequired()])
    status = StringField('狀態')
    keeper = StringField('保管人')
    remark = StringField('備註')
    sim_info = StringField('SIM資訊')
    netsuite_dept = StringField('NetSuite部門')
    eis_program = StringField('EIS專案')
    eg_account = StringField('EG帳戶')
    client = StringField('客戶')
    location = StringField('位置')
    firmware = StringField('韌體版本')
    connection_method = StringField('連接方式')
    note = StringField('備註')
    updated_by = StringField('更新者')
    updated_date = StringField('更新日期')
    pickup_person = StringField('領料人')
    pickup_order_number = StringField('領料單號')
    submit = SubmitField('提交')

class RMARecordForm(FlaskForm):
    pid_mac = StringField('PID / MAC', validators=[DataRequired(), Length(max=64)])
    status = SelectField(
        '狀態',
        choices=[
            ('收到', '收到'),
            ('測試中', '測試中'),
            ('測試正常已退回', '測試正常已退回'),
            ('寄回新GW(請在備註填入PID)', '寄回新GW(請在備註填入PID)')
        ],
        validators=[DataRequired()]
    )
    note = TextAreaField('備註', validators=[Optional(), Length(max=256)])
    jira_link = StringField('JIRA 連結', validators=[Optional(), Length(max=255)])
    submit = SubmitField('提交')

class ClientForm(FlaskForm):
    name = StringField('客戶名稱', validators=[DataRequired(), Length(max=255)])
    website_url = StringField('網站URL', validators=[Optional(), Length(max=512)])
    contact_name = StringField('聯絡人', validators=[Length(max=255)])
    contact_email = StringField('Email', validators=[Optional(), Email(), Length(max=255)])
    contact_phone = StringField('電話', validators=[Length(max=50)])
    submit = SubmitField('提交')

class ContractForm(FlaskForm):
    spot_id = SelectField('案場', coerce=int, validators=[DataRequired()])
    warranty_start = StringField('保固開始時間 (YYYY-MM-DD)', validators=[DataRequired(), Length(max=64)])
    warranty_end = StringField('保固結束時間 (YYYY-MM-DD)', validators=[DataRequired(), Length(max=64)])
    warranty_amount = StringField('保固金額', validators=[Optional(), Length(max=64)])
    maintenance_start = StringField('維護開始時間 (YYYY-MM-DD)', validators=[DataRequired(), Length(max=64)])
    maintenance_end = StringField('維護結束時間 (YYYY-MM-DD)', validators=[DataRequired(), Length(max=64)])
    link = StringField('連結', validators=[Optional(), Length(max=256)])
    submit = SubmitField('送出')
