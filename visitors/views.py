from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import Visitor


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

    return render(
        request,
        'visitors/visitor_list.html',
        {
            'visitors': visitors,
            'search_query': search_query,
            'total_visitors': visitors.count(),
        },
    )


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
