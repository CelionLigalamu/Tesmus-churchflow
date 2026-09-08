from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from attendance.models import Attendance
from .models import Member
from .forms import MemberForm
from .services import generate_reference_number
from audit.services import log_action


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

    total_members = members.count()
    page_obj = Paginator(members, 25).get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)

    context = {
        'members': page_obj,
        'page_obj': page_obj,
        'query_params': query_params.urlencode(),
        'search_query': search_query,
        'status_filter': status_filter,
        'status_choices': Member.STATUS_CHOICES,
        'total_members': total_members,
    }
    return render(request, 'members/member_list.html', context)


@login_required
def member_create(request):
    if request.user.is_tesmus_staff or not request.user.church_id:
        return redirect('home')
    form = MemberForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        member = form.save(commit=False)
        member.church = request.user.church
        member.reference_number = generate_reference_number(member.church_id)
        member.save()
        log_action(request.user, 'member_created', church=member.church, details=f'{member.reference_number} - {member.full_name}')
        messages.success(request, f'{member.full_name} was registered successfully.')
        return redirect('member_detail', pk=member.pk)
    return render(request, 'members/member_form.html', {'form': form})


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
