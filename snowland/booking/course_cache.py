from django.core.cache import cache


def clear_course_data_cache(client_codes, *, legacy=False):
    keys = [
        f'course_data_optimized_{version}_{code}'
        for code in client_codes
        for version in ('v1', 'v2')
    ]
    if legacy:
        keys.append('course_data_optimized_v1')
    cache.delete_many(keys)
