from django.core.management.base import BaseCommand,CommandError
from django.contrib.auth.models import User
from Client.models import Client
from Control.tenant_memberships import writable_staff_profile


class Command(BaseCommand):
    help = '設定指定學校的使用者權限；不修改共用登入帳號或其他學校'

    def add_arguments(self,parser):
        parser.add_argument('email')
        parser.add_argument('--client',required=True,help='學校 internal_code')
        parser.add_argument('--manager',action='store_true')
        parser.add_argument('--coach',action='store_true')

    def handle(self,*args,**options):
        try:
            user=User.objects.get(email__iexact=options['email'])
            client=Client.objects.get(internal_code=options['client'])
        except (User.DoesNotExist,User.MultipleObjectsReturned,Client.DoesNotExist) as exc:
            raise CommandError('找不到唯一的使用者或指定學校') from exc
        if not options['manager'] and not options['coach']:
            raise CommandError('請指定 --manager 或 --coach')
        profile=writable_staff_profile(user,client)
        if options['manager']:
            if not profile.is_manager:
                profile.role='hq_admin';profile.admin_permissions=None
            profile.is_manager=True
        if options['coach']:
            profile.is_coach=True
            if not profile.role:profile.role='coach'
        profile.save()
        self.stdout.write(self.style.SUCCESS('已更新指定學校權限；其他學校與共用帳號不變。'))
