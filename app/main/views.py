# app/main/views.py
from flask import render_template, redirect, url_for, jsonify, request, flash, abort, current_app, make_response
from flask_login import login_required, current_user
from datetime import datetime, timedelta, date
from functools import wraps
from sqlalchemy import text,func,or_
from .. import db, scheduler
from ..models import (
    User, MaterialJP, Client, Post, MaintenanceRecord, RecordHistory,
    TravelRecord, Catalog, Material, Spot, RMARecord, GWMonitor, Contract, SimCardStatus, SimCardEditRecord,TaipowerExcelRecord,TaipowermeterApply
)
from dateutil.relativedelta import relativedelta
from . import main
from app.admin.forms import (
    MaintenanceRecordForm, TravelRecordForm, AddSpotForm, DeleteForm,
    RMARecordForm, ClientForm, ContractForm
)
from flask_sse import sse
import logging, requests
import config
from webhook import send_message_to_google_chat
import io
import csv
import re
from .iij import iij_activate, iij_suspend, iij_cancel
from warrant import Cognito
from flask_wtf import csrf

# ========== 排程相關函式 ==========
def check_gw_status_single_logic(pid):
    gw = GWMonitor.query.get(pid)
    if not gw:
        return
    try:
        url = f"http://192.168.3.16:5000/get_gw_status/{gw.pid}"
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        online_status = data.get('data', [{}])[0].get('onlineStatus', None)
        if online_status == 0:
            send_message_to_google_chat(gw.webhook_url, f"PID : {gw.pid} 斷線，請確認狀態")
    except Exception as e:
        logging.error(f"[check_gw_status_single_logic] GW={pid} Error: {e}")

def check_gw_status_single_wrapper(app, pid):
    with app.app_context():
        check_gw_status_single_logic(pid)

def add_gw_job(app, gw):
    job_id = f"check_gw_status_{gw.id}"
    try:
        scheduler.remove_job(job_id)
    except:
        pass
    scheduler.add_job(
        id=job_id,
        func=check_gw_status_single_wrapper,
        trigger='interval',
        seconds=gw.frequency,
        kwargs={'app': app, 'pid': gw.id},
        replace_existing=True
    )
    logging.info(f"[Scheduler] Added/Updated job for GW ID={gw.id}, freq={gw.frequency}")

def remove_gw_job(gw_id):
    job_id = f"check_gw_status_{gw_id}"
    try:
        scheduler.remove_job(job_id)
        logging.info(f"[Scheduler] Removed job for GW ID={gw_id}")
    except:
        pass

def create_jobs(app):
    gw_list = GWMonitor.query.all()
    for gw in gw_list:
        add_gw_job(app, gw)
    logging.info(f"[Scheduler] create_jobs() done. total={len(gw_list)}")

# ========== 權限檢查 ==========
def get_jwt_token():

    """
    從 Cognito 取得 JWT access token。若取得失敗，會在日誌中印出錯誤原因並回傳 None。
    """
    try:
        # 建立 Cognito 客戶端
        user_pool_id = config.USER_POOL_ID
        client_id    = config.CLIENT_ID
        username     = config.USERNAME
        password     = config.PASSWORD

        c = Cognito(user_pool_id, client_id, username=username)
        c.authenticate(password=password)

        token = c.access_token
        if not token:
            current_app.logger.error(
                "get_jwt_token: access_token 為空，請檢查 Cognito 認證設定")
        return token

    except Exception as e:
        # 印出 stack trace 方便除錯
        current_app.logger.exception(f"get_jwt_token 失敗：{e}")
        return None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def owner_or_admin_required(model_class):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            record_id = kwargs.get('record_id') or args[0]
            record = model_class.query.get_or_404(record_id)
            if current_user.id != record.user_id and not current_user.is_admin:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def parse_date_and_prefix(s: str):
    """
    解析含有日期與可選前綴的字串，支援格式：
      - "(硬) 2024-05-31" 或 "(軟)2024/05/31"
      - "2024-05-31" 或 "2024/05/31"
      - "210000(2025／9／2)"  (全形斜線)
    回傳 (date_obj, prefix_str)；若無法解析則回傳 (None, "")
    """
    if not s or s.strip().lower() in ["n/a", "na"]:
        return (None, "")
    s = s.replace('／', '/')  # 全形換半形
    # 嘗試找出含前綴的情況
    m = re.search(r'\(\s*(軟|硬)\s*\)\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})', s)
    if m:
        prefix = f"({m.group(1)})"  # 保留括號
        date_str = m.group(2).replace('-', '/')
        try:
            d = datetime.strptime(date_str, '%Y/%m/%d').date()
            return (d, prefix)
        except Exception as e:
            logging.error(f"parse_date_and_prefix error for {s}: {e}")
            return (None, "")
    else:
        # 無前綴情況
        m = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', s)
        if m:
            date_str = m.group(1).replace('-', '/')
            try:
                d = datetime.strptime(date_str, '%Y/%m/%d').date()
                return (d, "")
            except Exception as e:
                logging.error(f"parse_date_and_prefix error for {s}: {e}")
                return (None, "")
        else:
            return (None, "")

def filter_date(col):
    """
    用於 SQL 過濾條件，從指定欄位中取出第一組符合 YYYY-MM-DD 或 YYYY/MM/DD 的字串，
    並將 '-' 替換成 '/'，以 to_date 解析。
    """
    return f"to_date(replace(regexp_replace({col}, '.*(\\d{{4}}[-/]\\d{{1,2}}[-/]\\d{{1,2}}).*', '\\1'), '-', '/'), 'YYYY/MM/DD')"

# ========== SSE & 測試路由 ==========
@main.route("/hello")
def publish_hello():
    sse.publish({"message": "Hello!"}, type='greeting')
    return "Message sent!"

@main.route('/message')
@login_required
def message():
    catalogs = Catalog.get_all()
    posts = Post.get_last5()
    return render_template('message.html', catalogs=catalogs, posts=posts)

@main.route('/post/', methods=['GET'])
def post_message():
    ret_data = {"value": request.args.get('messageValue')}
    p = Post()
    p.constain = ('%.200s' % ret_data['value'])
    p.author = current_user.username
    p.post_datetime = datetime.utcnow()
    db.session.add(p)
    db.session.commit()
    sse.publish({"message": "updatemessage"}, type='greeting')
    return jsonify({'value': 'Succeeded.'})

@main.route('/get/', methods=['GET'])
def get_message():
    posts = Post.get_last5()
    return jsonify([i.serialize for i in posts])

# ========== 首頁 (地圖) ==========
@main.route('/')
def index():
    spots = Spot.query.all()
    spots_list = [{
        'id': s.id,
        'latitude': s.latitude,
        'longitude': s.longitude,
        'description': s.description,
        'site_name': s.site_name,
        'gw_list': s.gw_list or [],
        'project_code': s.project_code or '',
        'client': s.client.name if s.client else '',
        'client_id': s.client.id if s.client else None
    } for s in spots]
    clients = Client.query.all()
    clients_list = [{'id': c.id, 'name': c.name} for c in clients]
    return render_template('index.html', spots=spots_list, clients=clients_list)

@main.route('/get_gw_status/<string:pid>', methods=['GET'])
def get_gw_status(pid):
    # 1. 先簡單驗證 pid 格式
    if not pid:
        return jsonify({'error': 'Missing PID'}), 400

    # 2. 拿 JWT
    jwt_token = get_jwt_token()
    if not jwt_token:
        current_app.logger.error("get_gw_status: 無法取得 JWT")
        return jsonify({'error': 'Unable to retrieve valid JWT token'}), 401

    # 3. 呼叫外部 API
    url = f"https://ndp-api.nextdrive.io/v1/gateways"
    params = {'uuids': pid, 'type': 'product_id'}
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/json"
    }

    try:
        # 加上 timeout，避免 hang 住
        r = requests.get(url, headers=headers, params=params, timeout=5)
        r.raise_for_status()
    except requests.exceptions.Timeout:
        current_app.logger.error(f"get_gw_status: GW={pid} request timed out")
        return jsonify({'error': 'Request to GW API timed out'}), 504
    except requests.exceptions.HTTPError as e:
        # 直接回傳外部回應的 status code 與訊息
        try:
            details = r.json()
        except ValueError:
            details = {'raw_text': r.text}
        return jsonify({
            'error': 'Failed to fetch GW status',
            'status_code': r.status_code,
            'details': details
        }), r.status_code
    except Exception as e:
        current_app.logger.exception(f"get_gw_status: GW={pid} exception")
        return jsonify({'error': 'Internal error', 'message': str(e)}), 500

    # 4. 正常回傳
    return jsonify(r.json()), 200


@main.route('/secret')
@login_required
def secret():
    return 'Only authenticated users are allowed! Current user: %s' % current_user.username

