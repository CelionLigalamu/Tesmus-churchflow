from django.db import models
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_protect
from services.models import Service
from members.models import Member
from .models import Attendance


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