"""
優化效果測試腳本

執行方式：
python manage.py shell < test_optimization.py

或在 Django shell 中逐行執行
"""
import time
from django.db import connection, reset_queries
from django.core.cache import cache
from booking.utils import build_course_data_optimized

print("=" * 60)
print("資料流優化效果測試")
print("=" * 60)

# ========== 測試 1: 資料庫查詢次數 ==========
print("\n[測試 1] 資料庫查詢次數比較")
print("-" * 60)

# 清除快取確保公平測試
cache.clear()
reset_queries()

# 測試優化版本
start_time = time.time()
course_data = build_course_data_optimized()
query_count = len(connection.queries)
execution_time = time.time() - start_time

print(f"✓ 優化版本:")
print(f"  - 資料庫查詢次數: {query_count}")
print(f"  - 執行時間: {execution_time:.3f} 秒")
print(f"  - 返回資料項目數:")
print(f"    * time_slot_config: {len(course_data['time_slot_config'])} 項")
print(f"    * course_categories: {len(course_data['course_categories'])} 項")
print(f"    * course_types: {len(course_data['course_types'])} 項")
print(f"    * course_templates: {len(course_data['course_templates'])} 項")
print(f"    * course_sessions: {len(course_data['course_sessions'])} 項")

# ========== 測試 2: 快取效果 ==========
print("\n[測試 2] 快取機制測試")
print("-" * 60)

# 第一次呼叫（應該要寫入快取）
cache.clear()
cache_key = 'course_data_optimized_v1'

start_time = time.time()
cached_data = cache.get(cache_key)
if not cached_data:
    cached_data = build_course_data_optimized()
    cache.set(cache_key, cached_data, 60 * 15)
    print("✓ 第一次呼叫（快取未命中）")
else:
    print("  第一次呼叫（快取命中）")
first_call_time = time.time() - start_time
print(f"  - 執行時間: {first_call_time:.3f} 秒")

# 第二次呼叫（應該從快取讀取）
start_time = time.time()
cached_data = cache.get(cache_key)
if not cached_data:
    cached_data = build_course_data_optimized()
    cache.set(cache_key, cached_data, 60 * 15)
    print("  第二次呼叫（快取未命中）")
else:
    print("✓ 第二次呼叫（快取命中）")
second_call_time = time.time() - start_time
print(f"  - 執行時間: {second_call_time:.3f} 秒")

if second_call_time < first_call_time:
    speedup = (first_call_time / second_call_time) - 1
    print(f"  - 速度提升: {speedup * 100:.1f}%")

# ========== 測試 3: 資料完整性檢查 ==========
print("\n[測試 3] 資料完整性檢查")
print("-" * 60)

errors = []

# 檢查必要欄位
required_keys = [
    'time_slot_config',
    'template_slots_config',
    'all_courses_data',
    'course_categories',
    'course_types',
    'course_templates',
    'course_sessions'
]

for key in required_keys:
    if key not in course_data:
        errors.append(f"缺少必要欄位: {key}")

# 檢查資料格式
if course_data.get('course_categories'):
    category = course_data['course_categories'][0]
    if 'id' not in category or 'name' not in category:
        errors.append("course_categories 格式錯誤")

if course_data.get('course_sessions'):
    session = course_data['course_sessions'][0]
    if 'id' not in session or 'template_id' not in session:
        errors.append("course_sessions 格式錯誤")

if errors:
    print("✗ 發現錯誤:")
    for error in errors:
        print(f"  - {error}")
else:
    print("✓ 所有資料格式正確")

# ========== 總結 ==========
print("\n" + "=" * 60)
print("測試總結")
print("=" * 60)
print(f"✓ 資料庫查詢次數: {query_count} 次")
print(f"✓ 首次載入時間: {first_call_time:.3f} 秒")
print(f"✓ 快取載入時間: {second_call_time:.3f} 秒")
print(f"✓ 資料完整性: {'通過' if not errors else '失敗'}")
print("\n優化建議:")
print("1. 確認已設定 Django Cache (settings.py)")
print("2. 課程資料更新後記得清除快取")
print("3. 考慮將 auto_cancel_unpaid_reservations 移到 Celery")
print("=" * 60)
