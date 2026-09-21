from django.contrib.auth.decorators import login_required
from django.contrib import messages as flash_messages
from django.db.models import Count
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from audit.services import log_action
from .models import SMSMessage, SMSTemplate
from .audience import get_recipients, user_can_send_to
from .failure_reasons import plain_failure_reason
from .forms import SMSTemplateForm
from .resend import MAX_RESEND_BATCH, can_resend_messages, resend_in_background, resend_now
from .services import delivery_report, describe_delivery, send_bulk
from .services import SYSTEM_TEMPLATES, ensure_system_templates
from members.models import Member
from members.services import ensure_default_ministry_roles
from services.models import Service
from tenants.models import Region


def can_manage_templates(user):
    return (
        user.is_authenticated
        and not user.is_tesmus_staff
        and bool(user.church_id)
        and user.scope_type == 'church'
    )


@login_required
def message_list(request):
    status_filter = request.GET.get('status', '').strip()

    all_messages = SMSMessage.objects.for_user(request.user).select_related(
        'template',
    ).order_by('-created_at')
    status_totals = count_by_status(all_messages)

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
            'can_resend': can_resend_messages(request.user),
        },
    )


def count_by_status(messages):
    totals = {status: 0 for status, _ in SMSMessage.STATUS_CHOICES}
    # order_by() clears the date ordering: left in place, Django groups by
    # status *and* send time, so each message becomes its own group of one.
    for row in messages.order_by().values('status').annotate(total=Count('id')):
        totals[row['status']] = row['total']
    return totals


def _return_to(request, fallback):
    """Where to go after a resend: the page it was started from, if it is ours."""
    next_url = request.POST.get('next', '')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        return next_url
    return fallback


@login_required
@require_POST
def message_resend(request, pk):
    """Resend one failed text now and report straight away whether it went."""
    message = get_object_or_404(SMSMessage.objects.for_user(request.user), pk=pk)
    return_to = _return_to(request, reverse('message_detail', args=[pk]))
    if not can_resend_messages(request.user):
        flash_messages.error(request, 'Only church-wide administrators can resend text messages.')
        return redirect(return_to)
    if not message.can_resend:
        if message.status in ('sent', 'delivered'):
            flash_messages.info(request, f'The text to {message.recipient_phone} was already sent, so it was not sent again.')
        else:
            flash_messages.info(request, f'The text to {message.recipient_phone} is already being sent. Its status will update shortly.')
        return redirect(return_to)

    result = resend_now(message)
    if result is None:
        flash_messages.info(request, f'The text to {message.recipient_phone} is already being sent. Its status will update shortly.')
        return redirect(return_to)
    log_action(request.user, 'sms_resent', church=result.church,
               details=f'{result.recipient_phone} - {result.get_status_display()} (attempt {result.attempt_count})')
    if result.status == 'sent':
        flash_messages.success(request, f'Text resent to {result.recipient_phone}.')
    else:
        flash_messages.error(
            request,
            f'The text to {result.recipient_phone} failed again. {plain_failure_reason(result.failure_reason)}',
        )
    return redirect(return_to)


@login_required
@require_POST
def message_resend_many(request):
    """Resend the ticked failed texts, or every failed text, in the background."""
    return_to = _return_to(request, reverse('message_list'))
    if not can_resend_messages(request.user):
        flash_messages.error(request, 'Only church-wide administrators can resend text messages.')
        return redirect(return_to)

    church_messages = SMSMessage.objects.for_user(request.user)
    if request.POST.get('scope') == 'all_failed':
        chosen = church_messages
    else:
        ids = [int(value) for value in request.POST.getlist('message') if value.isdigit()]
        if not ids:
            flash_messages.error(request, 'Tick the failed texts you want to resend.')
            return redirect(return_to)
        chosen = church_messages.filter(pk__in=ids)

    claimed = resend_in_background(chosen)
    if not claimed:
        flash_messages.info(request, 'There were no failed texts to resend.')
        return redirect(return_to)

    count = len(claimed)
    log_action(request.user, 'sms_resent', church=request.user.church, details=f'{count} failed text(s) queued to resend')
    note = f'{count} text{"s are" if count != 1 else " is"} being resent. Each status updates on this page as it is sent.'
    if count == MAX_RESEND_BATCH:
        note += ' Resend again for any that are left.'
    flash_messages.success(request, note)
    return redirect(return_to)


@login_required
def message_status(request):
    """Live status of the listed texts, so the page can switch Sending… to Sent or Failed."""
    ids = [int(value) for value in request.GET.get('ids', '').split(',') if value.strip().isdigit()][:100]
    church_messages = SMSMessage.objects.for_user(request.user)
    rows = church_messages.filter(pk__in=ids)
    totals = count_by_status(church_messages)
    return JsonResponse({
        'messages': {
            str(message.pk): {
                'status': message.status,
                'label': message.status_label,
                'css': message.status_css,
                'sending': message.is_sending,
                'can_resend': message.can_resend,
            }
            for message in rows
        },
        'totals': {'recipients': sum(totals.values()), **totals},
    })


