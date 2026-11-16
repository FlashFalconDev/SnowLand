import json
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from Client.models import Client, SiteContent


FIXTURES = Path(__file__).resolve().parents[2] / 'fixtures'
INITIALIZERS = (
    'initialize_homepage_presentation',
    'initialize_homepage_courses',
    'initialize_course_areas',
    'initialize_about_page',
    'initialize_join_us_page',
    'initialize_photography_pages',
    'initialize_site_footer',
    'initialize_guide_articles',
)
SINGLE_PAGES = {
    'about.contact', 'guides.index', 'guides.preparation', 'guides.faq-page',
    'news.offers', 'offers.earlybird', 'offers.referral', 'offers.promo',
    'photography.how-to-book',
}
COLLECTIONS = {
    'homepage.offers', 'homepage.reviews', 'course.resorts', 'course.resort-pages',
    'guides.article-pages', 'guides.faq', 'photography.gallery',
}


def read_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


def resort_content(row, reference):
    metadata = row['metadata']
    if row['location_key'] == 'course.resorts':
        metadata = {**metadata, 'imagePlaceholder': reference['heroImage']}
    else:
        details = {key: value for key, value in reference.items() if key != 'slug'}
        metadata = {**metadata, 'resort': {**metadata['resort'], **details}}
    return {
        **row, 'summary': reference['description'], 'image_url': reference['heroImage'],
        'tags': reference['tags'], 'metadata': metadata,
    }


def display_prices():
    source = read_fixture('website_pricing_2627.json')
    for group in source['groups']:
        columns = ('full', 'half')[:len(group['labels'])]
        labels = group.get('row_labels', ['1人', '2人', '3人', '4人'])
        periods = group.get('periods', source['periods'])
        plans = {}
        for key, title in (('regular', '一般時段'), ('discount', '優惠時段')):
            plans[key] = {
                'label': title,
                'period': periods[key],
                'rows': [
                    {'label': label, **dict(zip(columns, amounts, strict=True))}
                    for label, amounts in zip(labels, group[key], strict=True)
                ],
            }
        languages = {'title': '語言指定', 'rows': [['中文／粵語／英語', '依照指定教練等級加指定費']]}
        for slug in group['slugs']:
            addons = [
                {'title': '協助租借裝備加購', 'rows': [['加購協助(半小時)', 'NT$1,200']]},
                languages,
                {'title': '教練指定費', 'rows': [['1級教練', 'NT$1,200'], ['2級教練', 'NT$2,000'], ['校長', 'NT$3,000']]},
            ]
            if slug == 'off-piste-guide':
                addons = [
                    {'title': '嚮導人數', 'rows': [['1~4人', '一位嚮導'], ['5~8人', '兩位嚮導']]},
                    languages,
                ]
            yield {
                'content_type': 'setting',
                'location_key': 'course.pricing',
                'external_id': slug,
                'title': f'{slug} 官網價目表',
                'status': 'active',
                'source': 'website-reference-import',
                'metadata': {
                    'source_url': f"{source['source']}course/{slug}",
                    'pricing': {
                        'season_label': source['season'],
                        'currency': 'NT$',
                        'columns': list(columns),
                        'column_labels': dict(zip(columns, group['labels'], strict=True)),
                        'plans': plans,
                        'addons': addons,
                        'fee_notes': ['實際費用以訂課系統顯示為準。'],
                    },
                },
            }


class Command(BaseCommand):
    help = 'Preview or initialize the missing SnowLand public website content, preserving existing edits.'

    def add_arguments(self, parser):
        parser.add_argument('--client', required=True, choices=['snowland'])
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        client = Client.objects.select_for_update().filter(
            internal_code=options['client'], is_active=True,
        ).first()
        if client is None:
            raise CommandError('找不到啟用中的 SnowLand')

        apply = options['apply']
        rows = list(SiteContent.objects.filter(client=client))
        defaults = read_fixture('site_content_defaults.json')
        reference = {row['slug']: row for row in read_fixture('website_resort_reference.json')}
        original = {
            (row['location_key'], row['external_id']): row
            for row in defaults
            if row['location_key'] in {'course.pricing', 'course.resorts', 'course.resort-pages'}
        }
        for location in sorted(SINGLE_PAGES | COLLECTIONS | {'course.pricing'}):
            existing = [row for row in rows if row.location_key == location]
            candidates = [
                row for row in defaults if row['location_key'] == location
            ] if location != 'course.pricing' else list(display_prices())
            if location in {'course.resorts', 'course.resort-pages'}:
                candidates = [
                    resort_content(row, reference[row['external_id']])
                    if row['external_id'] in reference else row
                    for row in candidates
                ]
            missing = [
                row for row in candidates
                if not self.has_existing_content(row, existing)
            ]
            upgrades = []
            for candidate in candidates:
                baseline = original.get((location, candidate['external_id']))
                if baseline is None or baseline == candidate:
                    continue
                for row in existing:
                    if row.external_id != candidate['external_id'] or row.start_at or row.end_at:
                        continue
                    if all(getattr(row, key) == value for key, value in baseline.items()):
                        fields = ('summary', 'image_url', 'tags', 'metadata')
                        upgrades.append((row, {key: candidate[key] for key in fields if key in candidate}))
            if apply:
                SiteContent.objects.bulk_create(SiteContent(client=client, **row) for row in missing)
                for row, fields in upgrades:
                    for key, value in fields.items():
                        setattr(row, key, value)
                    row.save(update_fields=[*fields, 'updated_at'])
            self.stdout.write(f'{location}：{"新增" if apply else "可新增"} {len(missing)} 筆，保留既有 {len(existing) - len(upgrades)} 筆')
            if upgrades:
                self.stdout.write(f'{"已更新" if apply else "可更新"} {len(upgrades)} 筆未編輯的舊版資料')

        for command in INITIALIZERS:
            self.stdout.write(command)
            call_command(command, client=client.internal_code, apply=apply, stdout=self.stdout)

        call_command('import_coach_profile_defaults', client=client.internal_code, dry_run=not apply,
                     fill_card=True, stdout=self.stdout)

    @staticmethod
    def has_existing_content(candidate, existing):
        location = candidate['location_key']
        if location in SINGLE_PAGES or location == 'homepage.reviews':
            return bool(existing)
        for row in existing:
            if row.external_id == candidate['external_id']:
                return True
            if location == 'homepage.offers' and row.link_url and row.link_url == candidate['link_url']:
                return True
            if location == 'photography.gallery' and row.image_url and row.image_url == candidate['image_url']:
                return True
            if location == 'guides.faq' and row.title == candidate['title']:
                return True
        return False
