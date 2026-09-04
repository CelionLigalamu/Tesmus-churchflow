from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Count, Q
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_protect
from services.models import Service
from members.models import Member
from .models import Attendance


@login_required
def service_list(request):
    services = Service.objects.for_user(request.user).select_related(
        'region',
        'branch',
    ).annotate(
        registered_count=Count('attendances'),
        present_count=Count('attendances', filter=Q(attendances__result='present')),
        absent_count=Count('attendances', filter=Q(attendances__result='absent')),
    ).order_by('-date', '-start_time', 'name')

    service_rows = []
    for service in services:
        marked_total = service.present_count + service.absent_count
        attendance_rate = round((service.present_count / marked_total) * 100, 1) if marked_total else 0
        service_rows.append({
            'service': service,
            'registered': service.registered_count,
            'present': service.present_count,
            'absent': service.absent_count,
            'attendance_rate': attendance_rate,
        })

    return render(request, 'attendance/service_list.html', {'service_rows': service_rows})


@login_required
def service_detail(request, pk):
    service = get_object_or_404(
        Service.objects.for_user(request.user).select_related('region', 'branch'),
        pk=pk,
    )
    attendances = Attendance.objects.for_user(request.user).filter(
        service=service,
    ).select_related('member', 'visitor').order_by('member__full_name', 'visitor__full_name', 'checked_in_at')

    registered = attendances.count()
    present = attendances.filter(result='present').count()
    absent = attendances.filter(result='absent').count()
    unmarked = registered - present - absent
    marked_total = present + absent
    attendance_rate = round((present / marked_total) * 100, 1) if marked_total else 0

    return render(
        request,
        'attendance/service_detail.html',
        {
            'service': service,
            'attendances': attendances,
            'registered': registered,
            'present': present,
            'absent': absent,
            'unmarked': unmarked,
            'attendance_rate': attendance_rate,
        },
    )


@csrf_protect
def qr_checkin(request, token):
    service = get_object_or_404(Service, qr_token=token)

    if service.status != 'open':
        return render(request, 'attendance/checkin_closed.html', {'service': service})

    message = None

    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        member = Member.objects.filter(
            church_id=service.church_id
        ).filter(
            models.Q(reference_number__iexact=identifier) | models.Q(phone_number=identifier)
        ).first()

        if not member:
            message = "Member not found. Please check your ID or phone number."
        else:
            existing = Attendance.objects.filter(service=service, member=member).exists()
            if existing:
                message = "Your attendance has already been recorded."
            else:
                Attendance.objects.create(
                    church=service.church,
                    service=service,
                    member=member,
                    method='qr',
                )
                message = f"Thank you, {member.full_name}! Attendance recorded."

    return render(request, 'attendance/checkin.html', {'service': service, 'message': message})
