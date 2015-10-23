# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import push_notifications.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('push_notifications', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ADMDevice',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255, null=True, verbose_name='Name', blank=True)),
                ('active', models.BooleanField(default=True, help_text='Inactive devices will not be sent notifications', verbose_name='Is active')),
                ('date_created', models.DateTimeField(auto_now_add=True, verbose_name='Creation date', null=True)),
                ('device_id', push_notifications.fields.HexIntegerField(help_text='ANDROID_ID / TelephonyManager.getDeviceId() (always as hex)', null=True, verbose_name='Device ID', db_index=True, blank=True)),
                ('registration_id', models.TextField(verbose_name='Registration ID')),
                ('user', models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'verbose_name': 'ADM device',
            },
        ),
        migrations.CreateModel(
            name='ADMToken',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('token', models.CharField(max_length=80, verbose_name='Token')),
                ('expiration_date', models.DateTimeField()),
                ('request_id', models.CharField(max_length=36, verbose_name='Request ID')),
            ],
            options={
                'verbose_name': 'Amazon Device Messaging Access Token',
            },
        ),
    ]
