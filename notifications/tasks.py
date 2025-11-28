from __future__ import annotations

from typing import Iterable, Optional

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.utils.translation import gettext_lazy as _

from .models import Notification


@shared_task(name='notifications.create_order_status_notifications')
def create_order_status_notifications(order_id: int, new_status: str, triggered_by_id: Optional[int] = None) -> None:
    """Persist notifications for an order status change.

    This task is intentionally lightweight so it can be chained with
    realtime broadcasting (implemented in a subsequent step).
    """

    from core.models import Order  # Imported lazily to avoid circular imports

    try:
        order = Order.objects.select_related('user').get(pk=order_id)
    except Order.DoesNotExist:
        return

    severity = _status_to_severity(new_status)
    status_display = order.get_status_display()

    # Determine recipient set (buyer + involved sellers)
    recipient_ids = set(_get_order_recipient_ids(order))
    if triggered_by_id:
        recipient_ids.discard(triggered_by_id)

    if not recipient_ids:
        return

    message_template = _('Đơn hàng #{order_id} đã chuyển sang trạng thái "{status}".')
    message = message_template.format(order_id=order.order_id, status=status_display)

    channel_layer = get_channel_layer()

    for recipient_id in recipient_ids:
        notification = Notification.objects.create(
            recipient_id=recipient_id,
            order=order,
            category=Notification.CATEGORY_ORDER_STATUS,
            severity=severity,
            message=message,
        )

        if channel_layer is None:
            continue

        payload = {
            'id': notification.id,
            'message': notification.message,
            'category': notification.category,
            'severity': notification.severity,
            'order_id': notification.order_id,
            'created_at': notification.created_at.isoformat(),
            'is_read': notification.is_read,
        }

        async_to_sync(channel_layer.group_send)(
            f'notifications_{recipient_id}',
            {
                'type': 'notification.message',
                'payload': payload,
            },
        )


def _get_order_recipient_ids(order: 'Order') -> Iterable[int]:
    """Collect recipient user IDs for a given order."""

    recipient_ids = {order.user_id}
    seller_ids = order.order_items.values_list('product__store__user_id', flat=True)
    recipient_ids.update(filter(None, seller_ids))
    return recipient_ids


def _status_to_severity(status: str) -> str:
    mapping = {
        'pending': Notification.SEVERITY_INFO,
        'waiting_pickup': Notification.SEVERITY_WARNING,
        'shipping': Notification.SEVERITY_WARNING,
        'delivered': Notification.SEVERITY_SUCCESS,
        'cancelled': Notification.SEVERITY_ERROR,
    }
    return mapping.get(status, Notification.SEVERITY_INFO)
