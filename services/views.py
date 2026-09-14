from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Service
from .forms import ServiceForm
from .services import send_region_summaries, sync_and_finalize_service
from audit.services import log_action
from messaging.models import SMSMessage
from messaging.services import delivery_report, describe_delivery


@login_required
def service_list(request):
    status_filter = request.GET.get('status', '').strip()

    services = Service.objects.for_user(request.user).select_related(
        'region',
    ).order_by('-date', '-start_time', 'name')

    for service in services:
        sync_and_finalize_service(service)

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
            'created_by',
        ),
        pk=pk,
    )
    sync_and_finalize_service(service)

    return render(request, 'services/service_detail.html', {'service': service})


@login_required
@require_POST
def service_send_region_summaries(request, pk):
    """Text region pastors for a service that has already closed.

    Pastors are texted automatically when a service closes; this covers
    services that closed before their pastors were set up. Each pastor is
    still texted at most once per service.
    """
    if request.user.is_tesmus_staff or request.user.scope_type != 'church':
        messages.error(request, 'Only church-wide administrators can text region pastors.')
        return redirect('service_detail', pk=pk)

    service = get_object_or_404(Service.objects.for_user(request.user), pk=pk)
    sync_and_finalize_service(service)
    if service.status != 'finalized':
        messages.error(request, 'Region pastors can be texted once the service has closed.')
        return redirect('service_detail', pk=pk)

    already_texted = SMSMessage.objects.filter(dedupe_key__startswith=f'region-summary:{service.pk}:')
    before = already_texted.count()
    results = send_region_summaries(service)

    if not results:
        messages.warning(
            request,
            'No region pastors to text. Choose pastors on the Regions page, and check that '
            'the "Region attendance summary" message is switched on.',
        )
    elif already_texted.count() == before:
        messages.info(
            request,
            'These pastors were already texted for this service, and each pastor is texted '
            'only once. See Messages for how each text went.',
        )
    else:
        level, text = describe_delivery(delivery_report(results), noun='pastor')
        getattr(messages, level)(request, text)
        log_action(request.user, 'region_summaries_sent', church=service.church, details=service.name)
    return redirect('service_detail', pk=pk)
