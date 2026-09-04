from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from attendance.models import Attendance
from .models import Member


@login_required
def member_list(request):
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    members = Member.objects.for_user(request.user).select_related(
        'region',
        'branch',
    ).order_by('full_name', 'reference_number')

    if search_query:
        members = members.filter(
            Q(full_name__icontains=search_query)
            | Q(reference_number__icontains=search_query)
        )

    if status_filter in dict(Member.STATUS_CHOICES):
        members = members.filter(status=status_filter)

    context = {
        'members': members,
        'search_query': search_query,
        'status_filter': status_filter,
        'status_choices': Member.STATUS_CHOICES,
        'total_members': members.count(),
    }
    return render(request, 'members/member_list.html', context)


@login_required
def member_detail(request, pk):
    member = get_object_or_404(
        Member.objects.for_user(request.user).select_related('region', 'branch'),
        pk=pk,
    )
    attendance_history = Attendance.objects.for_user(request.user).filter(
        member=member,
    ).select_related('service').order_by('-service__date', '-checked_in_at')

    return render(
        request,
        'members/member_detail.html',
        {
            'member': member,
            'attendance_history': attendance_history,
        },
    )
