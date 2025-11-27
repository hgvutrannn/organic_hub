"""
Elasticsearch documents for Product model
"""
from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from core.models import Product


@registry.register_document
class ProductDocument(Document):
    """
    Elasticsearch document for Product model
    Field boosting: name^3 (name is 3x more important than description)
    """
    name = fields.TextField(
        analyzer='standard',
        fields={'raw': fields.KeywordField()}
    )
    description = fields.TextField(
        analyzer='standard'
    )
    price = fields.FloatField()
    category_id = fields.IntegerField()
    category_name = fields.KeywordField()
    store_id = fields.IntegerField()
    store_name = fields.KeywordField()
    certification_organization_ids = fields.KeywordField(multi=True)  # Multi-value field
    is_active = fields.BooleanField()
    created_at = fields.DateField()
    view_count = fields.IntegerField()

    class Index:
        name = 'products'
        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 0,
        }

    class Django:
        model = Product
        fields = [
            'product_id',
        ]
        related_models = []

    def get_queryset(self):
        """Return queryset to be indexed"""
        return super().get_queryset().select_related('category', 'store')

    def prepare_product_id(self, instance):
        """Prepare product_id field"""
        return instance.product_id

    def prepare_name(self, instance):
        """Prepare name field"""
        return instance.name

    def prepare_description(self, instance):
        """Prepare description field"""
        return instance.description or ''

    def prepare_price(self, instance):
        """Prepare price field"""
        return float(instance.price)

    def prepare_category_id(self, instance):
        """Prepare category_id field"""
        return instance.category.category_id if instance.category else None

    def prepare_category_name(self, instance):
        """Prepare category_name field"""
        return instance.category.name if instance.category else None

    def prepare_store_id(self, instance):
        """Prepare store_id field"""
        return instance.store.store_id

    def prepare_store_name(self, instance):
        """Prepare store_name field"""
        return instance.store.store_name

    # THÊM METHOD NÀY
    def prepare_certification_organization_ids(self, instance):
        """
        Prepare certification_organization_ids field
        Lấy tất cả certification_organization_id từ Store của Product
        """
        certification_ids = []
        store = instance.store
        
        # Lấy tất cả StoreVerificationRequest của Store
        verification_requests = store.verification_requests.all()
        
        for request in verification_requests:
            # Lấy tất cả StoreCertification của request
            certifications = request.certifications.all()
            for cert in certifications:
                # Chỉ lấy certification_organization_id nếu có và chưa tồn tại trong list
                if cert.certification_organization and cert.certification_organization.organization_id not in certification_ids:
                    certification_ids.append(cert.certification_organization.organization_id)
        
        return certification_ids
        
    def prepare_is_active(self, instance):
        """Prepare is_active field"""
        return instance.is_active

    def prepare_created_at(self, instance):
        """Prepare created_at field"""
        return instance.created_at

    def prepare_view_count(self, instance):
        """Prepare view_count field"""
        return instance.view_count

