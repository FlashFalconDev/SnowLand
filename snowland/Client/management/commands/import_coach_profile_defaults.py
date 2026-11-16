import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from Client.models import Client
from Client.coach_profiles import coach_profile_record, save_coach_profile
from Client.coach_reviews import ensure_legacy_coach_reviews
from Coach.models import Coach


class Command(BaseCommand):
    help='Preserve public coach copy in the CMS; never create coaches or overwrite existing edits.'

    def add_arguments(self, parser):
        parser.add_argument('--client',required=True,help='Existing client internal code')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--fill-card', action='store_true', help='Fill empty public card fields for newly imported profiles')

    @transaction.atomic
    def handle(self, *args, **options):
        client=Client.objects.filter(internal_code=options['client'],is_active=True).first()
        if not client:
            raise CommandError('找不到指定的啟用公司')
        source=Path(__file__).resolve().parents[2]/'fixtures'/'coach_profile_defaults.json'
        records=json.loads(source.read_text(encoding='utf-8'))
        created=preserved=unmatched=reviews=cards=0
        missing = []
        candidates = Coach.objects.filter(client=client)
        for profile in records:
            slug = profile['slug']
            coaches = list(candidates.filter(website_slug__iexact=slug).order_by('pk')[:2])
            if not coaches and client.internal_code == 'snowland':
                # The live directory uses Seven for 七針 and an ID URL for Leon.
                aliases = {
                    'qizhen': Q(website_slug__iexact='seven', name='七針'),
                    'leon': Q(website_slug='', name__iexact='leon'),
                }
                if slug in aliases:
                    coaches = list(candidates.filter(aliases[slug], website_enabled=True).order_by('pk')[:2])
            if len(coaches)>1:
                raise CommandError('官網代號重複，請先核對教練：'+profile['slug'])
            if not coaches:
                unmatched+=1
                missing.append(slug)
                continue
            coach = coaches[0]
            if not options['dry_run']:
                coach = candidates.select_for_update().get(pk=coach.pk)
            has_profile = coach_profile_record(coach) is not None
            fields = []
            if options['fill_card'] and not has_profile:
                for field, value in (('img', profile.get('image')), ('website_card_bio', profile.get('cardBio'))):
                    if value and not getattr(coach, field):
                        setattr(coach, field, value)
                        fields.append(field)
            cards += int(bool(fields))
            if options['dry_run']:
                created += int(not has_profile)
                preserved += int(has_profile)
                continue
            _,changed=save_coach_profile(coach,profile)
            if fields:
                coach.save(update_fields=fields)
            reviews+=ensure_legacy_coach_reviews(coach)
            created+=int(changed);preserved+=int(not changed)
        prefix = '教練介紹預覽' if options['dry_run'] else '教練介紹匯入'
        self.stdout.write(f'{prefix}：{"可新增" if options["dry_run"] else "新增"} {created}、保留既有 {preserved}、未對應 {unmatched}、補空白卡片 {cards}、評價歸檔新增 {reviews}')
        if missing:
            self.stdout.write('缺少對應教練：' + '、'.join(missing))
