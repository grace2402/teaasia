import os
import re
import importlib
from io import BytesIO
from datetime import datetime
from flask import Flask
from authlib.integrations.flask_client import OAuth
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
from flask_mail import Mail
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
from flask_uploads import UploadSet, IMAGES
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_sse import sse
from flask_apscheduler import APScheduler
from pytz import timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime
from config import config
import requests
from .utils.confluence_client import ConfluenceClient

# 初始化各個擴充套件
bootstrap = Bootstrap()
mail = Mail()
moment = Moment()
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.session_protection = 'None'
login_manager.login_view = 'auth.login'
images = UploadSet('images', IMAGES)
csrf = CSRFProtect()
migrate = Migrate()
scheduler = APScheduler()

# 預先匯入模型
from .models import SimCardStatus, SimCardEditRecord


def decode_mime_words(s: str) -> str:
    decoded = ""
    for word, charset in decode_header(s):
        if isinstance(word, bytes):
            decoded += word.decode(charset or 'utf-8', errors='ignore')
        else:
            decoded += word
    return decoded


def fetch_latest_taipower_excel() -> BytesIO or None:
    """
    抓取所有未讀台電金鑰郵件，標記為已讀並選擇最新一封，
    下載並解密 Excel 附件，回傳 BytesIO；若無符合條件，回 None。
    """
    mail_conn = imaplib.IMAP4_SSL('imap.gmail.com')
    mail_conn.login(EMAIL, PASSWORD)
    mail_conn.select('inbox')
    status, msgs = mail_conn.search(None, 'X-GM-RAW', '"from:taipower.com.tw is:unread"')
    if status != 'OK':
        scheduler.app.logger.error(f"搜尋信件失敗: status={status}")
        mail_conn.logout()
        return None

    uids = msgs[0].split()
    scheduler.app.logger.info(f"搜尋到 {len(uids)} 封未讀台電郵件")
    if not uids:
        scheduler.app.logger.info('沒有未讀台電金鑰郵件，跳過')
        mail_conn.logout()
        return None

    # 標記所有為已讀，準備挑最新
    for uid in uids:
        mail_conn.store(uid, '+FLAGS', '\\Seen')

    date_uid_list = []
    for uid in uids:
        st, fetch_data = mail_conn.fetch(uid, '(INTERNALDATE)')
        if st != 'OK':
            continue
        raw = ''
        for part in fetch_data:
            if isinstance(part, bytes):
                raw += part.decode('utf-8', errors='ignore')
            elif isinstance(part, tuple) and isinstance(part[1], (bytes, bytearray)):
                raw += part[1].decode('utf-8', errors='ignore')
        m = re.search(r'INTERNALDATE "([^"]+)"', raw)
        if m:
            dt = parsedate_to_datetime(m.group(1))
            date_uid_list.append((uid, dt))

    mail_conn.logout()
    if not date_uid_list:
        scheduler.app.logger.info('沒有可挑選的 INTERNALDATE，跳過')
        return None

    latest_uid, _ = max(date_uid_list, key=lambda x: x[1])

    # 重新抓取最新郵件
    mail_conn = imaplib.IMAP4_SSL('imap.gmail.com')
    mail_conn.login(EMAIL, PASSWORD)
    mail_conn.select('inbox')
    _, data = mail_conn.fetch(latest_uid, '(RFC822)')
    import email as std_email
    msg = std_email.message_from_bytes(data[0][1])
    mail_conn.store(latest_uid, '+FLAGS', '\\Seen')
    mail_conn.logout()

    subject = decode_mime_words(msg.get('Subject', ''))
    scheduler.app.logger.info(f"郵件主旨: {subject}")
    if '金鑰' not in subject:
        scheduler.app.logger.info('主旨不含關鍵字「金鑰」，跳過')
        return None

    pw = None
    attachment = None
    for part in msg.walk():
        if part.get_content_type() == 'text/plain' and pw is None:
            body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
            m = re.search(r'密碼[：:]\s*([^\s\n]+)', body)
            if m:
                pw = m.group(1)
                scheduler.app.logger.info(f"擷取到解密密碼: {pw}")
        disp = part.get('Content-Disposition')
        if disp and part.get_filename():
            fn = decode_mime_words(part.get_filename())
            if fn.lower().endswith(('.xls', '.xlsx')):
                attachment = part.get_payload(decode=True)
                scheduler.app.logger.info(f"擷取到附件: {fn}")

    if not attachment:
        scheduler.app.logger.warning('缺少附件，無法解密')
        return None
    if not pw:
        # 缺少密碼時使用預設密碼
        pw = 'nextdrive11402'
        scheduler.app.logger.warning(f'缺少解密密碼，改用預設密碼: {pw}')

    bio = BytesIO()
    office_file = msoffcrypto.OfficeFile(BytesIO(attachment))
    office_file.load_key(password=pw)
    office_file.decrypt(bio)
    bio.seek(0)
    scheduler.app.logger.info('Excel 附件解密完成，回傳 BytesIO')
    return bio