# ========== Site Management ==========
@main.route('/site_management', methods=['GET'], defaults={'spot_id': None})
@main.route('/site_management/<int:spot_id>', methods=['GET', 'POST'])
@login_required
def site_management(spot_id):
    delete_form = DeleteForm()
    # 取得客戶篩選參數，與 index.html 保持一致，參數名稱使用 client_id
    client_id = request.args.get('client_id', type=int)
    # 取得所有客戶，供下拉選單使用
    all_clients = Client.query.all()
    
    if spot_id:
        # 編輯模式
        spot = Spot.query.get_or_404(spot_id)
        form = AddSpotForm(obj=spot)
        if form.validate_on_submit():
            spot.site_name = form.site_name.data
            spot.description = form.description.data
            spot.longitude = form.longitude.data
            spot.latitude = form.latitude.data
            spot.gw_list = [gw.strip() for gw in form.gw_list.data.split(',')] if form.gw_list.data else []
            spot.project_code = form.project_code.data
            db.session.commit()
            flash('站點資訊已更新')
            return redirect(url_for('main.site_management'))
        
        # 編輯模式下同時取得列表資料（含篩選與分頁）
        page = request.args.get('page', 1, type=int)
        site_name_filter = request.args.get('site_name_filter', '', type=str)
        project_code_filter = request.args.get('project_code_filter', '', type=str)
        
        query = Spot.query
        if site_name_filter:
            query = query.filter(Spot.site_name.like(f'%{site_name_filter}%'))
        if project_code_filter:
            query = query.filter(Spot.project_code.like(f'%{project_code_filter}%'))
        if client_id:
            query = query.filter(Spot.client_id == client_id)
        
        pagination = query.paginate(page=page, per_page=10, error_out=False)
        spots = pagination.items
        
        # 組合各站點的合約資訊
        spot_contract_map = {}
        for s in spots:
            cs = Contract.query.filter_by(spot_id=s.id).all()
            spot_contract_map[s.id] = cs
        
        return render_template('site_management.html',
                               spot=spot,
                               spots=spots,
                               form=form,
                               delete_form=delete_form,
                               pagination=pagination,
                               spot_contract_map=spot_contract_map,
                               site_name_filter=site_name_filter,
                               project_code_filter=project_code_filter,
                               client_id=client_id,
                               all_clients=all_clients)
    else:
        # 列表模式
        page = request.args.get('page', 1, type=int)
        site_name_filter = request.args.get('site_name_filter', '', type=str)
        project_code_filter = request.args.get('project_code_filter', '', type=str)
        
        query = Spot.query
        if site_name_filter:
            query = query.filter(Spot.site_name.like(f'%{site_name_filter}%'))
        if project_code_filter:
            query = query.filter(Spot.project_code.like(f'%{project_code_filter}%'))
        if client_id:
            query = query.filter(Spot.client_id == client_id)
        
        pagination = query.paginate(page=page, per_page=10, error_out=False)
        spots = pagination.items
        
        # 組合各站點的合約資訊
        spot_contract_map = {}
        for s in spots:
            cs = Contract.query.filter_by(spot_id=s.id).all()
            spot_contract_map[s.id] = cs
        
        return render_template('site_management.html',
                               spots=spots,
                               delete_form=delete_form,
                               pagination=pagination,
                               spot_contract_map=spot_contract_map,
                               site_name_filter=site_name_filter,
                               project_code_filter=project_code_filter,
                               client_id=client_id,
                               all_clients=all_clients)

# ========== Material Management (TW) ==========
@main.route('/material_management')
@login_required
def material_management():
    page = request.args.get('page', 1, type=int)
    dm = request.args.get('device_model')
    st = request.args.get('status')
    kp = request.args.get('keeper')
    pm = request.args.get('pi_mac','')
    cf = request.args.get('client','')
    cid = request.args.get('client_id', type=int)
    q = Material.query.filter(Material.is_deleted==False)
    if dm: q = q.filter(Material.device_model==dm)
    if st: q = q.filter(Material.status==st)
    if kp: q = q.filter(Material.keeper==kp)
    if pm: q = q.filter(Material.pid.ilike(f'%{pm}%'))
    if cf: q = q.filter(Material.client.ilike(f'%{cf}%'))
    if cid: q = q.filter(Material.client_id==cid)
    pag = q.order_by(Material.updated_date.desc()).paginate(page=page, per_page=100, error_out=False)
    return render_template('material_management.html',
        materials=pag.items,
        pagination=pag,
        device_model_filter=dm,
        status_filter=st,
        keeper_filter=kp,
        pi_mac_filter=pm,
        client_filter=cf,
        client_id_filter=cid,
        clients=Client.query.all()
    )

# ========== Maintenance Records ==========
@main.route('/maintenance_records')
@login_required
def maintenance_records():
    form = MaintenanceRecordForm()
    drf = request.args.get('date_range_filter')
    sd = request.args.get('start_date')
    ed = request.args.get('end_date')
    lf = request.args.get('location_filter')
    df = request.args.get('description_filter')
    page = request.args.get('page', 1, type=int)
    q = MaintenanceRecord.query
    if drf:
        now = datetime.now()
        if drf=='3days': q = q.filter(MaintenanceRecord.datetime>=now-timedelta(days=3))
        elif drf=='1week': q = q.filter(MaintenanceRecord.datetime>=now-timedelta(weeks=1))
        elif drf=='1month': q = q.filter(MaintenanceRecord.datetime>=now-timedelta(weeks=4))
        elif drf=='6months': q = q.filter(MaintenanceRecord.datetime>=now-timedelta(weeks=26))
        elif drf=='1year': q = q.filter(MaintenanceRecord.datetime>=now-timedelta(weeks=52))
        elif drf=='custom' and sd and ed:
            start = datetime.strptime(sd,'%Y-%m-%d')
            end = datetime.strptime(ed,'%Y-%m-%d')
            q = q.filter(MaintenanceRecord.datetime.between(start,end))
    if lf: q = q.filter(MaintenanceRecord.location.contains(lf))
    if df: q = q.filter(MaintenanceRecord.description.contains(df))
    pag = q.order_by(MaintenanceRecord.datetime.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template('maintenance_records.html', maintenance_records=pag.items, pagination=pag, form=form)

@main.route('/add_maintenance_record', methods=['POST'])
@login_required
def add_maintenance_record():
    form = MaintenanceRecordForm()
    if form.validate_on_submit():
        try:
            db.session.add(MaintenanceRecord(
                datetime=form.datetime.data,
                location=form.location.data,
                description=form.description.data,
                jira_link=form.jira_link.data,
                performer=form.performer.data,
                user_id=current_user.id
            ))
            db.session.commit()
            flash('維運紀錄已新增')
        except Exception as e:
            flash(f'新增維運紀錄時發生錯誤: {e}')
            db.session.rollback()
    else:
        flash(f'表單提交失敗: {form.errors}')
    return redirect(url_for('main.maintenance_records'))

@main.route('/edit_maintenance_record/<int:record_id>', methods=['GET','POST'])
@login_required
@owner_or_admin_required(MaintenanceRecord)
def edit_maintenance_record(record_id):
    rec = MaintenanceRecord.query.get_or_404(record_id)
    form = MaintenanceRecordForm(obj=rec)
    if form.validate_on_submit():
        rec.datetime = form.datetime.data
        rec.location = form.location.data
        rec.description = form.description.data
        rec.jira_link = form.jira_link.data
        rec.performer = form.performer.data
        db.session.commit()
        flash('維運紀錄已更新')
        return redirect(url_for('main.maintenance_records'))
    return render_template('edit_maintenance_record.html', form=form, record=rec)

@main.route('/delete_maintenance_record/<int:record_id>', methods=['POST'])
@login_required
@owner_or_admin_required(MaintenanceRecord)
def delete_maintenance_record(record_id):
    rec = MaintenanceRecord.query.get_or_404(record_id)
    db.session.delete(rec)
    db.session.commit()
    flash('維運紀錄已删除')
    return redirect(url_for('main.maintenance_records'))

@main.route('/view_record_history/<int:record_id>', methods=['GET'])
@login_required
@admin_required
def view_record_history(record_id):
    rec = MaintenanceRecord.query.get_or_404(record_id)
    history = RecordHistory.query.filter_by(maintenance_record_id=rec.id).order_by(RecordHistory.edited_at.desc()).all()
    return render_template('view_record_history.html', record=rec, history_records=history, form=MaintenanceRecordForm())

@main.route('/revert_to_version/<int:history_id>', methods=['POST'])
@login_required
@admin_required
def revert_to_version(history_id):
    h = RecordHistory.query.get_or_404(history_id)
    r = h.record
    r.datetime = h.datetime
    r.location = h.location
    r.description = h.description
    r.jira_link = h.jira_link
    r.performer = h.performer
    db.session.commit()
    flash('紀錄已回到選擇的版本')
    return redirect(url_for('main.maintenance_records'))

# ========== Travel Records ==========
@main.route('/travel_records')
@login_required
def travel_records():
    form = TravelRecordForm()
    drf = request.args.get('date_range_filter')
    sd = request.args.get('start_date')
    ed = request.args.get('end_date')
    lf = request.args.get('location_filter')
    df = request.args.get('description_filter')
    page = request.args.get('page', 1, type=int)
    q = TravelRecord.query
    if drf:
        now = datetime.now()
        if drf=='3days': q = q.filter(TravelRecord.datetime>=now-timedelta(days=3))
        elif drf=='1week': q = q.filter(TravelRecord.datetime>=now-timedelta(weeks=1))
        elif drf=='1month': q = q.filter(TravelRecord.datetime>=now-timedelta(weeks=4))
        elif drf=='6months': q = q.filter(TravelRecord.datetime>=now-timedelta(weeks=26))
        elif drf=='1year': q = q.filter(TravelRecord.datetime>=now-timedelta(weeks=52))
        elif drf=='custom' and sd and ed:
            start = datetime.strptime(sd,'%Y-%m-%d')
            end = datetime.strptime(ed,'%Y-%m-%d')
            q = q.filter(TravelRecord.datetime.between(start,end))
    if lf: q = q.filter(TravelRecord.location.contains(lf))
    if df: q = q.filter(TravelRecord.description.contains(df))
    pag = q.order_by(TravelRecord.datetime.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template('travel_records.html', travel_records=pag.items, pagination=pag, form=form)

@main.route('/add_travel_record', methods=['POST'])
@login_required
def add_travel_record():
    f = TravelRecordForm()
    if f.validate_on_submit():
        try:
            db.session.add(TravelRecord(
                datetime=f.datetime.data,
                location=f.location.data,
                description=f.description.data,
                jira_link=f.jira_link.data,
                performer=f.performer.data,
                operation_log=f.operation_log.data,
                user_id=current_user.id
            ))
            db.session.commit()
            flash('出差紀錄已新增')
        except Exception as e:
            flash(f'新增出差紀錄時發生錯誤: {e}')
            db.session.rollback()
    else:
        flash(f'表單提交失敗: {f.errors}')
    return redirect(url_for('main.travel_records'))

@main.route('/edit_travel_record/<int:record_id>', methods=['GET','POST'])
@login_required
@owner_or_admin_required(TravelRecord)
def edit_travel_record(record_id):
    r = TravelRecord.query.get_or_404(record_id)
    f = TravelRecordForm(obj=r)
    if f.validate_on_submit():
        try:
            r.datetime = f.datetime.data
            r.location = f.location.data
            r.description = f.description.data
            r.jira_link = f.jira_link.data
            r.performer = f.performer.data
            r.operation_log = f.operation_log.data
            db.session.commit()
            flash('出差紀錄已更新')
            return redirect(url_for('main.travel_records'))
        except Exception as e:
            flash(f'更新出差紀錄時發生錯誤: {e}')
            db.session.rollback()
    return render_template('edit_travel_record.html', form=f, record=r)

@main.route('/delete_travel_record/<int:record_id>', methods=['POST'])
@login_required
@owner_or_admin_required(TravelRecord)
def delete_travel_record(record_id):
    r = TravelRecord.query.get_or_404(record_id)
    db.session.delete(r)
    db.session.commit()
    flash('出差紀錄已删除')
    return redirect(url_for('main.travel_records'))

# ========== Material CRUD (TW) ==========
@main.route('/update_material/<int:material_id>', methods=['POST'])
@login_required
def update_material(material_id):
    mat = Material.query.get_or_404(material_id)
    data = request.get_json() or {}
    if 'client' in data:
        cli_text = data.pop('client').strip()
        if cli_text:
            c = Client.query.filter_by(name=cli_text).first()
            if c:
                mat.client = c.name
                mat.client_id = c.id
            else:
                mat.client = cli_text
                mat.client_id = None
        else:
            mat.client=''
            mat.client_id=None
    elif 'client_id' in data:
        cid = data.pop('client_id')
        if cid:
            c = Client.query.get(int(cid))
            if c:
                mat.client = c.name
                mat.client_id = c.id
            else:
                mat.client=''
                mat.client_id=None
        else:
            mat.client=''
            mat.client_id=None
    for k,v in data.items():
        if hasattr(mat,k): setattr(mat,k,v)
    mat.updated_date = datetime.utcnow()
    mat.updated_by = current_user.email
    try:
        db.session.commit()
        return jsonify(success=True, newClientName=mat.client)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)),400

