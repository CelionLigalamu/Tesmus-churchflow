from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from attendance.models import Attendance
from .models import Member
from .forms import MemberForm, MinistryRoleForm, SelfRegistrationForm
from .models import DEFAULT_MINISTRY_ROLES, MinistryRole
from .services import ensure_default_ministry_roles, generate_reference_number
from . import importer
from django.views.decorators.csrf import csrf_protect
from tenants.models import Church
from messaging.services import send_reference_number_sms
from audit.services import log_action


def can_manage_roles(user):
    return user.is_authenticated and not user.is_tesmus_staff and bool(user.church_id) and user.scope_type == 'church'


@login_required
def member_list(request):
    search_query = request.GET.get('q', '').strip()

    members = Member.objects.for_user(request.user).select_related(
        'region',
        'branch',
    ).prefetch_related('ministry_roles').order_by('full_name', 'reference_number')

    if search_query:
        members = members.filter(
            Q(full_name__icontains=search_query)
            | Q(reference_number__icontains=search_query)
        )
    total_members = members.count()
    page_obj = Paginator(members, 25).get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)

    context = {
        'members': page_obj,
        'page_obj': page_obj,
        'query_params': query_params.urlencode(),
        'search_query': search_query,
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
        form.save_m2m()
        log_action(request.user, 'member_created', church=member.church, details=f'{member.reference_number} - {member.full_name}')
        messages.success(request, f'{member.full_name} was registered successfully.')
        return redirect('member_detail', pk=member.pk)
    return render(request, 'members/member_form.html', {'form': form})


@login_required
def member_edit(request, pk):
    if request.user.is_tesmus_staff or not request.user.church_id:
        return redirect('home')
    member = get_object_or_404(Member.objects.for_user(request.user), pk=pk)
    form = MemberForm(request.user, request.POST or None, instance=member)
    if request.method == 'POST' and form.is_valid():
        member = form.save()
        log_action(request.user, 'member_updated', church=member.church, details=f'{member.reference_number} - {member.full_name}')
        messages.success(request, f'{member.full_name} was updated successfully.')
        return redirect('member_detail', pk=member.pk)
    return render(request, 'members/member_form.html', {'form': form, 'member': member})


@login_required
def ministry_role_list(request):
    if not can_manage_roles(request.user):
        messages.error(request, 'Only church-wide administrators can manage ministry roles.')
        return redirect('member_list')
    roles = ensure_default_ministry_roles(request.user.church).prefetch_related('members')
    return render(request, 'members/ministry_role_list.html', {'roles': roles})


@login_required
def ministry_role_create(request):
    if not can_manage_roles(request.user):
        messages.error(request, 'Only church-wide administrators can manage ministry roles.')
        return redirect('member_list')
    form = MinistryRoleForm(request.user.church, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        role = form.save(commit=False)
        role.church = request.user.church
        last_order = request.user.church.ministry_roles.order_by('-sort_order').values_list('sort_order', flat=True).first()
        role.sort_order = max(last_order or 0, len(DEFAULT_MINISTRY_ROLES) * 10) + 10
        role.save()
        messages.success(request, f'{role.name} was created.')
        return redirect('ministry_role_list')
    return render(request, 'members/ministry_role_form.html', {'form': form, 'role': None})


@login_required
def ministry_role_edit(request, pk):
    if not can_manage_roles(request.user):
        messages.error(request, 'Only church-wide administrators can manage ministry roles.')
        return redirect('member_list')
    role = get_object_or_404(MinistryRole, pk=pk, church=request.user.church)
    form = MinistryRoleForm(request.user.church, request.POST or None, instance=role)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'{role.name} was updated.')
        return redirect('ministry_role_list')
    return render(request, 'members/ministry_role_form.html', {'form': form, 'role': role})


@login_required
def ministry_role_delete(request, pk):
    if not can_manage_roles(request.user):
        messages.error(request, 'Only church-wide administrators can manage ministry roles.')
        return redirect('member_list')
    role = get_object_or_404(MinistryRole, pk=pk, church=request.user.church)
    if request.method == 'POST':
        name = role.name
        role.delete()
        messages.success(request, f'{name} was removed.')
    return redirect('ministry_role_list')


@login_required
def member_detail(request, pk):
    member = get_object_or_404(
        Member.objects.for_user(request.user).select_related('region', 'branch').prefetch_related('ministry_roles'),
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


@login_required
@require_POST
def member_send_reference(request, pk):
    if request.user.is_tesmus_staff or not request.user.church_id:
        messages.error(request, 'You do not have permission to send reference numbers.')
        return redirect('member_list')

    member = get_object_or_404(Member.objects.for_user(request.user), pk=pk)
    sms_message = send_reference_number_sms(member)

    if sms_message is None:
        messages.warning(
            request,
            'The member reference number template is switched off. '
            'Turn it back on under Church setup to send this message.',
        )
        return redirect('member_detail', pk=member.pk)

    failed = sms_message.status == 'failed'

    # Log the attempt either way: "nobody ever tried" and "we tried and it
    # failed" are very different answers when a member says they never
    # received their reference number.
    log_action(
        request.user,
        'member_reference_sms_failed' if failed else 'member_reference_sms_sent',
        church=member.church,
        details=(
            f'{member.reference_number} - {member.full_name}'
            + (f' - {sms_message.failure_reason}' if failed else '')
        ),
    )

    if failed:
        messages.error(
            request,
            f'Could not send the reference number to {member.full_name}: '
            f'{sms_message.failure_reason or "the SMS provider rejected the message."}',
        )
    else:
        messages.success(
            request,
            f'Reference number sent to {member.full_name} on {member.phone_number}.',
        )

    return redirect('member_detail', pk=member.pk)


IMPORT_SESSION_KEY = 'member_import'


def can_import_members(user):
    return (
        not user.is_tesmus_staff
        and bool(user.church_id)
        and user.scope_type == 'church'
    )


@login_required
def member_import(request):
    """Upload a CSV and preview exactly what it will do before committing."""
    if not can_import_members(request.user):
        messages.error(request, 'Only church-wide administrators can import members.')
        return redirect('member_list')

    church = request.user.church
    context = {'template_header': ','.join(importer.TEMPLATE_HEADER)}

    if request.method == 'POST':
        upload = request.FILES.get('file')
        create_places = bool(request.POST.get('create_places'))
        if not upload:
            messages.error(request, 'Choose a CSV file to upload.')
            return render(request, 'members/member_import.html', context)

        try:
            rows = importer.read_rows(upload)
        except importer.ImportError_ as error:
            messages.error(request, str(error))
            return render(request, 'members/member_import.html', context)

        results = importer.validate(church, rows, create_places=create_places)
        # Held in the session so the confirm step cannot be pointed at a
        # different file than the one that was previewed.
        request.session[IMPORT_SESSION_KEY] = {
            'results': results,
            'create_places': create_places,
            'filename': upload.name,
        }
        context.update({
            'results': results,
            'summary': importer.summarise(results),
            'create_places': create_places,
            'filename': upload.name,
        })
        return render(request, 'members/member_import_preview.html', context)

    return render(request, 'members/member_import.html', context)


@login_required
@require_POST
def member_import_confirm(request):
    if not can_import_members(request.user):
        messages.error(request, 'Only church-wide administrators can import members.')
        return redirect('member_list')

    payload = request.session.pop(IMPORT_SESSION_KEY, None)
    if not payload:
        messages.error(request, 'That import has expired. Please upload the file again.')
        return redirect('member_import')

    created = importer.commit(
        request.user.church,
        payload['results'],
        create_places=payload['create_places'],
    )
    summary = importer.summarise(payload['results'])
    log_action(
        request.user,
        'members_imported',
        church=request.user.church,
        details=(
            f"{payload['filename']}: {created} created, "
            f"{summary['skip']} skipped, {summary['error']} with errors"
        ),
    )
    messages.success(
        request,
        f'{created} member(s) imported. {summary["skip"]} already existed and '
        f'{summary["error"]} row(s) had errors and were not imported. '
        'No text messages were sent.',
    )
    return redirect('member_list')


@csrf_protect
def member_self_register(request, token):
    """Public registration page reached by the church's own link or QR code.

    Open to anyone holding the link, so it is deliberately narrow: it creates a
    member and nothing else, it cannot create regions, and it never reveals
    existing member details.
    """
    church = get_object_or_404(
        Church,
        registration_token=token,
        is_active=True,
        self_registration_enabled=True,
    )
    form = SelfRegistrationForm(church, request.POST or None)

    if request.method == 'POST' and form.is_valid():
        region = form.cleaned_data.get('region')
        member = Member.objects.create(
            church=church,
            region=region,
            branch=region.branches.first() if region else None,
            full_name=form.cleaned_data['full_name'],
            phone_number=form.cleaned_data['phone_number'],
            reference_number=generate_reference_number(church.id),
        )
        log_action(None, 'member_self_registered', church=church,
                   details=f'{member.reference_number} - {member.full_name}')
        # The member needs their reference number to check in at services.
        send_reference_number_sms(member)
        return render(request, 'members/self_register_done.html', {
            'church': church,
            'member': member,
        })

    return render(request, 'members/self_register.html', {
        'church': church,
        'form': form,
    })
