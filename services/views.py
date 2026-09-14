import uuid

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Service
from .forms import ServiceForm
from .services import finalize_service, send_region_summaries, sync_and_finalize_service
from attendance.qr import qr_svg
from audit.services import log_action
from messaging.models import SMSMessage
from messaging.services import delivery_report, describe_delivery


def can_manage_service_checkin(user):
    """Church-wide administrators may change a service's check-in link or close it early."""
    return user.is_authenticated and not user.is_tesmus_staff and bool(user.church_id) and user.scope_type == 'church'


def checkin_url_for(request, service):
    return request.build_absolute_uri(reverse('qr_checkin', args=[service.qr_token]))


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

    context = {'service': service, 'can_manage_checkin': can_manage_service_checkin(request.user)}
    if service.status in ('upcoming', 'open'):
        checkin_url = checkin_url_for(request, service)
        context.update(checkin_url=checkin_url, checkin_qr_svg=qr_svg(checkin_url, scale=5))
    return render(request, 'services/service_detail.html', context)


@login_required
def service_checkin_poster(request, pk):
    """A printable page with the service's check-in QR code."""
    service = get_object_or_404(Service.objects.for_user(request.user).select_related('church'), pk=pk)
    sync_and_finalize_service(service)
    checkin_url = checkin_url_for(request, service)
    return render(request, 'services/checkin_poster.html', {
        'service': service,
        'checkin_url': checkin_url,
        'checkin_qr_svg': qr_svg(checkin_url, scale=10),
        'is_closed': service.status in ('closed', 'finalized'),
    })


@login_required
@require_POST
def service_new_checkin_link(request, pk):
    """Replace the check-in link, for example when it was shared outside church."""
    if not can_manage_service_checkin(request.user):
        messages.error(request, 'Only church-wide administrators can change the check-in link.')
        return redirect('service_detail', pk=pk)
    service = get_object_or_404(Service.objects.for_user(request.user), pk=pk)
    service.qr_token = uuid.uuid4()
    service.save(update_fields=['qr_token'])
    log_action(request.user, 'checkin_link_replaced', church=service.church, details=service.name)
    messages.success(request, 'A new check-in link was created. The old link and any printed QR posters no longer work.')
    return redirect('service_detail', pk=pk)


@login_required
@require_POST
def service_close_now(request, pk):
    """Close an open service early: mark absentees, send attendance texts, text pastors."""
    if not can_manage_service_checkin(request.user):
        messages.error(request, 'Only church-wide administrators can close a service early.')
        return redirect('service_detail', pk=pk)
    service = get_object_or_404(Service.objects.for_user(request.user), pk=pk)
    sync_and_finalize_service(service)
    if service.status == 'finalized':
        messages.info(request, 'This service has already closed.')
    elif service.status != 'open':
        messages.error(request, 'Only a service that is open for check-in can be closed early.')
    else:
        finalize_service(service)
        log_action(request.user, 'service_closed_early', church=service.church, details=service.name)
        messages.success(
            request,
            'The service is closed. Members who did not check in are marked absent, attendance texts '
            'are being sent, and region pastors will be texted.',
        )
    return redirect('service_detail', pk=pk)


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