@main.route('/add_material', methods=['POST'])
@login_required
def add_material():
    data = request.get_json()
    
    # 處理 Client
    cli_name = (data.get('client') or '').strip()
    cli_obj = None
    if cli_name:
        cli_obj = Client.query.filter_by(name=cli_name).first()
        if not cli_obj:
            cli_obj = Client(name=cli_name)
            db.session.add(cli_obj)
            db.session.flush()  # 取得 cli_obj.id

    # 處理 Location 與 Spot
    location = data.get('location', '').strip()
    spot_obj = None
    if location:
        spot_obj = Spot.query.filter_by(site_name=location).first()
        if not spot_obj:
            spot_obj = Spot(
                site_name=location,
                description='',
                longitude=0,
                latitude=0,
                gw_list=None,
                project_code='',
                client_id=cli_obj.id if cli_obj else None
            )
            db.session.add(spot_obj)
            db.session.flush()  # 取得新站點 id
        # 檢查 PID，若不含冒號則更新 spot_obj 的 gw_list
        pid = (data.get('pid') or '').strip()
        if pid and (":" not in pid):
            new_gw_list = [p.strip() for p in pid.split(',') if p.strip()]
            if spot_obj.gw_list:
                combined = list(set(spot_obj.gw_list) | set(new_gw_list))
                spot_obj.gw_list = combined
            else:
                spot_obj.gw_list = new_gw_list

    # 建立 Material 物件（id 讓 DB 自動產生）
    m = Material(
        device_model=data.get('device_model'),
        pid=data.get('pid'),
        pn=data.get('pn'),
        status=data.get('status'),
        keeper=data.get('keeper'),
        remark=data.get('remark'),
        sim_info=data.get('sim_info'),
        netsuite_dept=data.get('netsuite_dept'),
        eis_program=data.get('eis_program'),
        eg_account=data.get('eg_account'),
        client=cli_name,
        client_id=cli_obj.id if cli_obj else None,
        location=location,
        firmware=data.get('firmware'),
        connection_method=data.get('connection_method'),
        note=data.get('note'),
        updated_date=datetime.utcnow(),
        updated_by=current_user.email,
        pickup_person=data.get('pickup_person'),
        pickup_order_number=data.get('pickup_order_number')
    )
    
    try:
        db.session.add(m)
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e))


@main.route('/delete_material/<int:material_id>', methods=['POST'])
@login_required
def delete_material(material_id):
    mat = Material.query.get_or_404(material_id)
    try:
        mat.is_deleted = True
        mat.updated_date = datetime.utcnow()
        mat.updated_by = current_user.email

        # 若物料有 location 和 pid（且 pid 格式不含冒號），檢查並從 Spot 的 gw_list 移除該 pid
        pid = mat.pid.strip() if mat.pid else ""
        location = mat.location.strip() if mat.location else ""
        if pid and location and (":" not in pid):
            # 查詢對應的 Spot
            spot = Spot.query.filter_by(site_name=location).first()
            if spot and spot.gw_list:
                # 檢查其他非刪除的 Material 是否還使用該 pid
                other = Material.query.filter(
                    Material.location == location,
                    Material.pid == pid,
                    Material.is_deleted == False,
                    Material.id != mat.id
                ).first()
                # 若無其他 Material 使用該 pid，則從 Spot 的 gw_list 移除
                if not other and pid in spot.gw_list:
                    spot.gw_list = [p for p in spot.gw_list if p != pid]
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e))


# ========== Spot CRUD ==========
@main.route('/add_spot', methods=['GET','POST'])
@login_required
def add_spot():
    f = AddSpotForm()
    cs = Client.query.all()
    if f.is_submitted():
        s = Spot()
        s.site_name = f.site_name.data.strip() if f.site_name.data else None
        s.description = f.description.data.strip() if f.description.data else None
        s.project_code = f.project_code.data.strip() if f.project_code.data else None
        s.longitude = f.longitude.data if f.longitude.data else None
        s.latitude = f.latitude.data if f.latitude.data else None
        s.gw_list = f.gw_list.data if f.gw_list.data else None
        cid = request.form.get('client_id')
        s.client_id = int(cid) if cid else None
        db.session.add(s)
        db.session.commit()
        flash('新站點已添加')
        return redirect(url_for('main.site_management'))
    return render_template('add_spot.html', form=f, clients=cs)

@main.route('/edit_spot/<int:spot_id>', methods=['GET','POST'])
@login_required
def edit_spot(spot_id):
    sp = Spot.query.get_or_404(spot_id)
    f = AddSpotForm(obj=sp)
    cs = Client.query.all()
    if f.validate_on_submit():
        f.populate_obj(sp)
        cid = request.form.get('client_id')
        sp.client_id = int(cid) if cid else None
        db.session.commit()
        flash('站點資訊已更新')
        return redirect(url_for('main.site_management'))
    return render_template('edit_spot.html', form=f, spot=sp, clients=cs)

@main.route('/delete_spot/<int:spot_id>', methods=['POST'])
@login_required
def delete_spot(spot_id):
    try:
        sp = Spot.query.get_or_404(spot_id)
        db.session.delete(sp)
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)),400

# ========== RMA Records ==========
@main.route('/rma_records')
@login_required
def rma_records():
    page = request.args.get('page',1,int)
    st = request.args.get('status')
    pm = request.args.get('pid_mac')
    q = RMARecord.query
    if st: q = q.filter(RMARecord.status==st)
    if pm: q = q.filter(RMARecord.pid_mac.ilike(f'%{pm}%'))
    pag = q.order_by(RMARecord.id.asc()).paginate(page=page, per_page=100, error_out=False)
    return render_template('rma_records.html',records=pag.items,pagination=pag,status_filter=st,pid_mac_filter=pm)

@main.route('/add_rma_record', methods=['POST'])
@login_required
def add_rma_record():
    f = RMARecordForm()
    if f.validate_on_submit():
        try:
            db.session.add(RMARecord(
                pid_mac=f.pid_mac.data,
                status=f.status.data,
                note=f.note.data,
                jira_link=f.jira_link.data,
                user_id=current_user.id
            ))
            db.session.commit()
            flash('RMA 紀錄已新增')
        except Exception as e:
            flash(f'新增 RMA 紀錄時發生錯誤: {e}')
            db.session.rollback()
    else:
        flash(f'表單提交失敗: {f.errors}')
    return redirect(url_for('main.rma_records'))

@main.route('/update_rma_status/<int:record_id>', methods=['POST'])
@login_required
@owner_or_admin_required(RMARecord)
def update_rma_status(record_id):
    rec = RMARecord.query.get_or_404(record_id)
    ns = request.form.get('status')
    if ns not in ['收到','測試中','測試正常已退回','寄回新GW(請在備註填入PID)']:
        flash('無效的狀態選項','danger')
        return redirect(url_for('main.rma_records'))
    rec.status = ns
    db.session.commit()
    flash('RMA 狀態已更新','success')
    return redirect(url_for('main.rma_records'))

