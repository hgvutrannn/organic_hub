(() => {
  const dropdown = document.querySelector('[data-notification-dropdown]');
  if (!dropdown) {
    return;
  }

  const isAuthenticated = dropdown.dataset.auth === 'true';
  if (!isAuthenticated) {
    return;
  }

  const listUrl = dropdown.dataset.listUrl;
  const markReadTemplate = dropdown.dataset.markReadUrl;
  const markAllUrl = dropdown.dataset.markAllUrl;

  const listContainer = dropdown.querySelector('#notificationList');
  const badgeEl = dropdown.querySelector('#notificationBadge');
  const markAllBtn = dropdown.querySelector('#notificationsMarkAll');

  let notifications = [];
  let websocket;

  const maxVisible = parseInt(dropdown.dataset.limit || '15', 10);

  const fetchNotifications = async () => {
    try {
      const response = await fetch(listUrl, {
        credentials: 'same-origin',
      });
      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const data = await response.json();
      notifications = (data.notifications || []).map((item) => ({
        ...item,
        created_at: item.created_at,
      }));
      updateList();
      updateBadge(data.unread_count || getUnreadCount());
    } catch (error) {
      console.error('Không thể tải thông báo:', error);
    }
  };

  const updateList = () => {
    if (!listContainer) {
      return;
    }

    listContainer.innerHTML = '';

    if (!notifications.length) {
      listContainer.innerHTML = '<div class="text-center text-muted py-3">Không có thông báo</div>';
      return;
    }

    notifications.slice(0, maxVisible).forEach((notification) => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = `list-group-item list-group-item-action notification-item${notification.is_read ? '' : ' notification-item-unread'}`;
      item.dataset.id = String(notification.id);
      item.dataset.read = notification.is_read ? 'true' : 'false';
      item.innerHTML = `
        <div class="d-flex justify-content-between">
          <span class="me-3">${escapeHtml(notification.message)}</span>
          <small class="text-muted flex-shrink-0">${formatTimestamp(notification.created_at)}</small>
        </div>
      `;
      listContainer.appendChild(item);
    });
  };

  const updateBadge = (count) => {
    if (!badgeEl) {
      return;
    }

    if (count > 0) {
      badgeEl.textContent = count > 9 ? '9+' : String(count);
      badgeEl.hidden = false;
    } else {
      badgeEl.hidden = true;
    }

    if (markAllBtn) {
      markAllBtn.disabled = count === 0;
    }
  };

  const buildMarkReadUrl = (notificationId) => {
    return markReadTemplate.replace(/\/0\//, `/${notificationId}/`);
  };

  const markNotificationRead = async (notificationId) => {
    const target = notifications.find((item) => item.id === notificationId);
    if (!target || target.is_read) {
      return;
    }

    try {
      const response = await fetch(buildMarkReadUrl(notificationId), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        credentials: 'same-origin',
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      target.is_read = true;
      updateList();
      updateBadge(getUnreadCount());
    } catch (error) {
      console.error('Không thể đánh dấu thông báo đã đọc:', error);
    }
  };

  const markAllNotificationsRead = async () => {
    try {
      const response = await fetch(markAllUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        credentials: 'same-origin',
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      notifications = notifications.map((item) => ({ ...item, is_read: true }));
      updateList();
      updateBadge(0);
    } catch (error) {
      console.error('Không thể đánh dấu tất cả thông báo đã đọc:', error);
    }
  };

  const connectWebSocket = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const socketUrl = `${protocol}://${window.location.host}/ws/notifications/`;
    websocket = new WebSocket(socketUrl);

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (!data || !data.id) {
          return;
        }
        notifications.unshift({
          ...data,
          is_read: data.is_read ?? false,
        });
        updateList();
        updateBadge(getUnreadCount());
      } catch (error) {
        console.error('Không thể xử lý thông báo realtime:', error);
      }
    };

    websocket.onclose = () => {
      setTimeout(connectWebSocket, 5000);
    };
  };

  const handleListClick = (event) => {
    const target = event.target.closest('.notification-item');
    if (!target) {
      return;
    }

    const notificationId = parseInt(target.dataset.id, 10);
    if (!Number.isInteger(notificationId)) {
      return;
    }

    markNotificationRead(notificationId);
  };

  const bindEvents = () => {
    if (listContainer) {
      listContainer.addEventListener('click', handleListClick);
    }

    if (markAllBtn) {
      markAllBtn.addEventListener('click', markAllNotificationsRead);
    }
  };

  const escapeHtml = (unsafe) => {
    return String(unsafe)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  };

  const formatTimestamp = (isoDate) => {
    try {
      const date = new Date(isoDate);
      if (Number.isNaN(date.getTime())) {
        return '';
      }
      return date.toLocaleString('vi-VN', {
        hour: '2-digit',
        minute: '2-digit',
        day: '2-digit',
        month: '2-digit',
      });
    } catch (error) {
      return '';
    }
  };

  const getCsrfToken = () => {
    const cookieValue = document.cookie
      .split('; ')
      .find((row) => row.startsWith('csrftoken='));
    return cookieValue ? decodeURIComponent(cookieValue.split('=')[1]) : '';
  };

  const getUnreadCount = () => notifications.filter((item) => !item.is_read).length;

  bindEvents();
  fetchNotifications();
  connectWebSocket();
})();
