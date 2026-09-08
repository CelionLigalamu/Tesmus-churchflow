from django.contrib.auth.decorators import login_required
from django.contrib import messages as flash_messages
from django.db.models import Count
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from .models import SMSMessage
from .audience import get_recipients, user_can_send_to
from .services import send_bulk
from members.models import Member
from services.models import Service
from tenants.models import Branch, Region


@login_required
def message_list(request):
    status_filter = request.GET.get('status', '').strip()

    all_messages = SMSMessage.objects.for_user(request.user).select_related(
        'template',
    ).order_by('-created_at')
    status_totals = {status: 0 for status, _ in SMSMessage.STATUS_CHOICES}
    for row in all_messages.values('status').annotate(total=Count('id')):
        status_totals[row['status']] = row['total']

    sent_messages = all_messages

    if status_filter in dict(SMSMessage.STATUS_CHOICES):
        sent_messages = sent_messages.filter(status=status_filter)

    total_messages = sent_messages.count()
    page_obj = Paginator(sent_messages, 25).get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)

    return render(
        request,
        'messaging/message_list.html',
        {
            'sent_messages': page_obj,
            'page_obj': page_obj,
            'query_params': query_params.urlencode(),
            'status_choices': SMSMessage.STATUS_CHOICES,
            'status_filter': status_filter,
            'total_messages': total_messages,
            'total_recipients': sum(status_totals.values()),
            'sent_count': status_totals['sent'],
            'delivered_count': status_totals['delivered'],
            'failed_count': status_totals['failed'],
        },
    )


@login_required
def message_create(request):
    if request.user.is_tesmus_staff or not request.user.church_id:
        return redirect('home')
    regions = Region.objects.filter(church=request.user.church).order_by('name')
    branches = Branch.objects.filter(church=request.user.church).select_related('region').order_by('name')
    services = Service.objects.filter(church=request.user.church).order_by('-date', '-start_time')[:30]
    if request.user.scope_type == 'region' and request.user.scope_region_id:
        regions = regions.filter(pk=request.user.scope_region_id)
        branches = branches.filter(region_id=request.user.scope_region_id)
        services = services.filter(region_id=request.user.scope_region_id)
    elif request.user.scope_type == 'branch' and request.user.scope_branch_id:
        branches = branches.filter(pk=request.user.scope_branch_id)
        services = services.filter(branch_id=request.user.scope_branch_id)

    if request.method == 'POST':
        audience_type = request.POST.get('audience_type', 'church')
        region = regions.filter(pk=request.POST.get('region')).first() if request.POST.get('region') else None
        branch = branches.filter(pk=request.POST.get('branch')).first() if request.POST.get('branch') else None
        service = services.filter(pk=request.POST.get('service')).first() if request.POST.get('service') else None
        if audience_type == 'visitor_present':
            if request.user.scope_type == 'region' and request.user.scope_region_id:
                region = regions.filter(pk=request.user.scope_region_id).first()
            elif request.user.scope_type == 'branch' and request.user.scope_branch_id:
                branch = branches.filter(pk=request.user.scope_branch_id).first()
        body = request.POST.get('body', '').strip()
        if not body:
            flash_messages.error(request, 'Write a message before sending.')
        elif not user_can_send_to(request.user, audience_type, region=region, branch=branch):
            flash_messages.error(request, 'You do not have permission to message that audience.')
        else:
            recipients = get_recipients(request.user.church, audience_type, region=region, branch=branch, service=service)
            if audience_type in {'service_present', 'service_absent', 'visitor_present'} and not service:
                recipients = Member.objects.none()
            if not recipients.exists():
                flash_messages.error(request, 'No recipients match that audience.')
            else:
                send_bulk(request.user.church, recipients, body)
                flash_messages.success(request, f'Message queued for {recipients.count()} recipient(s).')
                return redirect('message_list')
    return render(request, 'messaging/message_form.html', {'regions': regions, 'branches': branches, 'services': services})


@login_required
def message_detail(request, pk):
    message = get_object_or_404(
        SMSMessage.objects.for_user(request.user).select_related('template'),
        pk=pk,
    )

    return render(request, 'messaging/message_detail.html', {'message': message})