@main.route('/edit_rma_record/<int:record_id>', methods=['GET','POST'])
@login_required
@owner_or_admin_required(RMARecord)
def edit_rma_record(record_id):
    rec = RMARecord.query.get_or_404(record_id)
    f = RMARecordForm(obj=rec)
    if f.validate_on_submit():
        rec.pid_mac = f.pid_mac.data
        rec.note = f.note.data
        rec.jira_link = f.jira_link.data
        db.session.commit()
        flash('RMA 紀錄已更新','success')
        return redirect(url_for('main.rma_records'))
    return render_template('edit_rma_record.html', form=f, record=rec)

@main.route('/delete_rma_record/<int:record_id>', methods=['POST'])
@login_required
@owner_or_admin_required(RMARecord)
def delete_rma_record(record_id):
    rec = RMARecord.query.get_or_404(record_id)
    db.session.delete(rec)
    db.session.commit()
    flash('RMA 紀錄已刪除')
    return redirect(url_for('main.rma_records'))

# ========== CSV 匯入 (TW) ==========
@main.route('/import_csv', methods=['POST'])
@login_required
def import_csv():
    if 'csv_file' not in request.files:
        print("❌ [DEBUG] csv_file not found in request.files")
        return jsonify(success=False, error='No file in request'), 400

    file = request.files['csv_file']
    if file.filename == '':
        print("❌ [DEBUG] file.filename is empty")
        return jsonify(success=False, error='No selected file'), 400

    try:
        import io, csv
        raw_bytes = file.read()
        print(f"✅ [DEBUG] Raw bytes length: {len(raw_bytes)}")
        file.stream.seek(0)
        stream = io.StringIO(raw_bytes.decode("utf-8", errors="replace"))
        csv_reader = csv.DictReader(stream)
        
        print(f"✅ [DEBUG] CSV header: {csv_reader.fieldnames}")

        # 如果需要確保序列存在，可保留這行（但不會用來賦值給 id）
        db.session.execute(text("CREATE SEQUENCE IF NOT EXISTS materials_id_seq"))

        row_count = 0
        for idx, row in enumerate(csv_reader, start=1):
            # 檢查是否為空行（所有欄位皆空白或 None）
            if not any((str(v).strip() for v in row.values() if v is not None)):
                print(f"⚠️ [DEBUG] Skipping empty row {idx}")
                continue

            print(f"✅ [DEBUG] Processing row {idx}: {row}")
            row_count += 1
            device_model       = row.get('Device Model', '')
            pid                = row.get('PI/MAC Address', '').strip()
            pn                 = row.get('P/N', '')
            status             = row.get('狀態', '')
            keeper             = row.get('保管人', '')
            remark             = row.get('Remark', '')
            sim_info           = row.get('SIM卡資訊', '')
            netsuite_dept      = row.get('NetSuite Dept', '')
            eis_program        = row.get('EIS Program', '')
            eg_account         = row.get('EG+ Account', '')
            client_name        = (row.get('Client') or '').strip()
            location           = row.get('Location', '')
            firmware           = row.get('Firmware', '')
            connection_method  = row.get('連網方式', '')
            note               = row.get('NOTE', '')
            pickup_person      = row.get('領料人', '')
            pickup_order_number= row.get('領料單號', '')

            # 取得或建立 Client
            client_obj = None
            if client_name:
                client_obj = Client.query.filter_by(name=client_name).first()
                if client_obj:
                    print(f"✅ [DEBUG] Found existing Client: {client_obj}")
                else:
                    client_obj = Client(name=client_name)
                    db.session.add(client_obj)
                    db.session.flush()  # 取得 client_obj.id
                    print(f"✅ [DEBUG] Created new Client: {client_obj}")

            # 處理 Spot：若 CSV 中有 Location，檢查 Spot 表中是否已存在此站點
            spot_obj = None
            if location:
                spot_obj = Spot.query.filter_by(site_name=location).first()
                if not spot_obj:
                    spot_obj = Spot(
                        site_name=location,
                        description='',
                        longitude=0,
                        latitude=0,
                        gw_list=None,
                        project_code='',
                        client_id=client_obj.id if client_obj else None
                    )
                    db.session.add(spot_obj)
                    db.session.flush()
                    print(f"✅ [DEBUG] Created new Spot: {spot_obj.site_name}")
                else:
                    print(f"✅ [DEBUG] Found existing Spot: {spot_obj.site_name}")

                # 若 PI/MAC Address 為不含冒號之格式，解析並更新 Spot 的 gw_list 欄位
                if pid and (":" not in pid):
                    new_gw_list = [p.strip() for p in pid.split(',') if p.strip()]
                    if spot_obj.gw_list:
                        combined = list(set(spot_obj.gw_list) | set(new_gw_list))
                        spot_obj.gw_list = combined
                    else:
                        spot_obj.gw_list = new_gw_list
                    print(f"✅ [DEBUG] Updated Spot '{spot_obj.site_name}' gw_list to: {spot_obj.gw_list}")

            new_material = Material(
                device_model=device_model,
                pid=pid,
                pn=pn,
                status=status,
                keeper=keeper,
                remark=remark,
                sim_info=sim_info,
                netsuite_dept=netsuite_dept,
                eis_program=eis_program,
                eg_account=eg_account,
                client=client_name,
                client_id=client_obj.id if client_obj else None,
                location=location,
                firmware=firmware,
                connection_method=connection_method,
                note=note,
                pickup_person=pickup_person,
                pickup_order_number=pickup_order_number,
                updated_date=datetime.utcnow(),
                updated_by=current_user.email,
                is_deleted=False
            )

            db.session.add(new_material)
            print(f"✅ [DEBUG] Added new Material for row {idx}: {new_material}")

        db.session.commit()
        print(f"✅ [DEBUG] CSV 匯入成功，共匯入 {row_count} 筆資料")
        return jsonify(success=True)

    except Exception as e:
        db.session.rollback()
        print("❌ [DEBUG] import_csv exception:", e)
        return jsonify(success=False, error=str(e)), 400


# ========== GW Monitor ==========
@main.route('/gw_monitor')
@login_required
def gw_monitor():
    spots = Spot.query.all()
    gw_monitors = GWMonitor.query.all()
    return render_template('gw_monitor.html',
        spots=[s.to_dict() for s in spots],
        gw_monitors=gw_monitors)

@main.route('/add_gw', methods=['POST'])
@login_required
def add_gw():
    gw_id=request.form.get('gw_id')
    pid=request.form.get('pid')
    freq=request.form.get('frequency')
    whurl=request.form.get('webhook_url')
    if not gw_id or not pid or not freq:
        flash('請完整填寫 GW ID、PID 和偵測頻率。','danger')
        return redirect(url_for('main.gw_monitor'))
    try:
        freq=int(freq)
        if freq<=0:
            flash('偵測頻率必須為正整數。','danger')
            return redirect(url_for('main.gw_monitor'))
    except:
        flash('偵測頻率必須為整數。','danger')
        return redirect(url_for('main.gw_monitor'))
    exist=GWMonitor.query.filter_by(gw_id=gw_id).first()
    if exist:
        flash(f'GW ID "{gw_id}" 已存在，無法重複添加。','danger')
        return redirect(url_for('main.gw_monitor'))
    try:
        new_gw=GWMonitor(gw_id=gw_id,pid=pid,frequency=freq,webhook_url=whurl)
        db.session.add(new_gw)
        db.session.commit()
        app_obj=current_app._get_current_object()
        add_gw_job(app_obj,new_gw)
        flash('監控 GW 已成功新增。','success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"[add_gw] Error while adding GW: {e}")
        flash(f'新增失敗，請稍後重試: {e}','danger')
    return redirect(url_for('main.gw_monitor'))

@main.route('/edit_gw/<int:gw_id>', methods=['POST'])
@login_required
def edit_gw(gw_id):
    gw=GWMonitor.query.get_or_404(gw_id)
    d=request.form
    gw.gw_id=d.get('gw_id')
    gw.pid=d.get('pid')
    try:
        gw.frequency=int(d.get('frequency',10))
    except:
        gw.frequency=10
    gw.webhook_url=d.get('webhook_url')
    db.session.commit()
    app_obj=current_app._get_current_object()
    add_gw_job(app_obj,gw)
    flash('編輯監控 GW 成功')
    return redirect(url_for('main.gw_monitor'))

@main.route('/delete_gw/<int:gw_id>', methods=['POST'])
@login_required
def delete_gw(gw_id):
    gw=GWMonitor.query.get_or_404(gw_id)
    remove_gw_job(gw_id)
    db.session.delete(gw)
    db.session.commit()
    flash('刪除監控 GW 成功')
    return redirect(url_for('main.gw_monitor'))

# ========== Client Management ==========
@main.route('/client_management', methods=['GET'])
@login_required
def client_management():
    # 取得目前頁碼
    page = request.args.get('page', 1, type=int)
    
    # 取得篩選參數
    name_filter = request.args.get('name_filter', '', type=str)
    contact_filter = request.args.get('contact_filter', '', type=str)
    
    # 建立基本查詢
    query = Client.query
    
    # 根據篩選條件調整查詢
    if name_filter:
        query = query.filter(Client.name.like(f'%{name_filter}%'))
    if contact_filter:
        query = query.filter(Client.contact_name.like(f'%{contact_filter}%'))
    
    # 分頁：每頁顯示 10 筆資料
    pagination = query.paginate(page=page, per_page=10, error_out=False)
    clients = pagination.items

    # 將參數傳給模板以便顯示原先的搜尋條件
    return render_template('client_management.html',
                           clients=clients,
                           pagination=pagination,
                           name_filter=name_filter,
                           contact_filter=contact_filter)


# ========== 站台列表 ==========
@main.route('/platforms')
@login_required
def platforms():
    clients = Client.query.filter(
        Client.website_url.isnot(None),
        Client.website_url != ''
    ).order_by(Client.name).all()
    return render_template('platforms.html', clients=clients)


@main.route('/add_client', methods=['POST'])
@login_required
def add_client():
    form = ClientForm()
    # 如果 CSRF 或其他驗證失敗，form.validate_on_submit() == False
    if form.validate_on_submit():
        client = Client(
            name=form.name.data,
            website_url=form.website_url.data,
            contact_name=form.contact_name.data,
            contact_email=form.contact_email.data,
            contact_phone=form.contact_phone.data
        )
        db.session.add(client)
        db.session.commit()
        flash('客戶新增成功！', 'success')
    else:
        # 顯示各欄位錯誤
        for field, errors in form.errors.items():
            label = getattr(form, field).label.text
            for err in errors:
                flash(f"{label}：{err}", 'danger')
    # 無論成功或失敗，都回列表
    return redirect(url_for('main.client_management'))


@main.route('/edit_client/<int:client_id>', methods=['GET','POST'])
@login_required
def edit_client(client_id):
    c=Client.query.get_or_404(client_id)
    f=ClientForm(obj=c)
    if f.validate_on_submit():
        c.name=f.name.data
        c.website_url=f.website_url.data
        c.contact_name=f.contact_name.data
        c.contact_email=f.contact_email.data
        c.contact_phone=f.contact_phone.data
        db.session.commit()
        flash('客戶資訊已更新','success')
        return redirect(url_for('main.client_management'))
    return render_template('edit_client.html', form=f, title="編輯客戶")

@main.route('/delete_client/<int:client_id>', methods=['POST'])
@login_required
def delete_client(client_id):
    c=Client.query.get_or_404(client_id)
    if Spot.query.filter_by(client_id=client_id).count()>0:
        flash('無法刪除，請先刪除或重新指派此客戶的 Spot','danger')
        return redirect(url_for('main.client_management'))
    db.session.delete(c)
    db.session.commit()
    flash('客戶已刪除','success')
    return redirect(url_for('main.client_management'))

# ========== Spot Management (Index) ==========
@main.route('/spot_management', defaults={'client_id':None})
@main.route('/spot_management/<int:client_id>')
@login_required
def spot_management(client_id):
    if client_id:
        s=Spot.query.filter_by(client_id=client_id).all()
    else:
        s=Spot.query.all()
    clients=[{'id':x.id,'name':x.name} for x in Client.query.all()]
    return render_template('index.html',spots=[y.to_dict() for y in s],clients=clients)

@main.route('/get_gateway_devices/<string:gateway_uuid>', methods=['GET'])
def get_gateway_devices(gateway_uuid):
    jwt_token=get_jwt_token()
    if not jwt_token:
        return jsonify({'error':'Unable to retrieve valid JWT token'}),401
    try:
        url=f"https://ndp-api.nextdrive.io/v1/gateways/{gateway_uuid}/devices"
        r=requests.get(url, headers={"Authorization":f"Bearer {jwt_token}"})
        if r.status_code!=200:
            return jsonify({'error':'Failed to fetch gateway devices','details':r.json()}),r.status_code
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'error':str(e)}),500

