from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import PastoralFollowUp


@login_required
def followup_list(request):
    status_filter = request.GET.get('status', '').strip()

    followups = PastoralFollowUp.objects.for_user(request.user).select_related(
        'member',
        'assigned_to',
    ).order_by('follow_up_date', '-created_at')

    if status_filter in dict(PastoralFollowUp.STATUS_CHOICES):
        followups = followups.filter(status=status_filter)

    return render(
        request,
        'pastoral/followup_list.html',
        {
            'followups': followups,
            'status_choices': PastoralFollowUp.STATUS_CHOICES,
            'status_filter': status_filter,
            'total_followups': followups.count(),
        },
    )


@login_required
def followup_detail(request, pk):
    followup = get_object_or_404(
        PastoralFollowUp.objects.for_user(request.user).select_related(
            'member',
            'assigned_to',
        ),
        pk=pk,
    )

    return render(request, 'pastoral/followup_detail.html', {'followup': followup})
