# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import (
    migrations,
    models,
)


class Migration(migrations.Migration):

    dependencies = [
        ('maasserver', '0004_migrate_installable_to_node_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='node',
            name='installable',
        ),
    ]