from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import Service


@login_required
def service_list(request):
    status_filter = request.GET.get('status', '').strip()

    services = Service.objects.for_user(request.user).select_related(
        'region',
        'branch',
    ).order_by('-date', '-start_time', 'name')

    if status_filter in dict(Service.STATUS_CHOICES):
        services = services.filter(status=status_filter)

    return render(
        request,
        'services/service_list.html',
        {
            'services': services,
            'status_choices': Service.STATUS_CHOICES,
            'status_filter': status_filter,
            'total_services': services.count(),
        },
    )


@login_required
def service_detail(request, pk):
    service = get_object_or_404(
        Service.objects.for_user(request.user).select_related(
            'region',
            'branch',
            'created_by',
        ),
        pk=pk,
    )

    return render(request, 'services/service_detail.html', {'service': service})
