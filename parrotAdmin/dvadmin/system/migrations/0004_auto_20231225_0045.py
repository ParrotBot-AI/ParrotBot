# Generated by Django 3.2.19 on 2023-12-25 00:45

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0003_auto_20231219_2025'),
    ]

    operations = [
        migrations.CreateModel(
            name='MicroServiceRegister',
            fields=[
                ('id', models.BigAutoField(help_text='Id', primary_key=True, serialize=False, verbose_name='Id')),
                ('description', models.CharField(blank=True, help_text='描述', max_length=255, null=True, verbose_name='描述')),
                ('modifier', models.CharField(blank=True, help_text='修改人', max_length=255, null=True, verbose_name='修改人')),
                ('dept_belong_id', models.CharField(blank=True, help_text='数据归属部门', max_length=255, null=True, verbose_name='数据归属部门')),
                ('update_datetime', models.DateTimeField(auto_now=True, help_text='修改时间', null=True, verbose_name='修改时间')),
                ('create_datetime', models.DateTimeField(auto_now_add=True, help_text='创建时间', null=True, verbose_name='创建时间')),
                ('name', models.CharField(help_text='服务名称', max_length=50, verbose_name='服务名称')),
                ('host', models.CharField(help_text='服务ip', max_length=50, verbose_name='服务ip')),
                ('port', models.IntegerField(help_text='服务端口号', verbose_name='服务端口号')),
                ('heartBeatApi', models.CharField(help_text='心跳检测api', max_length=50, verbose_name='心跳检测api')),
                ('frequency', models.IntegerField(help_text='心跳检测频率', verbose_name='心跳检测频率')),
                ('status', models.IntegerField(choices=[(0, '关闭'), (1, '开启'), (2, '重启')], default=1, help_text='服务状态', verbose_name='服务状态')),
                ('API_Key', models.CharField(help_text='服务专属apikey', max_length=50, verbose_name='服务专属apikey')),
                ('creator', models.ForeignKey(db_constraint=False, help_text='创建人', null=True, on_delete=django.db.models.deletion.SET_NULL, related_query_name='creator_query', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
            ],
            options={
                'verbose_name': '微服务注册',
                'verbose_name_plural': '微服务注册',
                'db_table': 'parrot_mircoservice_register',
                'ordering': ('-create_datetime',),
            },
        ),
        migrations.AddField(
            model_name='menu',
            name='micro_service',
            field=models.ForeignKey(blank=True, db_constraint=False, help_text='关联微服务', null=True, on_delete=django.db.models.deletion.PROTECT, to='system.microserviceregister', verbose_name='关联微服务'),
        ),
        migrations.AddField(
            model_name='operationlog',
            name='micro_service',
            field=models.ForeignKey(blank=True, db_constraint=False, help_text='关联微服务', null=True, on_delete=django.db.models.deletion.PROTECT, to='system.microserviceregister', verbose_name='关联微服务'),
        ),
    ]