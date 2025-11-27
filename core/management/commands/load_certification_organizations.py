from django.core.management.base import BaseCommand
from core.models import CertificationOrganization


class Command(BaseCommand):
    help = 'Load initial certification organizations data'

    def handle(self, *args, **options):
        organizations_data = [
            {
                'name': 'Soil Association Certification Ltd',
                'abbreviation': 'SA',
                'description': 'Soil Association is the UK\'s leading organic certification body.',
                'website': 'https://www.soilassociation.org/',
                'is_active': True,
            },
            {
                'name': 'Organic Farmers & Growers CIC',
                'abbreviation': 'OF&G',
                'description': 'Organic Farmers & Growers is a leading UK organic certification body.',
                'website': 'https://ofgorganic.org/',
                'is_active': True,
            },
            {
                'name': 'Organic Food Federation',
                'abbreviation': 'OFF',
                'description': 'The Organic Food Federation is a UK-based organic certification body.',
                'website': 'https://www.organicfoodfederation.co.uk/',
                'is_active': True,
            },
            {
                'name': 'Biodynamic Association Certification',
                'abbreviation': 'BDA',
                'description': 'Biodynamic Association Certification (often accompanied by Demeter label).',
                'website': 'https://www.biodynamic.org.uk/',
                'is_active': True,
            },
            {
                'name': 'Quality Welsh Food Certification Ltd',
                'abbreviation': 'QWFC',
                'description': 'Quality Welsh Food Certification Ltd provides organic certification services.',
                'website': 'https://www.qwfc.co.uk/',
                'is_active': True,
            },
            {
                'name': 'OF&G (Scotland) Ltd',
                'abbreviation': 'OF&G Scotland',
                'description': 'OF&G (Scotland) Ltd is the Scottish branch of Organic Farmers & Growers.',
                'website': 'https://ofgorganic.org/',
                'is_active': True,
            },
            {
                'name': 'Irish Organic Association',
                'abbreviation': 'IOA',
                'description': 'The Irish Organic Association is Ireland\'s leading organic certification body.',
                'website': 'https://www.irishorganicassociation.ie/',
                'is_active': True,
            },
            {
                'name': 'Global Trust Certification Ltd',
                'abbreviation': 'GTC',
                'description': 'Global Trust Certification Ltd provides organic and food safety certification services.',
                'website': 'https://www.globaltrustcert.com/',
                'is_active': True,
            },
        ]

        created_count = 0
        updated_count = 0

        for org_data in organizations_data:
            org, created = CertificationOrganization.objects.update_or_create(
                abbreviation=org_data['abbreviation'],
                defaults={
                    'name': org_data['name'],
                    'description': org_data['description'],
                    'website': org_data['website'],
                    'is_active': org_data['is_active'],
                }
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created: {org.name} ({org.abbreviation})')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'↻ Updated: {org.name} ({org.abbreviation})')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Successfully loaded {len(organizations_data)} organizations '
                f'({created_count} created, {updated_count} updated)'
            )
        )

