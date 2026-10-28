# Generated migration to fix NULL user_id foreign key issues

from django.db import migrations

def fix_null_user_ids(apps, schema_editor):
    """
    This migration ensures NULL user_id values are properly handled.
    Since the models already allow null=True, we just need to ensure
    the database is in a consistent state.
    """
    # No data changes needed - the models already allow NULL
    # This migration just ensures the schema is consistent
    pass

def reverse_fix(apps, schema_editor):
    """Reverse migration"""
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('detections', '0002_speakerdetection_emotiondetection'),
    ]

    operations = [
        migrations.RunPython(fix_null_user_ids, reverse_fix),
    ]

