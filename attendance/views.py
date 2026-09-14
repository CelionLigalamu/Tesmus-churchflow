from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from members.models import Member
from members.phones import members_with_phone, phone_key
from services.models import Service
from services.services import sync_and_finalize_service

from . import checkin
from .models import Attendance


@login_required
def service_list(request):
    services = Service.objects.for_user(request.user).select_related(
        'region',
    ).annotate(
        registered_count=Count('attendances'),
        present_count=Count('attendances', filter=Q(attendances__result='present')),
        absent_count=Count('attendances', filter=Q(attendances__result='absent')),
    ).order_by('-date', '-start_time', 'name')

    for service in services:
        sync_and_finalize_service(service)

    total_services = services.count()
    page_obj = Paginator(services, 25).get_page(request.GET.get('page'))
    service_rows = []
    for service in page_obj:
        marked_total = service.present_count + service.absent_count
        attendance_rate = round((service.present_count / marked_total) * 100, 1) if marked_total else 0
        service_rows.append({
            'service': service,
            'registered': service.registered_count,
            'present': service.present_count,
            'absent': service.absent_count,
            'attendance_rate': attendance_rate,
        })

    query_params = request.GET.copy()
    query_params.pop('page', None)
    return render(request, 'attendance/service_list.html', {
        'service_rows': service_rows,
        'page_obj': page_obj,
        'query_params': query_params.urlencode(),
        'total_services': total_services,
    })


@login_required
def service_detail(request, pk):
    service = get_object_or_404(
        Service.objects.for_user(request.user).select_related('region'),
        pk=pk,
    )
    sync_and_finalize_service(service)
    attendances = Attendance.objects.for_user(request.user).filter(
        service=service,
    ).select_related('member', 'visitor').order_by('member__full_name', 'visitor__full_name', 'checked_in_at')

    registered = attendances.count()
    present = attendances.filter(result='present').count()
    absent = attendances.filter(result='absent').count()
    unmarked = registered - present - absent
    marked_total = present + absent
    attendance_rate = round((present / marked_total) * 100, 1) if marked_total else 0
    page_obj = Paginator(attendances, 25).get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)

    return render(
        request,
        'attendance/service_detail.html',
        {
            'service': service,
            'attendances': page_obj,
            'page_obj': page_obj,
            'query_params': query_params.urlencode(),
            'registered': registered,
            'present': present,
            'absent': absent,
            'unmarked': unmarked,
            'attendance_rate': attendance_rate,
        },
    )


@csrf_protect
def qr_checkin(request, token):
    """The public page members open from the service QR code to check themselves in."""
    service = get_object_or_404(Service.objects.select_related('church'), qr_token=token)
    sync_and_finalize_service(service)
    device_id, is_new_device = checkin.device_id_for(request)
    context = {'service': service, 'church': service.church}

    if service.status != 'open':
        response = render(request, 'attendance/checkin_closed.html', context)
    else:
        outcome = None
        identifier = ''
        if request.method == 'POST':
            identifier = request.POST.get('identifier', '').strip()[:30]
            outcome = checkin.check_in(service, identifier, device_id, checkin.client_ip(request))
        context.update(outcome=outcome, identifier='' if outcome and outcome.succeeded else identifier)
        response = render(request, 'attendance/checkin.html', context)

    if is_new_device:
        checkin.remember_device(response, device_id, secure=request.is_secure())
    return response


# --- Usher check-in screen -------------------------------------------------

def can_use_usher_screen(user):
    """Ushers, and church-wide administrators, may check members in by hand."""
    return (
        user.is_authenticated and not user.is_tesmus_staff and bool(user.church_id)
        and (user.is_usher or user.scope_type == 'church')
    )


@login_required
def usher_home(request):
    """Today's services for the usher's church."""
    user = request.user
    if not can_use_usher_screen(user):
        if user.is_usher:
            return render(request, 'attendance/usher_home.html', {'services': [], 'no_church': True})
        messages.error(request, 'Only ushers and church-wide administrators can use the usher check-in screen.')
        return redirect('home')

    now = timezone.localtime()
    services = list(Service.objects.filter(church_id=user.church_id, date=now.date()).order_by('start_time', 'created_at'))
    for service in services:
        sync_and_finalize_service(service, now=now)
    return render(request, 'attendance/usher_home.html', {'services': services})


@login_required
def usher_service(request, pk):
    """Search a member and check them in to one of today's services."""
    if not can_use_usher_screen(request.user):
        return redirect('usher_home')
    service = get_object_or_404(Service, pk=pk, church_id=request.user.church_id)
    sync_and_finalize_service(service)

    query = request.GET.get('q', '').strip()[:100]
    searched = service.status == 'open' and len(query) >= 2
    results = []
    if searched:
        members = Member.objects.filter(church_id=service.church_id).select_related('region')
        if len(phone_key(query)) >= 9:
            matches = members_with_phone(members, query)
        else:
            matches = members.filter(Q(full_name__icontains=query) | Q(reference_number__iexact=query))
        matches = list(matches.order_by('full_name')[:20])
        checked_in = set(Attendance.objects.filter(service=service, member__in=matches).values_list('member_id', flat=True))
        results = [{'member': member, 'checked_in': member.pk in checked_in} for member in matches]

    check_ins = Attendance.objects.filter(service=service, member__isnull=False, result__in=['', 'present'])
    return render(request, 'attendance/usher_service.html', {
        'service': service,
        'query': query,
        'searched': searched,
        'results': results,
        'checked_in_count': check_ins.count(),
        'member_total': Member.objects.filter(church_id=service.church_id).count(),
        'recent': check_ins.select_related('member').order_by('-checked_in_at')[:10],
    })


@login_required
@require_POST
def usher_check_in(request, pk):
    if not can_use_usher_screen(request.user):
        return redirect('usher_home')
    service = get_object_or_404(Service, pk=pk, church_id=request.user.church_id)
    sync_and_finalize_service(service)

    query = request.POST.get('q', '').strip()[:100]
    back = reverse('usher_service', args=[service.pk])
    if query:
        back = f'{back}?{urlencode({"q": query})}'

    if service.status != 'open':
        messages.error(request, 'Check-in for this service is not open.')
        return redirect(back)

    member_id = request.POST.get('member', '')
    if not member_id.isdigit():
        raise Http404('Unknown member')
    member = get_object_or_404(Member, pk=member_id, church_id=service.church_id)
    _attendance, created = Attendance.objects.get_or_create(
        service=service, member=member,
        defaults={'church_id': service.church_id, 'method': 'usher', 'checked_in_by': request.user},
    )
    if created:
        messages.success(request, f'{member.full_name} is checked in.')
    else:
        messages.info(request, f'{member.full_name} was already checked in.')
    return redirect(back)
