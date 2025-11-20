from django.shortcuts import render

def username_view(request):
    username = None

    if request.method == 'POST':
        username = request.POST.get('username')

    return render(request, 'username_form.html', {'username': username})
