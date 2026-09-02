"""
Celery 定時任務配置

用途：
1. 自動檢查未付款預約（每 10 分鐘檢查，超過 24 小時才取消）
2. 清除過期快取（每天凌晨 3 點執行）

使用前需先安裝：
pip install celery redis

並在 settings.py 中配置 Celery
"""
from celery import shared_task
from django.core.cache import cache
from .tasks import auto_cancel_unpaid_reservations


@shared_task
def scheduled_auto_cancel_reservations():
    """
    定時任務：自動取消未付款預約

    執行頻率：每 10 分鐘檢查一次；實際取消條件由 tasks.py 的 24 小時規則判斷。
    """
    try:
        auto_cancel_unpaid_reservations()
        return "自動取消任務執行成功"
    except Exception as e:
        return f"自動取消任務執行失敗: {str(e)}"


@shared_task
def scheduled_clear_expired_cache():
    """
    定時任務：清除過期快取

    執行頻率：每天凌晨 3 點
    """
    try:
        cache_key = 'course_data_optimized_v1'
        cache.delete(cache_key)
        return "快取清除成功"
    except Exception as e:
        return f"快取清除失敗: {str(e)}"


# ========== Celery Beat 排程配置（加到 settings.py） ==========
"""
在 snowland/settings.py 中加入：

from celery.schedules import crontab

CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Taipei'

CELERY_BEAT_SCHEDULE = {
    'auto-cancel-unpaid-reservations': {
        'task': 'booking.celery_tasks.scheduled_auto_cancel_reservations',
        'schedule': 600.0,  # 每 10 分鐘檢查一次；未付款滿 24 小時才取消
    },
    'clear-expired-cache': {
        'task': 'booking.celery_tasks.scheduled_clear_expired_cache',
        'schedule': crontab(hour=3, minute=0),  # 每天凌晨 3 點執行
    },
}
"""
