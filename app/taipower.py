# app/taipower.py
import os
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

# 建立 Blueprint，名稱為 taipower
# 說明：若主程式以 url_prefix='/taipowermeters' 註冊此 Blueprint，
# 那麼 API 1 的最終路徑將為 POST /taipowermeters，
# 而 API 2 則會是 POST /taipowermeters/themsIo/agreeImage
taipower_bp = Blueprint('taipower', __name__)

@taipower_bp.route('', methods=['POST'])
def route_b():
    """
    處理申請 Route B 的 API
    接收 JSON 格式資料，請求範例如下：
    {
        "userName": "John",
        "identity": "A123456789",
        "email": "john@example.com",
        "phone": "0912345678",
        "openDateTime": "2025-04-15T12:00:00Z",
        "tpcNo": "YOUR_TPC_NO_HERE"
    }
    說明：
    - openDateTime 欄位會嘗試解析 ISO8601 格式日期字串
    - tpcNo 為必填欄位，若未提供將回傳錯誤
    """
    data = request.get_json() or {}
    user_name = data.get('userName', '').strip()
    identity = data.get('identity', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    open_date_time_str = data.get('openDateTime', '').strip()
    tpc_no = data.get('tpcNo', '').strip()  # 擷取 tpcNo 欄位

    if not tpc_no:
        return jsonify({"error": "tpcNo 欄位是必填的"}), 400

    open_date_time = None
    if open_date_time_str:
        try:
            # 將 ISO8601 格式的日期字串轉換成 datetime 物件，
            # 這裡透過 .replace('Z', '') 處理 UTC 時區標記
            open_date_time = datetime.fromisoformat(open_date_time_str.replace('Z', ''))
        except Exception as e:
            return jsonify({"error": f"openDateTime 格式有誤: {e}"}), 400

    # TODO: 根據需求，將資料寫入資料庫或執行其他商業邏輯

    return jsonify({
        "message": "申請 Route B 成功",
        "data": {
            "userName": user_name,
            "identity": identity,
            "email": email,
            "phone": phone,
            "openDateTime": open_date_time_str,
            "tpcNo": tpc_no
        }
    }), 200


@taipower_bp.route('/themsIo/agreeImage', methods=['POST'])
def agree_image():
    """
    處理使用者上傳圖片的 API
    使用 Multipart/Form-Data 傳遞，欄位名稱為 image
    備註：
    - 建議僅支援 JPG 格式圖片，上傳時進行副檔名檢查
    """
    file = request.files.get('image')
    if not file or file.filename == '':
        return jsonify({"error": "未收到任何圖片檔案"}), 400

    filename = secure_filename(file.filename)

    # 檢查檔案副檔名是否為 JPG 或 JPEG 格式
    allowed_extensions = {'jpg', 'jpeg'}
    ext = filename.rsplit('.', 1)[-1].lower()
    if ext not in allowed_extensions:
        return jsonify({"error": "僅允許上傳 JPG 格式圖片"}), 400

    # 設定上傳資料夾，這裡以專案的 uploads 資料夾為例
    upload_folder = os.path.join(current_app.root_path, 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)

    file_path = os.path.join(upload_folder, filename)

    try:
        file.save(file_path)
    except Exception as e:
        return jsonify({"error": f"檔案儲存失敗: {e}"}), 500

    # TODO: 如有需要，可在此將檔案資訊寫入資料庫

    return jsonify({
        "message": "圖片上傳成功",
        "fileName": filename,
        "filePath": file_path
    }), 200