def update_simcard_status_on_20th():
    """
    每月 20 號 16:10 (Asia/Tokyo)：產出上月 SIM 卡結算報表並透過 Google Chat 通知。
    計費邏輯：若上月任一天為 active，則整月依 active 費率計算。
    """
    import os
    import csv
    from datetime import datetime
    from webhook import send_message_to_google_chat
    from .models import SimCardStatus, SimCardEditRecord  # 根據專案實際路徑調整

    with scheduler.app.app_context():
        # 1. 計算上月起訖（UTC）
        now = datetime.utcnow()
        year, month = now.year, now.month
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1
        period_start = datetime(prev_year, prev_month, 1)
        period_end   = datetime(year, month, 1)

        # 2. 撈出所有 SIM 主檔
        records = SimCardStatus.query.filter(SimCardStatus.pid != 'dummy').all()
        groups = {}
        for r in records:
            # 查詢上月編輯紀錄，判斷是否曾 active
            history = SimCardEditRecord.query.filter(
                SimCardEditRecord.sim_card_status_id == r.id,
                SimCardEditRecord.updated_at >= period_start,
                SimCardEditRecord.updated_at <  period_end
            ).all()
            was_active = any(rec.original_status == 'active' for rec in history) or r.status == 'active'
            effective_status = 'active' if was_active else r.status
            groups.setdefault(r.group or 'No Group', []).append(effective_status)

        # 3. 組成報表文字
        lines = [f"SIM 卡結算報表：{period_start.strftime('%Y/%m')}"]
        for group_name, statuses in groups.items():
            cnt = {'active': 0, 'suspend': 0, 'dead': 0}
            for st in statuses:
                if st in cnt:
                    cnt[st] += 1
            total = cnt['active'] * 400 + cnt['suspend'] * 200
            lines.append(f"【群組：{group_name}】")
            lines.extend([f"  {k} : {v}" for k, v in cnt.items()])
            lines.append(f"  總計金額: {total}")
            lines.append("")

        # 4. 匯出 CSV
        export_folder = os.path.join(os.getcwd(), 'exports')
        os.makedirs(export_folder, exist_ok=True)
        filename = f"sim_card_billing_{period_start.strftime('%Y%m')}.csv"
        filepath = os.path.join(export_folder, filename)
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for line in lines:
                writer.writerow([line])

        # 5. 發送 Google Chat 通知
        webhook_url = (
            'https://chat.googleapis.com/v1/spaces/AAAA_3dZ2vU/messages?'
            'key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&'
            'token=htISliwluLmxYmbYhaR7t8BYMEokeMzUaTaFEbXo69Q'
        )
        msg_text = '\n'.join(lines) + f'\nCSV 檔案：{filepath}'
        send_message_to_google_chat(webhook_url, msg_text)


def import_taipower_excel_records():
    """
    每日 16:10 (Asia/Taipei)：下載並解密台電 Excel，若 TPC_number 存在則覆蓋，否則新增，
    並根據 TaipowermeterApply 記錄呼叫第三方 API。
    """
    scheduler.app.logger.info('【import_taipower_excel】開始執行')
    TP_KEY_UPDATE_TOKEN = 'hemstw-i-am-hemstw'

    with scheduler.app.app_context():
        bio = fetch_latest_taipower_excel()
        if not bio:
            scheduler.app.logger.info('fetch_latest_taipower_excel() 回傳 None，結束本次排程')
            return
        scheduler.app.logger.info('取得 Excel 檔案，開始解析內容')

        wb = openpyxl.load_workbook(bio, data_only=True)
        sheet = wb.active
        rows = list(sheet.iter_rows(values_only=True))
        if len(rows) < 2:
            scheduler.app.logger.info('Excel 無資料行，跳過')
            return

        headers = list(rows[0])
        if len(headers) > 8 and not headers[8]:
            headers[8] = '完整表號'
        valid_indices = [i for i, h in enumerate(headers) if h]
        keys = [headers[i] for i in valid_indices]

        for row in rows[1:]:
            data_map = {keys[j]: row[i] for j, i in enumerate(valid_indices)}
            tpc = str(data_map.get('電號') or '').strip()
            if not tpc:
                continue

            rec = TaipowerExcelRecord.query.filter_by(TPC_number=tpc).first()
            attrs = {
                'username': str(data_map.get('戶名') or ''),
                'case_number': str(data_map.get('案件受理號碼') or ''),
                'guk_h': str(data_map.get('GUK_H') or ''),
                'ak_h': str(data_map.get('AK_H') or ''),
                'meter_brand': str(data_map.get('電表品牌') or ''),
                'meter_number': str(data_map.get('表號') or ''),
                'multiplier': str(data_map.get('倍數') or ''),
                'full_meter_number': str(data_map.get('完整表號') or ''),
                'request_date': str(data_map.get('申請日期') or '')
            }

            if rec:
                for k, v in attrs.items():
                    setattr(rec, k, v)
                rec.updated_at = datetime.utcnow()
                db.session.add(rec)
            else:
                new_rec = TaipowerExcelRecord(
                    TPC_number=tpc,
                    username=attrs['username'],
                    case_number=attrs['case_number'],
                    guk_h=attrs['guk_h'],
                    ak_h=attrs['ak_h'],
                    meter_brand=attrs['meter_brand'],
                    meter_number=attrs['meter_number'],
                    multiplier=attrs['multiplier'],
                    full_meter_number=attrs['full_meter_number'],
                    request_date=attrs['request_date']
                )
                db.session.add(new_rec)

                apply_rec = TaipowermeterApply.query.filter_by(tpc_number=tpc).order_by(
                    TaipowermeterApply.created_at.desc()
                ).first()
                if apply_rec:
                    url = f'https://api-eg3.nextdrive.io/api/v1/taipowermeters/{apply_rec.hems_no}/keys'
                    payload = {
                        'guk_h': attrs['guk_h'],
                        'ak_h': attrs['ak_h'],
                        'meterMultiplier': attrs['multiplier']
                    }
                    headers = {
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {TP_KEY_UPDATE_TOKEN}'
                    }
                    try:
                        resp = requests.put(url, headers=headers, json=payload, timeout=10)
                        if resp.status_code not in (200, 201):
                            scheduler.app.logger.error(f"第三方 API PUT {url} 回傳 {resp.status_code}: {resp.text}")
                        else:
                            scheduler.app.logger.info(f"第三方 API 成功 PUT {url} (tpc={tpc})")
                    except Exception as e:
                        scheduler.app.logger.error(f"第三方 API 呼叫失敗: {e}")
                else:
                    scheduler.app.logger.warning(f"tpc={tpc} 在 TaipowermeterApply 中無對應紀錄，跳過")

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            scheduler.app.logger.error(f"import_taipower_excel commit 失敗: {e}")


