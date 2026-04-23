# migrations/env.py

from __future__ import with_statement
import sys
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, create_engine

# ----------------------------------------------------------------------
#  一、把项目根目录加入 Python 搜索路径，以便下面能 import 到 wsgi.py 和 app 模块
# ----------------------------------------------------------------------
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ----------------------------------------------------------------------
#  二、从 Flask 应用中读取 SQLALCHEMY_DATABASE_URI，并覆盖 Alembic 原来 ini 文件里的 URL
# ----------------------------------------------------------------------
from wsgi import app  # 直接 import 你的 Flask app 实例
flask_sqlalchemy_url = app.config.get('SQLALCHEMY_DATABASE_URI')
if not flask_sqlalchemy_url:
    raise RuntimeError("Flask 配置中没有找到 'SQLALCHEMY_DATABASE_URI'。请检查 wsgi.py 中是否正确设置。")

# Alembic Config 对象
config = context.config

# 覆盖 alembic.ini 里原本的 sqlalchemy.url
# 这样无论 alembic.ini 里写的是哪条 URL，都会被下面这一行替换成 Flask app 中定义的 URI
config.set_main_option('sqlalchemy.url', flask_sqlalchemy_url)

# ----------------------------------------------------------------------
#  三、读取 alembic.ini 里的 logging 配置
# ----------------------------------------------------------------------
fileConfig(config.config_file_name)

# ----------------------------------------------------------------------
#  四、导入你的 Flask-SQLAlchemy db 以及所有 Model，以便 Alembic 自动识别 metadata
# ----------------------------------------------------------------------
from app import db
import app.models  # 确保所有 model 都被导入进来

# 让 Alembic 知道 “要对哪个 metadata 进行对比”
target_metadata = db.metadata


# ----------------------------------------------------------------------
#  五、定义 Offline 与 Online 两种迁移模式
# ----------------------------------------------------------------------

def run_migrations_offline():
    """
    在 offline 模式下，只产生 SQL 脚本，不实际连接数据库执行。
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """
    在 online 模式下，真正去连接数据库并执行迁移。
    """
    # 从 config 中读取最终要连接的 URL（已经被我们在上面用 Flask 的配置覆盖过）
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("没有在 Alembic 配置中找到 'sqlalchemy.url'。")

    # 用 SQLAlchemy 的 create_engine 建立连接
    engine = create_engine(url, poolclass=pool.NullPool)
    connection = engine.connect()

    # 配置 context，使其使用我们打开的连接
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # 如果生成的 migration 里发现没有实际 schema 变动，就跳过
        process_revision_directives=_auto_skip_empty,
    )

    try:
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.close()


def _auto_skip_empty(context, revision, directives):
    """
    如果 autogenerate 找不到任何 schema 变动，就不要生成空的 migration 文件。
    """
    if getattr(config.cmd_opts, 'autogenerate', False):
        script = directives[0]
        if script.upgrade_ops.is_empty():
            directives[:] = []
            logger = context.get_context().opts.get('logger', None)
            if logger:
                logger.info('没有检测到 schema 变动，跳过生成空迁移。')


# ----------------------------------------------------------------------
#  六、选择执行 offline 还是 online
# ----------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