# ========== Contract Management ==========
@main.route('/contract_management', methods=['GET'])
@login_required
def contract_management():
    # 取得篩選／搜尋參數
    spot_id_filter            = request.args.get('spot_id_filter', '')
    warranty_status_filter    = request.args.get('warranty_status_filter', '')
    maintenance_status_filter = request.args.get('maintenance_status_filter', '')
    search                    = request.args.get('search', '').strip()

    today = date.today()
    one_month_later = today + relativedelta(months=3)

    # 起始 query
    q = Contract.query

    # 案場篩選
    if spot_id_filter.isdigit():
        q = q.filter(Contract.spot_id == int(spot_id_filter))

    # 保固狀態篩選
    if warranty_status_filter == 'within':
        q = q.filter(text(
            "warranty_start != 'N/A' AND warranty_end != 'N/A' "
            "AND warranty_end ~ '\\d{4}[-/]\\d{1,2}[-/]\\d{1,2}' "
            f"AND {filter_date('warranty_start')} <= :today "
            f"AND {filter_date('warranty_end')} >= :today"
        )).params(today=today)
    elif warranty_status_filter == 'expired':
        q = q.filter(text(
            "warranty_end != 'N/A' AND warranty_end ~ '\\d{4}[-/]\\d{1,2}[-/]\\d{1,2}' "
            f"AND {filter_date('warranty_end')} < :today"
        )).params(today=today)

    # 維護狀態篩選
    if maintenance_status_filter == 'within':
        q = q.filter(text(
            "maintenance_start != 'N/A' AND maintenance_end != 'N/A' "
            "AND maintenance_end ~ '\\d{4}[-/]\\d{1,2}[-/]\\d{1,2}' "
            f"AND {filter_date('maintenance_start')} <= :today "
            f"AND {filter_date('maintenance_end')} >= :today"
        )).params(today=today)
    elif maintenance_status_filter == 'expired':
        q = q.filter(text(
            "maintenance_end != 'N/A' AND maintenance_end ~ '\\d{4}[-/]\\d{1,2}[-/]\\d{1,2}' "
            f"AND {filter_date('maintenance_end')} < :today"
        )).params(today=today)

    # 關鍵字搜尋（案場名稱或公司名稱）
    if search:
        q = (
            q.join(Spot, Contract.spot_id == Spot.id)
             .join(Client, Spot.client_id == Client.id)
             .filter(
                 or_(
                     Spot.site_name.ilike(f'%{search}%'),
                     Client.name.ilike(f'%{search}%')
                 )
             )
        )

    # 取得所有符合條件的 contracts
    contracts = q.all()

    # 解析日期並抓前綴
    for c in contracts:
        # 保固
        ws_date, ws_prefix = parse_date_and_prefix(c.warranty_start or "")
        we_date, we_prefix = parse_date_and_prefix(c.warranty_end   or "")
        c.warranty_start_date = ws_date
        c.warranty_end_date   = we_date
        c.warranty_prefix     = ws_prefix or we_prefix

        # 維護
        ms_date, ms_prefix = parse_date_and_prefix(c.maintenance_start or "")
        me_date, me_prefix = parse_date_and_prefix(c.maintenance_end   or "")
        c.maintenance_start_date = ms_date
        c.maintenance_end_date   = me_date
        c.maintenance_prefix     = ms_prefix or me_prefix

    # 計算排序用 key
    def sort_key(c):
        ws = c.warranty_end_date or date(9999,12,31)
        ms = c.maintenance_end_date or date(9999,12,31)
        min_end = min(ws, ms)
        group   = 1 if min_end < today else 0
        return (group, min_end)

    sorted_contracts = sorted(contracts, key=sort_key)

    # 手動分頁
    per_page = 10
    page     = request.args.get('page', 1, type=int)
    total    = len(sorted_contracts)
    start    = (page - 1) * per_page
    end      = start + per_page
    page_contracts = sorted_contracts[start:end]

    # 建立 spot_id → client_name map（僅針對本頁 contracts）
    spot_ids = [c.spot_id for c in page_contracts if c.spot_id]
    spot_client_map = {}
    if spot_ids:
        spots_data = db.session.query(Spot.id, Spot.client_id)\
                               .filter(Spot.id.in_(spot_ids)).all()
        client_ids = [s.client_id for s in spots_data if s.client_id]
        clients    = db.session.query(Client.id, Client.name)\
                               .filter(Client.id.in_(client_ids)).all()
        client_map = {cid: name for cid, name in clients}
        spot_client_map = {sid: client_map.get(cid, '無對應公司')
                           for sid, cid in spots_data}

    # 準備表單 & 下拉選單
    f     = ContractForm()
    spots = Spot.query.order_by(Spot.site_name).all()
    f.spot_id.choices = [(s.id, s.site_name) for s in spots]

    # 組 pagination 物件
    class SimplePagination:
        def __init__(self, page, per_page, total):
            self.page     = page
            self.per_page = per_page
            self.total    = total
            self.pages    = (total + per_page - 1) // per_page

        @property
        def has_prev(self): return self.page > 1
        @property
        def has_next(self): return self.page < self.pages

        def iter_pages(self, left_edge=2, left_current=2, right_current=2, right_edge=2):
            last = 0
            for num in range(1, self.pages + 1):
                if num <= left_edge or \
                   (num > self.page - left_current - 1 and num < self.page + right_current) or \
                   num > self.pages - right_edge:
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num

    pagination = SimplePagination(page, per_page, total)

    return render_template(
        'contract_management.html',
        contracts       = page_contracts,
        form            = f,
        spots           = spots,
        pagination      = pagination,
        today           = today,
        one_month_later = one_month_later,
        search          = search,
        spot_client_map = spot_client_map
    )

@main.route('/add_contract', methods=['GET','POST'])
@login_required
def add_contract():
    f = ContractForm()
    s = Spot.query.order_by(Spot.site_name).all()
    f.spot_id.choices = [(z.id, z.site_name) for z in s]
    if f.validate_on_submit():
        new_contract = Contract(
            warranty_start = f.warranty_start.data,
            warranty_end = f.warranty_end.data,
            warranty_amount = f.warranty_amount.data,  # 新增保固金額欄位
            maintenance_start = f.maintenance_start.data,
            maintenance_end = f.maintenance_end.data,
            spot_id = f.spot_id.data,
            link = f.link.data
        )
        db.session.add(new_contract)
        db.session.commit()
        flash('合約已新增', 'success')
        return redirect(url_for('main.contract_management'))
    return render_template('edit_contract.html', form=f, title="新增合約")


