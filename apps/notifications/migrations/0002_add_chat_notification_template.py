from django.db import migrations

def create_chat_notification_template(apps, schema_editor):
    NotificationTemplate = apps.get_model('notifications', 'NotificationTemplate')
    NotificationTemplate.objects.create(
        name='new_chat_message',
        body='{sender} sent you a new message: {message}'
    )

class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_chat_notification_template),
    ]
