from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .models import Visitor
from .forms import VisitorForm
from audit.services import log_action


@login_required
def visitor_list(request):
    search_query = request.GET.get('q', '').strip()

    visitors = Visitor.objects.for_user(request.user).select_related(
        'region',
        'branch',
        'converted_to_member',
    ).order_by('-first_visit_date', 'full_name')

    if search_query:
        visitors = visitors.filter(
            Q(full_name__icontains=search_query)
            | Q(phone_number__icontains=search_query)
        )

    total_visitors = visitors.count()
    page_obj = Paginator(visitors, 25).get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)

    return render(
        request,
        'visitors/visitor_list.html',
        {
            'visitors': page_obj,
            'page_obj': page_obj,
            'query_params': query_params.urlencode(),
            'search_query': search_query,
            'total_visitors': total_visitors,
        },
    )


@login_required
def visitor_create(request):
    if request.user.is_tesmus_staff or not request.user.church_id:
        return redirect('home')
    form = VisitorForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        visitor = form.save(commit=False)
        visitor.church = request.user.church
        visitor.save()
        log_action(request.user, 'visitor_recorded', church=visitor.church, details=visitor.full_name)
        messages.success(request, f'{visitor.full_name} was recorded successfully.')
        return redirect('visitor_detail', pk=visitor.pk)
    return render(request, 'visitors/visitor_form.html', {'form': form})


@login_required
def visitor_detail(request, pk):
    visitor = get_object_or_404(
        Visitor.objects.for_user(request.user).select_related(
            'region',
            'branch',
            'converted_to_member',
        ),
        pk=pk,
    )

    return render(request, 'visitors/visitor_detail.html', {'visitor': visitor})
