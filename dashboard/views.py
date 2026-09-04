from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from analytics.services import church_summary


@login_required
def home(request):
    user = request.user
    if user.is_tesmus_staff:
        return render(request, 'dashboard/tesmus_home.html')

    summary = church_summary(user.church)
    return render(request, 'dashboard/church_home.html', {'summary': summary})