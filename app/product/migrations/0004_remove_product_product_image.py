from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0003_migrate_image_data'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='product',
            name='product_image',
        ),
    ]
