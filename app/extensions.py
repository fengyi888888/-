"""Flask 扩展集中实例化，避免循环导入。"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()