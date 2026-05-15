#!/usr/bin/env python
# wsgi.py

try:
    from cryptography.hazmat.bindings.openssl.binding import Binding
    _crypto_lib = Binding().lib

    import OpenSSL.crypto
    _pyssl_lib = OpenSSL.crypto._lib

    for flag in (
        'X509_V_FLAG_NOTIFY_POLICY',
        'X509_V_FLAG_CB_ISSUER_CHECK',
    ):
        if not hasattr(_crypto_lib, flag):
            setattr(_crypto_lib, flag, 0)
        if not hasattr(_pyssl_lib, flag):
            setattr(_pyssl_lib, flag, 0)
except Exception:
    pass


import os
from app import create_app, db
from app.models import User, Role, Catalog, MaintenanceRecord
from flask_migrate import Migrate
from flask_uploads import configure_uploads
from app import images

app = create_app(os.getenv('FLASK_CONFIG') or 'default')

# 配置文件上傳
configure_uploads(app, images)

# 設置 Flask-Migrate
migrate = Migrate(app, db)

@app.shell_context_processor
def make_shell_context():
    """為 Flask Shell 提供上下文變數"""
    return dict(app=app, db=db, User=User, Role=Role, Catalog=Catalog, MaintenanceRecord=MaintenanceRecord)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
