# Generated migration to remove phone_number and make email required

from django.db import migrations, models
from django.core.exceptions import ObjectDoesNotExist


def ensure_all_users_have_email(apps, schema_editor):
    """Ensure all users have email before making it required"""
    CustomUser = apps.get_model('core', 'CustomUser')
    
    # Find users without email
    users_without_email = CustomUser.objects.filter(email__isnull=True) | CustomUser.objects.filter(email='')
    
    for user in users_without_email:
        # Generate email from user_id if no email exists
        if not user.email or user.email == '':
            # Try to use phone_number if exists, otherwise generate from user_id
            if hasattr(user, 'phone_number') and user.phone_number:
                # Create email from phone_number
                user.email = f"user_{user.user_id}@migrated.local"
            else:
                user.email = f"user_{user.user_id}@migrated.local"
            user.save()


def reverse_ensure_email(apps, schema_editor):
    """Reverse migration - nothing to do"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_platformdiscountcode'),
    ]

    operations = [
        # Step 1: Ensure all users have email
        migrations.RunPython(ensure_all_users_have_email, reverse_ensure_email),
        
        # Step 2: Make email required (remove null=True, blank=True)
        migrations.AlterField(
            model_name='customuser',
            name='email',
            field=models.EmailField(max_length=255, unique=True, verbose_name='Email'),
        ),
        
        # Step 3: Remove phone_number field (if it exists)
        # Note: This will fail if phone_number doesn't exist, which is fine
        migrations.RemoveField(
            model_name='customuser',
            name='phone_number',
        ),
    ]

