# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-11-29 19:50
from __future__ import unicode_literals

import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0145_clear_undo_history'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='changeparametercommand',
            name='delta_ptr',
        ),
        migrations.RemoveField(
            model_name='changeparametercommand',
            name='parameter_val',
        ),
        migrations.RemoveField(
            model_name='addmodulecommand',
            name='dependent_wf_module_last_delta_ids',
        ),
        migrations.RemoveField(
            model_name='changedataversioncommand',
            name='dependent_wf_module_last_delta_ids',
        ),
        migrations.RemoveField(
            model_name='changeparameterscommand',
            name='dependent_wf_module_last_delta_ids',
        ),
        migrations.RemoveField(
            model_name='deletemodulecommand',
            name='dependent_wf_module_last_delta_ids',
        ),
        migrations.RemoveField(
            model_name='reordermodulescommand',
            name='dependent_wf_module_last_delta_ids',
        ),
        migrations.AlterField(
            model_name='addmodulecommand',
            name='wf_module',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='server.WfModule'),
        ),
        migrations.AlterField(
            model_name='addmodulecommand',
            name='wf_module_delta_ids',
            field=django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), size=2), size=None),
        ),
        migrations.AlterField(
            model_name='changedataversioncommand',
            name='wf_module',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='server.WfModule'),
        ),
        migrations.AlterField(
            model_name='changedataversioncommand',
            name='wf_module_delta_ids',
            field=django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), size=2), size=None),
        ),
        migrations.AlterField(
            model_name='changeparameterscommand',
            name='wf_module_delta_ids',
            field=django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), size=2), size=None),
        ),
        migrations.AlterField(
            model_name='changewfmodulenotescommand',
            name='wf_module',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='server.WfModule'),
        ),
        migrations.AlterField(
            model_name='changewfmoduleupdatesettingscommand',
            name='wf_module',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='server.WfModule'),
        ),
        migrations.AlterField(
            model_name='deletemodulecommand',
            name='wf_module',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='server.WfModule'),
        ),
        migrations.AlterField(
            model_name='deletemodulecommand',
            name='wf_module_delta_ids',
            field=django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), size=2), size=None),
        ),
        migrations.AlterField(
            model_name='reordermodulescommand',
            name='wf_module_delta_ids',
            field=django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), size=2), size=None),
        ),
        migrations.DeleteModel(
            name='ChangeParameterCommand',
        ),
    ]