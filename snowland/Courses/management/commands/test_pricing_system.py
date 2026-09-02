from django.core.management.base import BaseCommand
from django.utils import timezone
from Coursekit.models import CoursePricing, SeasonSetting
from Resorts.models import Resorts

class Command(BaseCommand):
    help = '测试新的定价系统'

    def handle(self, *args, **options):
        self.stdout.write('开始测试定价系统...')
        
        # 测试1: 显示所有雪场
        self.stdout.write('\n=== 雪场信息 ===')
        for resort in Resorts.objects.all():
            self.stdout.write(f'- {resort.display_name} ({resort.name})')
        
        # 测试2: 显示所有定价策略
        self.stdout.write('\n=== 定价策略信息 ===')
        strategies = CoursePricing.objects.all()
        if strategies:
            for strategy in strategies:
                self.stdout.write(f'- {strategy}')
        else:
            self.stdout.write('暂无定价策略数据')
        
        # 测试3: 测试价格计算（如果有定价策略的话）
        if strategies:
            self.stdout.write('\n=== 价格计算测试 ===')
            for strategy in strategies:
                self.stdout.write(f'\n{strategy.template} - {strategy.resort.display_name}:')
                
                # 测试淡季价格
                for people in range(1, min(7, strategy.max_capacity + 1)):
                    price = strategy.calculate_price(people, is_peak_season=False)
                    self.stdout.write(f'  淡季 {people}人: ${price:,}')
                
                # 测试旺季价格
                for people in range(1, min(7, strategy.max_capacity + 1)):
                    price = strategy.calculate_price(people, is_peak_season=True)
                    self.stdout.write(f'  旺季 {people}人: ${price:,}')
        else:
            self.stdout.write('\n=== 价格计算测试 ===')
            self.stdout.write('暂无定价策略数据，无法进行价格计算测试')
        
        # 测试4: 测试季节判断
        self.stdout.write('\n=== 季节判断测试 ===')
        today = timezone.now().date()
        season_type = SeasonSetting.get_season_type_for_date(today)
        self.stdout.write(f'今天 ({today}) 是: {season_type}')
        
        # 测试5: 容量限制测试（如果有定价策略的话）
        if strategies:
            self.stdout.write('\n=== 容量限制测试 ===')
            for strategy in strategies:
                try:
                    # 尝试计算超过容量的价格
                    strategy.calculate_price(strategy.max_capacity + 1, is_peak_season=False)
                except ValueError as e:
                    self.stdout.write(f'✓ {strategy.template} - {strategy.resort.display_name}: {e}')
        else:
            self.stdout.write('\n=== 容量限制测试 ===')
            self.stdout.write('暂无定价策略数据，无法进行容量限制测试')
        
        self.stdout.write('\n定价系统测试完成！')
        self.stdout.write('\n注意：你需要在管理界面中手动创建定价策略数据')
