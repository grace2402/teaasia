#!/bin/bash
# Fix config corruption and start app
python3 -c "
import os
with open('/app/config.py', 'r') as f: c = f.read()
if 'os.env...RD' in c or '***@teaasia-db' in c:
    c = c.replace(\"os.env...RD')\", \"os.environ.get('MAIL_PASSWORD')\")
    c = c.replace(\"os.env...RD', '')\", \"os.environ.get('PASSWORD', '')\")
    c = c.replace(\"***@teaasia-db\", \"teaasia@teaasia-db\")
    with open('/app/config.py', 'w') as f: f.write(c)
" && exec gunicorn -b 0.0.0.0:5000 --workers 2 --timeout 120 wsgi:app