@main.route('/edit_contract/<int:contract_id>', methods=['GET','POST'])
@login_required
def edit_contract(contract_id):
    c = Contract.query.get_or_404(contract_id)
    f = ContractForm(obj=c)
    s = Spot.query.order_by(Spot.site_name).all()
    f.spot_id.choices = [(z.id, z.site_name) for z in s]
    if f.validate_on_submit():
        c.warranty_start = f.warranty_start.data
        c.warranty_end = f.warranty_end.data
        c.warranty_amount = f.warranty_amount.data  # 更新保固金額欄位
        c.maintenance_start = f.maintenance_start.data
        c.maintenance_end = f.maintenance_end.data
        c.spot_id = f.spot_id.data
        c.link = f.link.data
        db.session.commit()
        flash('合約已更新', 'success')
        return redirect(url_for('main.contract_management'))
    return render_template('edit_contract.html', form=f, title="編輯合約", contract=c)


@main.route('/delete_contract/<int:contract_id>', methods=['POST'])
@login_required
def delete_contract(contract_id):
    c=Contract.query.get_or_404(contract_id)
    db.session.delete(c)
    db.session.commit()
    flash('合約已刪除','success')
    return redirect(url_for('main.contract_management'))

# ========== JP 版物料管理 ==========
@main.route('/material_jp_management', methods=['GET'])
@login_required
def material_jp_management():
    page=request.args.get('page',1,int)
    q=MaterialJP.query.filter(MaterialJP.is_deleted==False)
    pag=q.order_by(MaterialJP.updated_date.desc()).paginate(page=page, per_page=100, error_out=False)
    return render_template('material_jp_management.html', materials=pag.items, pagination=pag)

@main.route('/add_material_jp', methods=['POST'])
@login_required
def add_material_jp():
    d=request.get_json()
    m=MaterialJP(
        device_model=d.get('device_model'),
        pid=d.get('pid'),
        pn=d.get('pn'),
        status=d.get('status'),
        keeper=d.get('keeper'),
        remark=d.get('remark'),
        sim_info=d.get('sim_info'),
        netsuite_dept=d.get('netsuite_dept'),
        eis_program=d.get('eis_program'),
        eg_account=d.get('eg_account'),
        location=d.get('location'),
        firmware=d.get('firmware'),
        connection_method=d.get('connection_method'),
        note=d.get('note'),
        updated_by=current_user.email,
        updated_date=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        is_deleted=False,
        pickup_person=d.get('pickup_person'),
        pickup_order_number=d.get('pickup_order_number')
    )
    try:
        db.session.add(m)
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)),400

@main.route('/edit_material_jp/<int:material_id>', methods=['POST'])
@login_required
def edit_material_jp(material_id):
    mat=MaterialJP.query.get_or_404(material_id)
    d=request.get_json() or {}
    for k in ['device_model','pid','pn','status','keeper','remark','sim_info','netsuite_dept',
              'eis_program','eg_account','location','firmware','connection_method','note',
              'pickup_person','pickup_order_number']:
        if k in d: setattr(mat,k,d[k])
    mat.updated_by=current_user.email
    mat.updated_date=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    try:
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)),400

@main.route('/delete_material_jp/<int:material_id>', methods=['POST'])
@login_required
def delete_material_jp(material_id):
    mat=MaterialJP.query.get_or_404(material_id)
    try:
        mat.is_deleted=True
        mat.updated_by=current_user.email
        mat.updated_date=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)),400

@main.route('/import_csv_jp', methods=['POST'])
@login_required
def import_csv_jp():
    if 'csv_file' not in request.files:
        return jsonify(success=False, error='No file in request'),400
    file=request.files['csv_file']
    if file.filename=='':
        return jsonify(success=False, error='No selected file'),400
    try:
        import io,csv
        raw=file.read()
        file.stream.seek(0)
        stream=io.StringIO(raw.decode("utf-8", errors="replace"))
        csv_reader=csv.DictReader(stream)
        row_count=0
        for idx,row in enumerate(csv_reader,start=1):
            if not any(str(v).strip() for v in row.values() if v):
                continue
            row_count+=1
            m=MaterialJP(
                device_model=row.get('Device Model',''),
                pid=row.get('PI/MAC Address','').strip(),
                pn=row.get('P/N',''),
                status=row.get('狀態',''),
                keeper=row.get('保管人',''),
                remark=row.get('Remark',''),
                sim_info=row.get('SIM卡資訊',''),
                netsuite_dept=row.get('NetSuite Dept',''),
                eis_program=row.get('EIS Program',''),
                eg_account=row.get('EG+ Account',''),
                location=row.get('Location',''),
                firmware=row.get('Firmware',''),
                connection_method=row.get('連網方式',''),
                note=row.get('NOTE',''),
                pickup_person=row.get('領料人',''),
                pickup_order_number=row.get('領料單號',''),
                updated_by=current_user.email,
                updated_date=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                is_deleted=False
            )
            db.session.add(m)
        db.session.commit()
        return jsonify(success=True, rows=row_count)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)),400

# =========================
# SIM 卡狀態 新增/編輯 頁面
# =========================
@main.route('/simcard_status', methods=['GET', 'POST'])
@login_required
def simcard_status():
    # 只保留三種狀態
    allowed_statuses = ['active', 'suspend', 'dead']
    
    if request.method == 'POST':
        record_id    = request.form.get('record_id')
        pid          = request.form.get('pid', '').strip()
        iccid        = request.form.get('iccid', '').strip()
        status_value = request.form.get('status', '').strip()
        group        = request.form.get('group', '').strip() or ""

        if status_value not in allowed_statuses:
            flash("狀態選項無效", "danger")
            return redirect(url_for('main.simcard_status'))

        # 新增或編輯前先紀錄
        if record_id:
            record = SimCardStatus.query.get_or_404(record_id)
            db.session.add(SimCardEditRecord(
                sim_card_status_id=record.id,
                original_pid=record.pid or "",
                original_iccid=record.iccid or "",
                original_status=record.status or "",
                original_group=record.group or "",
                updated_by=current_user.username,
                updated_at=datetime.utcnow()
            ))
            record.pid    = pid or record.pid
            record.iccid  = iccid or record.iccid
            record.status = status_value
            record.group  = group or record.group
        else:
            if not pid and not iccid:
                flash("請至少填入 PID 或 ICCID", "danger")
                return redirect(url_for('main.simcard_status'))
            record = SimCardStatus(
                pid=pid,
                iccid=iccid,
                status=status_value,
                group=group
            )
            db.session.add(record)
            db.session.flush()
            db.session.add(SimCardEditRecord(
                sim_card_status_id=record.id,
                original_pid="",
                original_iccid="",
                original_status="",
                original_group="",
                updated_by=current_user.username,
                updated_at=datetime.utcnow()
            ))

        # 呼叫 IIJ API
        if status_value == 'active':
            resp = iij_activate(record.iccid or record.pid)
        elif status_value == 'suspend':
            resp = iij_suspend(record.iccid or record.pid)
        else:
            resp = iij_cancel(record.iccid or record.pid)

        # 處理 resp 可能為 dict 或 Response
        if isinstance(resp, dict):
            body = resp
            status_code = None
        else:
            try:
                body = resp.json()
            except Exception:
                db.session.rollback()
                flash(f"IIJ 回應非 JSON：{resp.text}", "danger")
                return redirect(url_for('main.simcard_status'))
            status_code = resp.status_code

        # 檢查 HTTP 200 且 code == 200
        if status_code != 200 or int(body.get("code", 0)) != 200:
            db.session.rollback()
            flash(f"IIJ API 呼叫失敗：HTTP {status_code}，code={body.get('code')}，msg={body.get('message')}", "danger")
            return redirect(url_for('main.simcard_status'))

        # 最後 commit
        try:
            db.session.commit()
            flash(f"SIM 卡狀態已{'更新' if record_id else '新增'}", "success")
        except Exception as e:
            db.session.rollback()
            flash("資料庫儲存失敗：" + str(e), "danger")

        return redirect(url_for('main.simcard_status'))

    # GET：篩選 & 顯示
    query = SimCardStatus.query
    pid_filter    = request.args.get('pid', '').strip()
    iccid_filter  = request.args.get('iccid', '').strip()
    status_filter = request.args.get('status','').strip()
    group_filter  = request.args.get('group','').strip()
    if pid_filter:
        query = query.filter(SimCardStatus.pid.ilike(f"%{pid_filter}%"))
    if iccid_filter:
        query = query.filter(SimCardStatus.iccid.ilike(f"%{iccid_filter}%"))
    if status_filter:
        query = query.filter(SimCardStatus.status == status_filter)
    if group_filter:
        query = query.filter(SimCardStatus.group.ilike(f"%{group_filter}%"))
    
    page       = request.args.get('page', 1, type=int)
    pagination = query.paginate(page=page, per_page=10, error_out=False)
    statuses   = pagination.items

    edit_records_map = {
        rec.id: SimCardEditRecord.query
                    .filter_by(sim_card_status_id=rec.id)
                    .order_by(SimCardEditRecord.updated_at.desc())
                    .all()
        for rec in statuses
    }
    record_to_edit = None
    if request.args.get('edit_id'):
        record_to_edit = SimCardStatus.query.get(request.args.get('edit_id'))

    return render_template(
        "simcard_status.html",
        statuses=statuses,
        allowed_statuses=allowed_statuses,
        edit_records_map=edit_records_map,
        record_to_edit=record_to_edit,
        pagination=pagination
    )