def create_jobs(app):
    # GW 狀態自動檢查排程 (每5分鐘)
    from app.main.gw_monitor import check_all_spots as _check_all_spots
    scheduler.add_job(
        id='check_gw_status_job',
        func=_check_all_spots,
        trigger='interval',
        minutes=5,
        replace_existing=True
    )

    # SIM 卡月度排程 (每月 9 號 16:10 Asia/Tokyo)
    scheduler.add_job(
        id='update_simcard_status_job',
        func=update_simcard_status_on_20th,
        trigger='cron',
        day=27,
        hour=18,
        minute=50,
        timezone=timezone('Asia/Tokyo'),
        replace_existing=True
    )
    # 台電 Excel 每日排程 (已停用 - Gmail IMAP 連線會卡住)
    # scheduler.add_job(
    #     id='import_taipower_excel_job',
    #     func=import_taipower_excel_records,
    #     trigger='cron',
    #     hour=16,
    #     minute=58,
    #     timezone=timezone('Asia/Taipei'),
    #     replace_existing=True
    # )


def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    app._static_folder = os.path.abspath('static/')

    # 初始化
    bootstrap.init_app(app)
    mail.init_app(app)
    moment.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    confluence = ConfluenceClient(app)

    # Google OAuth (Authlib)
    google_oauth = None
    client_id = os.environ.get('GOOGLE_CLIENT_ID') or app.config.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET') or app.config.get('GOOGLE_CLIENT_SECRET')
    if client_id and client_secret:
        from authlib.integrations.flask_client import OAuth as AuthOAuth
        oauth_obj = AuthOAuth(app)
        try:
            oauth_obj.register(
                name='google',
                client_id=client_id,
                client_secret=client_secret,
                server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
                client_kwargs={'scope': 'openid email profile'}
            )
            google_oauth = oauth_obj
            app.logger.info('Google OAuth initialized.')
        except Exception as e:
            app.logger.error(f'Google OAuth init failed: {e}')

    app.extensions['google_oauth'] = google_oauth
    # 藍圖
    from .main import main as main_bp
    app.register_blueprint(main_bp)
    from .main.views import gw_status_refresh
    csrf.exempt(gw_status_refresh)
    from .auth import auth as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    from .admin import admin as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    from .taipower import taipower_bp
    app.register_blueprint(taipower_bp, url_prefix='/taipowermeters')
    app.extensions["confluence"] = confluence
    
    # SSE blueprint with Redis backend
    app.config['SSE_REDIS_URL'] = app.config.get('REDIS_URL', 'redis://localhost:6379')
    app.register_blueprint(sse, url_prefix='/sse')
    # Notify SSE blueprint
    from .notifysse import notifysse as notifysse_bp
    app.register_blueprint(notifysse_bp)
    
    # 啟動排程
    if not app.config.get('IS_MIGRATION', False) and os.environ.get('IS_MIGRATION', 'false').lower() != 'true':
        scheduler.init_app(app)
        scheduler.start()
        app.logger.info('Scheduler started.')
        create_jobs(app)

    return app
