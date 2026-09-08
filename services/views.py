from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from .models import Service
from .forms import ServiceForm
from audit.services import log_action


@login_required
def service_list(request):
    status_filter = request.GET.get('status', '').strip()

    services = Service.objects.for_user(request.user).select_related(
        'region',
        'branch',
    ).order_by('-date', '-start_time', 'name')

    if status_filter in dict(Service.STATUS_CHOICES):
        services = services.filter(status=status_filter)

    total_services = services.count()
    page_obj = Paginator(services, 25).get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)

    return render(
        request,
        'services/service_list.html',
        {
            'services': page_obj,
            'page_obj': page_obj,
            'query_params': query_params.urlencode(),
            'status_choices': Service.STATUS_CHOICES,
            'status_filter': status_filter,
            'total_services': total_services,
        },
    )


@login_required
def service_create(request):
    if request.user.is_tesmus_staff or not request.user.church_id:
        return redirect('home')
    form = ServiceForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        service = form.save(commit=False)
        service.church = request.user.church
        service.created_by = request.user
        service.save()
        log_action(request.user, 'service_created', church=service.church, details=service.name)
        messages.success(request, f'{service.name} was scheduled successfully.')
        return redirect('service_detail', pk=service.pk)
    return render(request, 'services/service_form.html', {'form': form})


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
