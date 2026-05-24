from django.db import migrations


def move_images_to_product_image(apps, schema_editor):
    Product = apps.get_model('product', 'Product')
    ProductImage = apps.get_model('product', 'ProductImage')
    for p in Product.objects.filter(is_delete=False).exclude(product_image__isnull=True).exclude(product_image=''):
        ProductImage.objects.create(
            product=p,
            image=p.product_image,
            is_primary=True,
            sort_order=0,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0002_add_product_image_model'),
    ]

    operations = [
        migrations.RunPython(move_images_to_product_image, migrations.RunPython.noop),
    ]
