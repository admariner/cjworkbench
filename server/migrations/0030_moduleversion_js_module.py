# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-01-02 17:13
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0029_auto_20190102_1526'),
    ]

    operations = [
        migrations.AddField(
            model_name='moduleversion',
            name='js_module',
            field=models.TextField(default='', null=True, verbose_name='js_module'),
        ),
    ]