@login_required
def message_create(request):
    if request.user.is_tesmus_staff or not request.user.church_id:
        return redirect('home')
    regions = Region.objects.filter(church=request.user.church).order_by('name')
    # Kept unsliced: Django cannot filter a queryset after slicing, and the
    # chosen service is looked up below. Only the page list is shortened.
    services = Service.objects.filter(church=request.user.church).order_by('-date', '-start_time')
    ministry_roles = ensure_default_ministry_roles(request.user.church)
    if request.user.scope_type == 'region' and request.user.scope_region_id:
        regions = regions.filter(pk=request.user.scope_region_id)
        services = services.filter(region_id=request.user.scope_region_id)

    if request.method == 'POST':
        audience_type = request.POST.get('audience_type', 'church')
        region = regions.filter(pk=request.POST.get('region')).first() if request.POST.get('region') else None
        service = services.filter(pk=request.POST.get('service')).first() if request.POST.get('service') else None
        if audience_type == 'visitor_present':
            if request.user.scope_type == 'region' and request.user.scope_region_id:
                region = regions.filter(pk=request.user.scope_region_id).first()
        leadership_role = None
        if audience_type == 'leadership':
            leadership_role = ministry_roles.filter(
                pk=request.POST.get('leadership_role')
            ).first()
            if request.user.scope_type == 'region' and request.user.scope_region_id:
                region = regions.filter(pk=request.user.scope_region_id).first()
        body = request.POST.get('body', '').strip()
        if not body:
            flash_messages.error(request, 'Write a message before sending.')
        elif audience_type == 'leadership' and not leadership_role:
            flash_messages.error(request, 'Choose a leadership group.')
        elif not user_can_send_to(request.user, audience_type, region=region):
            flash_messages.error(request, 'You do not have permission to message that audience.')
        else:
            recipients = get_recipients(
                request.user.church,
                audience_type,
                region=region,
                service=service,
                result=leadership_role.pk if leadership_role else None,
            )
            if audience_type in {'service_present', 'service_absent', 'visitor_present'} and not service:
                recipients = Member.objects.none()
            if not recipients.exists():
                flash_messages.error(request, 'No recipients match that audience.')
            else:
                audience_label = leadership_role.name if leadership_role else dict(SMSMessage.AUDIENCE_CHOICES).get(audience_type, audience_type)
                results = send_bulk(request.user.church, recipients, body, audience_type=audience_type, audience_label=audience_label)
                level, text = describe_delivery(delivery_report(results), noun='recipient')
                getattr(flash_messages, level)(request, text)
                return redirect('message_list')
    return render(request, 'messaging/message_form.html', {
        'regions': regions,
        'services': services[:30],
        'ministry_roles': ministry_roles,
    })


@login_required
def message_detail(request, pk):
    message = get_object_or_404(
        SMSMessage.objects.for_user(request.user).select_related('template'),
        pk=pk,
    )

    return render(request, 'messaging/message_detail.html', {
        'message': message,
        'can_resend': can_resend_messages(request.user),
    })


@login_required
def template_list(request):
    if not can_manage_templates(request.user):
        flash_messages.error(request, 'Only church-wide administrators can manage SMS templates.')
        return redirect('message_list')

    templates = [
        {
            'template': template,
            'label': SYSTEM_TEMPLATES[template.name]['label'],
            'description': SYSTEM_TEMPLATES[template.name]['description'],
            'placeholders': SYSTEM_TEMPLATES[template.name]['placeholders'],
        }
        for template in ensure_system_templates(request.user.church)
    ]
    return render(request, 'messaging/template_list.html', {'templates': templates})


@login_required
def template_edit(request, pk):
    if not can_manage_templates(request.user):
        flash_messages.error(request, 'Only church-wide administrators can manage SMS templates.')
        return redirect('message_list')

    sms_template = get_object_or_404(
        SMSTemplate.objects.filter(church=request.user.church),
        pk=pk,
    )
    form = SMSTemplateForm(request.POST or None, instance=sms_template)
    if request.method == 'POST' and form.is_valid():
        form.save()
        flash_messages.success(request, 'SMS template updated successfully.')
        return redirect('sms_template_list')

    spec = SYSTEM_TEMPLATES.get(sms_template.name, {})
    return render(request, 'messaging/template_form.html', {
        'form': form,
        'sms_template': sms_template,
        'template_label': spec.get('label', sms_template.name),
        'template_description': spec.get('description', ''),
        'template_placeholders': spec.get('placeholders', ()),
    })
