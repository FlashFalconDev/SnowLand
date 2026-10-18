def display_marketing_source(value):
    source = (value or '').strip()
    if source.lower() == 'other':
        return '其他'
    return source or '未填寫'
