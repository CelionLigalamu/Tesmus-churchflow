from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import SMSMessage


@login_required
def message_list(request):
    status_filter = request.GET.get('status', '').strip()

    messages = SMSMessage.objects.for_user(request.user).select_related(
        'template',
    ).order_by('-created_at')

    if status_filter in dict(SMSMessage.STATUS_CHOICES):
        messages = messages.filter(status=status_filter)

    return render(
        request,
        'messaging/message_list.html',
        {
            'messages': messages,
            'status_choices': SMSMessage.STATUS_CHOICES,
            'status_filter': status_filter,
            'total_messages': messages.count(),
        },
    )


@login_required
def message_detail(request, pk):
    message = get_object_or_404(
        SMSMessage.objects.for_user(request.user).select_related('template'),
        pk=pk,
    )

    return render(request, 'messaging/message_detail.html', {'message': message})