@main.route('/delete_simcard_status/<int:status_id>', methods=['POST'])
@login_required
def delete_simcard_status(status_id):
    record = SimCardStatus.query.get_or_404(status_id)
    try:
        delete_rec = SimCardEditRecord(
            sim_card_status_id=record.id,
            original_pid=record.pid or "",
            original_iccid=record.iccid or "",
            original_status=record.status or "",
            original_group=record.group or "",
            updated_by=current_user.username,
            updated_at=datetime.utcnow()
        )
        db.session.add(delete_rec)
        
        dummy = SimCardStatus.query.filter_by(pid='dummy').first()
        if not dummy:
            dummy = SimCardStatus(pid='dummy', iccid='dummy', status='dummy', group='dummy')
            db.session.add(dummy)
            db.session.commit()  # 取得 dummy.id
        SimCardEditRecord.query.filter_by(sim_card_status_id=record.id)\
                               .update({"sim_card_status_id": dummy.id})
        
        db.session.delete(record)
        db.session.commit()
        flash("SIM 卡狀態已刪除，相關編輯紀錄已保留", "success")
    except Exception as e:
        db.session.rollback()
        flash("刪除失敗：" + str(e), "danger")
    return redirect(url_for('main.simcard_status'))


@main.route('/import_simcard_csv', methods=['POST'])
@login_required
def import_simcard_csv():
    if 'csv_file' not in request.files:
        flash("沒有上傳檔案", "danger")
        return redirect(url_for("main.simcard_status"))
    file = request.files['csv_file']
    if not file.filename:
        flash("沒有選擇檔案", "danger")
        return redirect(url_for("main.simcard_status"))
    
    try:
        raw = file.read()
        file.stream.seek(0)
        stream = io.StringIO(raw.decode("utf-8", errors="replace"))
        reader = csv.DictReader(stream)
        row_count = 0
        
        for row in reader:
            orig_pid   = (row.get("original_PID") or "").strip()
            orig_iccid = (row.get("original_ICCID") or "").strip()
            new_pid    = (row.get("new_PID") or "").strip()
            new_iccid  = (row.get("new_ICCID") or "").strip()
            status_val = (row.get("status") or "").strip()
            group      = (row.get("group") or "").strip() or ""

            if status_val not in ['active','suspend','dead'] or not (new_pid or new_iccid):
                continue

            record = None
            if orig_pid:
                record = SimCardStatus.query.filter_by(pid=orig_pid).first()
            if not record and orig_iccid:
                record = SimCardStatus.query.filter_by(iccid=orig_iccid).first()

            if record:
                edit_rec = SimCardEditRecord(
                    sim_card_status_id=record.id,
                    original_pid=record.pid or "",
                    original_iccid=record.iccid or "",
                    original_status=record.status or "",
                    original_group=record.group or "",
                    updated_by=current_user.username,
                    updated_at=datetime.utcnow()
                )
                db.session.add(edit_rec)

                record.pid    = new_pid or record.pid
                record.iccid  = new_iccid or record.iccid
                record.status = status_val
                record.group  = group

                if status_val == 'active':
                    iij_activate(record.iccid or record.pid)
                elif status_val == 'suspend':
                    iij_suspend(record.iccid or record.pid)
                else:
                    iij_cancel(record.iccid or record.pid)
            else:
                new_rec = SimCardStatus(
                    pid=new_pid,
                    iccid=new_iccid,
                    status=status_val,
                    group=group
                )
                db.session.add(new_rec)
                db.session.flush()

                edit_rec = SimCardEditRecord(
                    sim_card_status_id=new_rec.id,
                    original_pid="",
                    original_iccid="",
                    original_status="",
                    original_group="",
                    updated_by=current_user.username,
                    updated_at=datetime.utcnow()
                )
                db.session.add(edit_rec)

                if status_val == 'active':
                    iij_activate(new_rec.iccid or new_rec.pid)
                elif status_val == 'suspend':
                    iij_suspend(new_rec.iccid or new_rec.pid)
                else:
                    iij_cancel(new_rec.iccid or new_rec.pid)

            row_count += 1

        db.session.commit()
        flash(f"匯入完成，共處理 {row_count} 筆資料", "success")
    except Exception as e:
        db.session.rollback()
        flash("匯入失敗：" + str(e), "danger")

    return redirect(url_for("main.simcard_status"))


@main.route('/simcard_edit_records', methods=['GET'])
@login_required
def simcard_edit_records():
    pid_filter   = request.args.get('pid', '').strip()
    iccid_filter = request.args.get('iccid', '').strip()
    q = SimCardEditRecord.query
    if pid_filter:
        q = q.filter(SimCardEditRecord.original_pid.ilike(f"%{pid_filter}%"))
    if iccid_filter:
        q = q.filter(SimCardEditRecord.original_iccid.ilike(f"%{iccid_filter}%"))
    records = q.order_by(SimCardEditRecord.updated_at.desc()).all()
    return render_template(
        "simcard_edit_records.html",
        records=records,
        pid_filter=pid_filter,
        iccid_filter=iccid_filter
    )


@main.route('/edit_simcard_status/<int:record_id>', methods=['GET', 'POST'])
@login_required
def edit_simcard_status(record_id):
    record = SimCardStatus.query.get_or_404(record_id)
    allowed_statuses = ['active', 'suspend', 'dead']
    
    if request.method == 'POST':
        new_pid    = request.form.get('pid', '').strip() or record.pid
        new_iccid  = request.form.get('iccid', '').strip() or record.iccid
        new_status = request.form.get('status', '').strip()
        new_group  = request.form.get('group', '').strip() or record.group

        if new_status not in allowed_statuses:
            flash("狀態選項無效", "danger")
            return redirect(url_for('main.edit_simcard_status', record_id=record_id))

        db.session.add(SimCardEditRecord(
            sim_card_status_id=record.id,
            original_pid=record.pid or "",
            original_iccid=record.iccid or "",
            original_status=record.status or "",
            original_group=record.group or "",
            updated_by=current_user.username,
            updated_at=datetime.utcnow()
        ))

        record.pid    = new_pid
        record.iccid  = new_iccid
        record.status = new_status
        record.group  = new_group

        if new_status == 'active':
            resp = iij_activate(record.iccid or record.pid)
        elif new_status == 'suspend':
            resp = iij_suspend(record.iccid or record.pid)
        else:
            resp = iij_cancel(record.iccid or record.pid)

        if isinstance(resp, dict):
            body = resp
            status_code = None
        else:
            try:
                body = resp.json()
            except Exception:
                db.session.rollback()
                flash(f"IIJ 回應非 JSON：{resp.text}", "danger")
                return redirect(url_for('main.edit_simcard_status', record_id=record_id))
            status_code = resp.status_code

        if status_code != 200 or int(body.get("code", 0)) != 200:
            db.session.rollback()
            flash(f"IIJ API 呼叫失敗：HTTP {status_code}，code={body.get('code')}，msg={body.get('message')}", "danger")
            return redirect(url_for('main.edit_simcard_status', record_id=record_id))

        try:
            db.session.commit()
            flash("SIM 卡狀態已更新", "success")
            return redirect(url_for('main.simcard_status'))
        except Exception as e:
            db.session.rollback()
            flash("更新失敗：" + str(e), "danger")
            return redirect(url_for('main.edit_simcard_status', record_id=record_id))

    return render_template("edit_simcard_status.html",
                           record=record,
                           allowed_statuses=allowed_statuses)


@main.route('/export_simcard_csv', methods=['GET'])
@login_required
def export_simcard_csv():
    pid_filter    = request.args.get('pid', '').strip()
    iccid_filter  = request.args.get('iccid', '').strip()
    status_filter = request.args.get('status', '').strip()
    group_filter  = request.args.get('group', '').strip()

    query = SimCardStatus.query.filter(SimCardStatus.pid != "dummy")
    if pid_filter:
        query = query.filter(SimCardStatus.pid.ilike(f"%{pid_filter}%"))
    if iccid_filter:
        query = query.filter(SimCardStatus.iccid.ilike(f"%{iccid_filter}%"))
    if status_filter:
        query = query.filter(SimCardStatus.status == status_filter)
    if group_filter:
        query = query.filter(SimCardStatus.group.ilike(f"%{group_filter}%"))
    
    records = query.all()

    status_counts = {}
    for rec in records:
        st = rec.status or "unknown"
        status_counts[st] = status_counts.get(st, 0) + 1

    total_amount = (status_counts.get("active", 0) + status_counts.get("resume", 0)) * 400 \
                   + status_counts.get("suspend", 0) * 200

    si = io.StringIO()
    cw = csv.writer(si)
    
    cw.writerow(["統計資訊"])
    cw.writerow(["狀態", "數量"])
    for st in ["active", "cancel", "suspend", "resume", "skipped"]:
        cw.writerow([st, status_counts.get(st, 0)])
    cw.writerow(["總計金額", total_amount])
    cw.writerow([])
    cw.writerow(["ID", "PID", "ICCID", "Status", "Group"])
    for rec in records:
        cw.writerow([rec.id, rec.pid, rec.iccid, rec.status, rec.group])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=simcard_status_export.csv"
    output.headers["Content-Type"] = "text/csv"
    return output


@main.route('/site_detail/<int:spot_id>')
@login_required
def site_detail(spot_id):
    spot = Spot.query.get_or_404(spot_id)

    # 取得站點的客戶名稱
    client_name = spot.client.name if spot.client else "無"

    # 取得 GW 列表
    gw_list = [gw for gw in spot.gw_list if gw]

    # 計算相關記錄數量
    maintenance_count = MaintenanceRecord.query.filter_by(location=spot.site_name).count()
    travel_count = TravelRecord.query.filter_by(location=spot.site_name).count()

    return render_template('site_detail.html', spot=spot, client_name=client_name,
                           gw_list=gw_list, maintenance_count=maintenance_count,
                           travel_count=travel_count)

@main.route('/key_application', methods=['GET'])
@login_required
def key_application():
    return render_template("key_application.html")

