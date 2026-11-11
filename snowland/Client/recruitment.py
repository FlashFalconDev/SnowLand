from hashlib import sha256
import json

from PIL import Image, UnidentifiedImageError
from rest_framework import serializers


MB = 1024 * 1024
MAX_UPLOAD_BYTES = 20 * MB
FILE_FORMATS = {
    'pdf': ('.pdf', 'application/pdf'),
    'jpeg': ('.jpg', 'image/jpeg'),
    'png': ('.png', 'image/png'),
}
CHOICE_TYPES = ('single', 'multiple')


class RecruitmentFieldSerializer(serializers.Serializer):
    id = serializers.RegexField(r'\A[a-z0-9][a-z0-9_-]{0,63}\Z')
    label = serializers.CharField(max_length=150)
    type = serializers.ChoiceField(choices=('short', 'long', *CHOICE_TYPES, 'file'))
    required = serializers.BooleanField()
    options = serializers.ListField(child=serializers.CharField(max_length=100), max_length=20, required=False)
    formats = serializers.ListField(child=serializers.ChoiceField(choices=FILE_FORMATS), max_length=3, required=False)
    max_mb = serializers.IntegerField(min_value=1, max_value=10, required=False)

    def validate(self, field):
        kind = field['type']
        if kind in CHOICE_TYPES:
            options = field.get('options', [])
            if len(set(options)) != len(options) or len(options) < 2:
                raise serializers.ValidationError('選擇題至少需要兩個不同的選項')
            return {key: field[key] for key in ('id', 'label', 'type', 'required', 'options')}
        if kind == 'file':
            formats = field.get('formats', [])
            if not formats or 'max_mb' not in field:
                raise serializers.ValidationError('附件必須設定接受格式及大小上限')
            return {**field, 'formats': list(dict.fromkeys(formats))}
        return {key: field[key] for key in ('id', 'label', 'type', 'required')}


class RecruitmentSettingsSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    fields = RecruitmentFieldSerializer(many=True, max_length=30)
    revision = serializers.CharField(max_length=64)

    def validate(self, data):
        fields = data['fields']
        if len({field['id'] for field in fields}) != len(fields):
            raise serializers.ValidationError('題目代號不能重複')
        if data['enabled'] and not fields:
            raise serializers.ValidationError('請至少新增一道題目再開放表單')
        files = [field for field in fields if field['type'] == 'file']
        if len(files) > 5 or sum(field['max_mb'] for field in files) > MAX_UPLOAD_BYTES // MB:
            raise serializers.ValidationError('附件欄位最多 5 個，各欄位大小上限合計不得超過 20 MB')
        return data


def digest(data):
    return sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def form_settings(form):
    config = {'enabled': form.enabled, 'fields': form.fields} if form else {'enabled': False, 'fields': []}
    return {**config, 'revision': digest(config)}


def validate_answers(fields, answers, files):
    if not isinstance(answers, dict):
        raise serializers.ValidationError('回答格式不正確')
    clean_answers, uploads, errors = {}, {}, {}
    for field in fields:
        field_id = field['id']
        kind = field['type']
        if kind == 'file':
            upload = files.get(f'file_{field_id}')
            if upload:
                try:
                    uploads[field_id] = validate_upload(field, upload)
                except ValueError as error:
                    errors[field_id] = str(error)
            elif field['required']:
                errors[field_id] = '請上傳附件'
            continue

        value = answers.get(field_id, [] if kind == 'multiple' else '')
        if kind == 'multiple':
            if not isinstance(value, list) or len(value) > len(field['options']) or any(
                not isinstance(option, str) or option not in field['options'] for option in value
            ) or len(set(value)) != len(value):
                errors[field_id] = '請選擇表單上的選項'
                continue
        elif not isinstance(value, str) or '\x00' in value:
            errors[field_id] = '回答格式不正確'
            continue
        elif kind == 'single':
            if value and value not in field['options']:
                errors[field_id] = '請選擇表單上的選項'
                continue
        else:
            value = value.strip()
            try:
                value.encode('utf-8')
            except UnicodeEncodeError:
                errors[field_id] = '回答包含不支援的字元'
                continue
            limit = 200 if kind == 'short' else 5000
            if len(value) > limit:
                errors[field_id] = f'最多可填寫 {limit} 個字'
                continue
        if field['required'] and not value:
            errors[field_id] = '這是必填欄位'
        elif value:
            clean_answers[field_id] = value
    if errors:
        raise serializers.ValidationError({'fields': errors})
    return clean_answers, uploads


def validate_upload(field, upload):
    if not 0 < upload.size <= field['max_mb'] * MB:
        raise ValueError(f'請選擇小於或等於 {field["max_mb"]} MB 的非空白檔案')
    try:
        if upload.read(5) == b'%PDF-':
            file_format = 'pdf'
        else:
            upload.seek(0)
            image = Image.open(upload, formats=('JPEG', 'PNG'))
            file_format = image.format.lower()
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError) as error:
        raise ValueError('檔案不是有效的 PDF、JPEG 或 PNG') from error
    finally:
        upload.seek(0)
    if file_format not in field['formats']:
        raise ValueError('此欄位不接受這個檔案格式')
    return file_format
