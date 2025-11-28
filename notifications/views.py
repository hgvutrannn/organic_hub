from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from .models import Notification


@login_required
@require_GET
def notification_list(request):
    """Return recent notifications for the authenticated user."""

    try:
        limit = int(request.GET.get('limit', 15))
    except (TypeError, ValueError):
        limit = 15

    notifications_qs = (
        request.user.notifications
        .select_related('order')
        .order_by('-created_at')[:max(limit, 1)]
    )

    notifications_data = [
        {
            'id': notification.id,
            'message': notification.message,
            'severity': notification.severity,
            'category': notification.category,
            'order_id': notification.order_id,
            'is_read': notification.is_read,
            'created_at': notification.created_at.isoformat(),
        }
        for notification in notifications_qs
    ]

    unread_count = request.user.notifications.filter(is_read=False).count()

    return JsonResponse(
        {
            'notifications': notifications_data,
            'unread_count': unread_count,
        }
    )


@login_required
@require_POST
def mark_notification_read(request, pk):
    """Mark a single notification as read."""

    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])

    return JsonResponse({'success': True})


@login_required
@require_POST
def mark_all_notifications_read(request):
    """Mark all user notifications as read."""

    updated = (
        request.user.notifications
        .filter(is_read=False)
        .update(is_read=True)
    )

    return JsonResponse({'success': True, 'updated': updated})