# ========== 台電電表資料查詢 ==========
@main.route('/taipower/search', methods=['GET'])
@login_required
def search_taipower_records():
    """
    根據 full_meter_number 查詢 TaipowerExcelRecord，
    支援空格、英文逗號、中文逗號、頓號分隔多筆查詢
    """
    query = request.args.get('full_meter_number', '')

    # 支援多種分隔符：空白 (\s)、英文逗號 ','、中文逗號 '，'、頓號 '、'
    parts = re.split(r'[\s,，、]+', query)
    numbers = [p.strip() for p in parts if p.strip()]

    results = []
    if numbers:
        results = TaipowerExcelRecord.query.filter(
            TaipowerExcelRecord.full_meter_number.in_(numbers)
        ).all()

    return render_template('search_taipower.html', results=results)


@main.route('/nd/taipowermeters', methods=['POST'])
@login_required
def create_taipowermeter_by_nd():
    """
    1. 從前端接收 JSON payload
    2. 轉發給 Taipower 官方 API（帶 ND token）
    3. 解析回傳的 data.hemsNo，並寫入本地 taipowermeter_applies (submitted_by='ND')
    4. 把 Taipower 回應原封不動回傳給前端
    """
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "無效的 JSON"}), 400

    # 從 config 抓 ND token，或硬寫亦可
    nd_token = current_app.config.get('ND_TOKEN', 'hemstw-i-am-hemstw')
    tp_api_url = "https://api-eg3.nextdrive.io/api/v1/taipowermeters"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {nd_token}"
    }

    try:
        tp_resp = requests.post(tp_api_url, headers=headers, json=payload, timeout=10)
    except requests.RequestException as e:
        current_app.logger.error(f"[ND Proxy] 呼叫 Taipower API 失敗: {e}")
        return jsonify({"error": "無法連線到 Taipower API"}), 502

    tp_status = tp_resp.status_code
    tp_text = tp_resp.text

    # 如果外部 API 回錯，就直接把錯誤回傳，不寫資料庫
    if tp_status != 200:
        return (tp_text, tp_status, {"Content-Type": "application/json"})

    # 解析 JSON 並取出 data.hemsNo
    try:
        tp_json = tp_resp.json()
    except ValueError:
        return jsonify({"error": "無法解析 Taipower 回應"}), 500

    hems_no = tp_json.get("data", {}).get("hemsNo")
    if not hems_no:
        return jsonify({"error": "回應缺少 data.hemsNo"}), 500

    # 把 hems_no 寫到本地資料庫 (submitted_by='ND')
    try:
        existing = TaipowermeterApply.query.filter_by(hems_no=hems_no).first()
        if not existing:
            new_apply = TaipowermeterApply(hems_no=hems_no, submitted_by="ND")
            db.session.add(new_apply)
            db.session.commit()
    except Exception as db_err:
        current_app.logger.error(f"[ND Proxy] 無法寫入 TaipowermeterApply: {db_err}")
        # 如果寫入失敗，也可以選擇忽略，僅記 log
        # db.session.rollback()

    # 回傳外部 API 的原始回應
    return (tp_text, tp_status, {"Content-Type": "application/json"})

@main.route('/confluence', methods=['GET'])
@login_required
def confluence_overview():
    """
    Confluence 子頁面總覽 + 新增按鈕
    """
    client   = current_app.extensions['confluence']
    parent_id = current_app.config['CONFLUENCE']['PARENT_ID']

    try:
        children = client.get_child_pages(parent_id)
    except Exception as e:
        flash(f'取得子頁面失敗：{e}', 'danger')
        children = []

    return render_template('confluence_overview.html',
                           children=children,
                           base_url=client.base_url)

def get_account_id(username):
    """
    1) 如果跟目前 Confluence 登入的使用者相同，就呼叫 /user/current
    2) 否則呼叫 /user/search?query=，再精確比對 displayName
    3) 仍找不到就回 None
    """
    client = current_app.extensions['confluence']
    # 1) 自己
    # 注意：需要把 ConfluenceClient 的 auth 也傳給這個 requests
    r0 = requests.get(
        f"{client.base_url}/rest/api/user/current",
        auth=client.auth,
        headers={"Content-Type":"application/json"},
        timeout=5
    )
    if r0.ok and r0.json().get("displayName") == username:
        return r0.json().get("accountId")

    # 2) 搜尋並精確比對
    r1 = requests.get(
        f"{client.base_url}/rest/api/user/search?query={username}",
        auth=client.auth,
        headers={"Content-Type":"application/json"},
        timeout=5
    )
    if r1.ok:
        for u in r1.json():
            if u.get("displayName") == username:
                return u.get("accountId")
        # fallback：直接回第一筆（或你要的邏輯）
        if r1.json():
            return r1.json()[0].get("accountId")
    return None

def make_mention_by_id(account_id, display_name):
    """
    用 ri:user account-id 建立 mention
    """
    return (
      '<ac:structured-macro ac:name="mention">'
        f'<ac:parameter ac:name="user">{display_name}</ac:parameter>'
        f'<ac:plain-text-body><![CDATA[@{display_name}]]></ac:plain-text-body>'
        f'<ac:link><ri:user ri:account-id="{account_id}" /></ac:link>'
      '</ac:structured-macro>'
    )

def make_mention(username):
    """
    用 ri:user account-id 建立 mention，
    找不到 account-id 就回空字串。
    """
    if not username:
        return ""
    account_id = get_account_id(username)
    if not account_id:
        return ""
    # 正式 mention 只用 <ac:link>/<ri:user>
    return f'<ac:link><ri:user ri:account-id="{account_id}" /></ac:link>'

@main.route('/confluence/create', methods=['GET','POST'])
def create_confluence_page():
    if request.method == 'POST':
        # 1) 組 title
        status = request.form.get('status', 'TMP')
        now_ts = datetime.now().strftime('%y%m%d%H%M')
        title  = f"{status}{now_ts}"

        # 2) 讀表單欄位 (注意 name 要和前端一致)
        folder_link    = request.form.get('folder_link', '').strip()
        objects        = request.form.getlist('purpose_object[]')
        targets        = request.form.getlist('purpose_target[]')
        svc_content    = request.form.get('service_content', '').strip()
        proj_schedule  = request.form.get('project_schedule', '').strip()
        svc_time       = request.form.get('service_time', '').strip()
        sales_name     = request.form.get('sales', '').strip().lstrip('@')
        pjo_name       = request.form.get('pjo',   '').strip().lstrip('@')

        # 3) 產生 mention 標記
        sales_markup = make_mention(sales_name)
        pjo_markup   = make_mention(pjo_name)

        # 4) 動態拼「目的」表格列，若對象一樣就合併儲存格
        rows_html = ""

        # 先算出每個 o 出現了幾次
        counts = {}
        for o in objects:
            key = o.strip()
            if key:
                counts[key] = counts.get(key, 0) + 1

        prev_o = None
        for o, t in zip(objects, targets):
            o_str = o.strip()
            t_str = t.strip()
            # 都空就跳過
            if not (o_str or t_str):
                continue

            # 碰到新的 o，才輸出帶 rowspan 的儲存格
            if o_str and o_str != prev_o:
                rowspan = counts.get(o_str, 1)
                rows_html += (
                    f"<tr>"
                    f"<td rowspan='{rowspan}'>{o_str}</td>"
                    f"<td>{t_str}</td>"
                    f"</tr>"
                )
                prev_o = o_str
            else:
                # 同一個 o，直接輸出第二欄
                rows_html += f"<tr><td>{t_str}</td></tr>"

        # 5) 處理專案資料夾連結
        if folder_link:
            folder_html = (
                '<p><strong>專案資料夾：</strong> '
                f'<a href="{folder_link}" target="_blank">{folder_link}</a>'
                '</p>'
            )
        else:
            folder_html = ''

        # 6) 組 body (Storage)
        html_body = f"""
{folder_html}

<p><strong>目的</strong></p>
<table>
  <thead><tr><th>對象</th><th>關鍵目標</th></tr></thead>
  <tbody>
    {rows_html}
  </tbody>
</table>

<p><strong>服務內容：</strong> {svc_content}</p>
<p><strong>專案時程：</strong> {proj_schedule}</p>
<p><strong>服務時間：</strong> {svc_time}</p>

<p><strong>業務：</strong> {sales_markup}</p>
<p><strong>PJO：</strong> {pjo_markup}</p>
"""

        # 7) 呼叫 ConfluenceClient 建頁
        client = current_app.extensions['confluence']
        try:
            result = client.create_page(title, html_body)
            url    = client.base_url + result['_links']['webui']
            flash(f'✅ 已建立頁面：<a href="{url}" target="_blank">{title}</a>', 'success')
            return redirect(url_for('main.confluence_overview'))

        except Exception as e:
            flash(f'❌ 建立失敗：{e}', 'danger')
            # 回顯原始輸入
            return render_template(
                'create_confluence.html',
                status=status,
                folder_link=folder_link,
                purpose_object=objects,
                purpose_target=targets,
                service_content=svc_content,
                project_schedule=proj_schedule,
                service_time=svc_time,
                sales=sales_name,
                pjo=pjo_name
            )

    # GET: 傳預設值
    return render_template(
        'create_confluence.html',
        status='TMP',
        folder_link='',
        purpose_object=['',''],
        purpose_target=['',''],
        service_content='',
        project_schedule='',
        service_time='',
        sales='',
        pjo=''
    )

@main.route('/confluence/delete/<string:page_id>', methods=['POST'])
@login_required
def delete_confluence_page(page_id):
    client = current_app.extensions['confluence']
    try:
        client.delete_page(page_id)
        flash('✅ 子頁面已刪除', 'success')
    except Exception as e:
        flash(f'❌ 刪除失敗：{e}', 'danger')
    return redirect(url_for('main.confluence_overview'))