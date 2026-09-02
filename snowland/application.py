import os
import sys

# 添加项目路径到Python路径
sys.path.insert(0, os.path.dirname(__file__))

# 设置Django环境
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "snowland.settings")

# 导入Django WSGI应用
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
