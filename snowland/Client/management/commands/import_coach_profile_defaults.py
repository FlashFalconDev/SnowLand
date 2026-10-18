import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from Client.models import Client
from Client.coach_profiles import save_coach_profile
from Client.coach_reviews import ensure_legacy_coach_reviews
from Coach.models import Coach


class Command(BaseCommand):
    help='Preserve legacy public coach copy in the CMS; never create coaches or overwrite existing edits.'

    def add_arguments(self, parser):
        parser.add_argument('--client',required=True,help='Existing client internal code')

    @transaction.atomic
    def handle(self, *args, **options):
        client=Client.objects.filter(internal_code=options['client'],is_active=True).first()
        if not client:
            raise CommandError('找不到指定的啟用公司')
        source=Path(__file__).resolve().parents[2]/'fixtures'/'coach_profile_defaults.json'
        records=json.loads(source.read_text(encoding='utf-8'))
        created=preserved=unmatched=reviews=0
        for profile in records:
            coaches=list(Coach.objects.filter(client=client,website_slug=profile['slug']).order_by('pk')[:2])
            if len(coaches)>1:
                raise CommandError('官網代號重複，請先核對教練：'+profile['slug'])
            if not coaches:
                unmatched+=1
                continue
            _,changed=save_coach_profile(coaches[0],profile)
            reviews+=ensure_legacy_coach_reviews(coaches[0])
            created+=int(changed);preserved+=int(not changed)
        self.stdout.write(f'教練介紹匯入：新增 {created}、保留既有 {preserved}、未對應 {unmatched}、評價歸檔新增 {reviews}；未新增或修改教練基本資料')
