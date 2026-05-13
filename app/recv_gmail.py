import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import os
import re
import msoffcrypto
import openpyxl
from io import BytesIO

# 帳號設定
EMAIL = "skuvy.liang@nextdrive.io"
PASSWORD = "pnxnmmoddhqmdsci"
SAVE_FOLDER = "taipower_replies"
os.makedirs(SAVE_FOLDER, exist_ok=True)


def decode_mime_words(s: str) -> str:
    decoded = ""
    for word, charset in decode_header(s):
        if isinstance(word, bytes):
            decoded += word.decode(charset or "utf-8", errors="ignore")
        else:
            decoded += word
    return decoded


def decrypt_excel(filepath: str, password: str) -> BytesIO:
    decrypted = BytesIO()
    with open(filepath, "rb") as f:
        file = msoffcrypto.OfficeFile(f)
        file.load_key(password=password)
        file.decrypt(decrypted)
    decrypted.seek(0)
    return decrypted


def read_excel_content(decrypted_io: BytesIO):
    wb = openpyxl.load_workbook(decrypted_io, data_only=True)
    sheet = wb.active
    print(f"📄 工作表：{sheet.title}")
    for row in sheet.iter_rows(values_only=True):
        print(row)


def download_and_process_latest():
    # 保留原 download_and_process_latest
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(EMAIL, PASSWORD)
    mail.select("inbox")

    raw_criteria = 'from:taipower.com.tw is:unread'
    status, messages = mail.search(None, 'X-GM-RAW', f'"{raw_criteria}"')
    if status != 'OK':
        print("❌ 搜尋失敗")
        mail.logout()
        return

    mail_ids = messages[0].split()
    if not mail_ids:
        print("📭 沒有符合條件的未讀信件")
        mail.logout()
        return

    latest_id = mail_ids[-1]
    print(f"📬 處理最新UID={latest_id.decode()}")

    _, data = mail.fetch(latest_id, "(RFC822)")
    msg = email.message_from_bytes(data[0][1])

    subject = decode_mime_words(msg.get("Subject", ""))
    if "金鑰" not in subject:
        print("⏭️ 最新一封信件非金鑰相關")
        mail.logout()
        return

    found_password = None
    attachment_path = None
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
            m = re.search(r"密碼[：:]\s*([^\s\n]+)", body)
            if m:
                found_password = m.group(1)
        disp = part.get("Content-Disposition")
        if disp and part.get_filename():
            fname = decode_mime_words(part.get_filename())
            if fname.lower().endswith((".xls", ".xlsx")):
                path = os.path.join(SAVE_FOLDER, fname)
                with open(path, "wb") as f:
                    f.write(part.get_payload(decode=True))
                attachment_path = path

    mail.store(latest_id, '+FLAGS', '\\Seen')
    mail.logout()

    if not found_password or not attachment_path:
        print("⚠️ 缺少密碼或附件，略過處理")
        return

    try:
        bio = decrypt_excel(attachment_path, found_password)
        read_excel_content(bio)
    except Exception as e:
        print(f"❌ 解密/讀取失敗：{e}")


def fetch_latest_taipower_excel() -> BytesIO:
    """
    抓取所有未讀金鑰信件，選擇日期最晚的一封，回傳解密後的 BytesIO；否則回 None
    """
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(EMAIL, PASSWORD)
    mail.select("inbox")

    status, msgs = mail.search(None, 'X-GM-RAW', '"from:taipower.com.tw is:unread"')
    if status != 'OK':
        mail.logout()
        return None

    uids = msgs[0].split()
    if not uids:
        mail.logout()
        return None

    # 取出每封信的 INTERNALDATE，選最新
    date_uid_list = []
    for uid in uids:
        st, dt_data = mail.fetch(uid, '(INTERNALDATE)')
        if st != 'OK':
            continue
        # dt_data[0][1] 格式: b'1 (INTERNALDATE "01-Jan-2025 12:34:56 +0000")'
        txt = dt_data[0][1].decode('utf-8', errors='ignore')
        m = re.search(r'INTERNALDATE "([^"]+)"', txt)
        if not m:
            continue
        dt = parsedate_to_datetime(m.group(1))
        date_uid_list.append((uid, dt))

    mail.logout()
    if not date_uid_list:
        return None
    # 選最新日期
    latest_uid = max(date_uid_list, key=lambda x: x[1])[0]

    # 重新登入以取回該信完整內容
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(EMAIL, PASSWORD)
    mail.select("inbox")
    _, data = mail.fetch(latest_uid, "(RFC822)")
    msg = email.message_from_bytes(data[0][1])

    subject = decode_mime_words(msg.get("Subject", ""))
    if "金鑰" not in subject:
        mail.logout()
        return None

    pw = None
    attachment_bytes = None
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
            m = re.search(r"密碼[：:]\s*([^\s\n]+)", body)
            if m:
                pw = m.group(1)
        disp = part.get("Content-Disposition")
        if disp and part.get_filename():
            fn = decode_mime_words(part.get_filename())
            if fn.lower().endswith((".xls", ".xlsx")):
                attachment_bytes = part.get_payload(decode=True)

    # 標記已讀
    mail.store(latest_uid, '+FLAGS', '\\Seen')
    mail.logout()

    if not pw or not attachment_bytes:
        return None

    bio = BytesIO()
    office = msoffcrypto.OfficeFile(BytesIO(attachment_bytes))
    office.load_key(password=pw)
    office.decrypt(bio)
    bio.seek(0)
    return bio


if __name__ == "__main__":
    download_and_process_latest()
