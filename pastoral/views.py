from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from audit.services import log_action

from .forms import AbsenceAlertSettingForm, FollowUpUpdateForm
from .models import PastoralFollowUp

OPEN = PastoralFollowUp.OPEN_STATUSES


def visible_followups(user):
    """Church-wide admins see every follow-up; region leaders see their region's."""
    followups = PastoralFollowUp.objects.for_user(user)
    if not user.is_tesmus_staff and user.scope_type == 'region':
        if user.scope_region_id:
            followups = followups.filter(Q(member__region_id=user.scope_region_id) | Q(assigned_to=user))
        else:
            followups = followups.filter(assigned_to=user)
    return followups


def can_update_followups(user):
    """Church leaders who can see a follow-up may record progress on it."""
    return (
        user.is_authenticated
        and not user.is_tesmus_staff
        and not getattr(user, 'is_usher', False)
        and bool(user.church_id)
        and user.scope_type in ('church', 'region')
    )


def can_change_alert_setting(user):
    return can_update_followups(user) and user.scope_type == 'church'


@login_required
def followup_list(request):
    status_filter = request.GET.get('status', '').strip()
    visible = visible_followups(request.user)
    needs_pastor = visible.filter(status__in=OPEN, reason=PastoralFollowUp.MISSED_SERVICES, pastors__isnull=True)

    followups = visible.select_related('member', 'member__region', 'assigned_to').prefetch_related('pastors').annotate(
        open_first=Case(When(status__in=OPEN, then=Value(0)), default=Value(1), output_field=IntegerField()),
    ).order_by('open_first', '-created_at')
    if status_filter == 'needs_pastor':
        followups = followups.filter(pk__in=needs_pastor.values('pk'))
    elif status_filter in dict(PastoralFollowUp.STATUS_CHOICES):
        followups = followups.filter(status=status_filter)

    church = request.user.church
    return render(
        request,
        'pastoral/followup_list.html',
        {
            'followups': followups,
            'status_choices': PastoralFollowUp.STATUS_CHOICES,
            'status_filter': status_filter,
            'total_followups': followups.count(),
            'open_count': visible.filter(status__in=OPEN).count(),
            'needs_pastor_count': needs_pastor.count(),
            'returned_count': visible.filter(status='returned').count(),
            'church': church,
            'setting_form': AbsenceAlertSettingForm(instance=church) if can_change_alert_setting(request.user) else None,
        },
    )


@login_required
@require_POST
def absence_alert_setting(request):
    """The church chooses how many services in a row count as 'stopped coming'."""
    if not can_change_alert_setting(request.user):
        messages.error(request, 'Only church-wide administrators can change when pastors are alerted.')
        return redirect('pastoral_followup_list')
    form = AbsenceAlertSettingForm(request.POST, instance=request.user.church)
    if not form.is_valid():
        messages.error(request, 'Enter a number from 0 to 20.')
        return redirect('pastoral_followup_list')
    church = form.save()
    count = church.absence_alert_after
    log_action(request.user, 'absence_alert_setting_changed', church=church, details=f'Alert after {count} missed services')
    if count:
        messages.success(request, f"Pastors will be alerted when a member misses {count} services in a row.")
    else:
        messages.success(request, 'Absence alerts are off. No new follow-ups will be opened automatically.')
    return redirect('pastoral_followup_list')


@login_required
def followup_detail(request, pk):
    followup = get_object_or_404(
        visible_followups(request.user).select_related(
            'member', 'member__region', 'assigned_to', 'trigger_service',
        ).prefetch_related('pastors'),
        pk=pk,
    )
    update_form = None
    if can_update_followups(request.user):
        update_form = FollowUpUpdateForm(initial={'status': followup.status})
    return render(request, 'pastoral/followup_detail.html', {
        'followup': followup,
        'update_form': update_form,
        'can_manage_regions': can_change_alert_setting(request.user),
    })


@login_required
@require_POST
def followup_update(request, pk):
    """Change the status and add a dated note, keeping the full history."""
    followup = get_object_or_404(visible_followups(request.user).select_related('member'), pk=pk)
    if not can_update_followups(request.user):
        messages.error(request, 'You cannot update pastoral follow-ups.')
        return redirect('pastoral_followup_detail', pk=pk)
    form = FollowUpUpdateForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Choose a status and keep the note under 2000 characters.')
        return redirect('pastoral_followup_detail', pk=pk)

    new_status = form.cleaned_data['status']
    note = form.cleaned_data['note'].strip()
    if new_status == followup.status and not note:
        messages.info(request, 'Nothing to save: choose a new status or write a note.')
        return redirect('pastoral_followup_detail', pk=pk)

    author = request.user.get_full_name() or request.user.username
    statuses = dict(PastoralFollowUp.STATUS_CHOICES)
    if new_status != followup.status:
        followup.add_note(f'Status changed from {statuses[followup.status]} to {statuses[new_status]}.', author)
        followup.closed_at = None if new_status in OPEN else timezone.now()
    if note:
        followup.add_note(note, author)
    followup.status = new_status
    try:
        with transaction.atomic():
            followup.save(update_fields=['status', 'notes', 'closed_at'])
    except IntegrityError:
        messages.error(request, 'This member already has another open follow-up for missed services. Close that one first.')
        return redirect('pastoral_followup_detail', pk=pk)

    log_action(request.user, 'pastoral_followup_updated', church=followup.church,
               details=f'{followup.member.reference_number} - {statuses[new_status]}')
    messages.success(request, 'Follow-up updated.')
    return redirect('pastoral_followup_detail', pk=pk)
