from django.shortcuts import render, redirect, get_object_or_404
from .models import ChatUser, ChatMessage
from .forms import SignupForm, LoginForm
from django.db.models import Q


def get_logged_in_user(request):
	user_id = request.session.get('chat_user_id')
	if not user_id:
		return None
	try:
		return ChatUser.objects.get(id=user_id)
	except ChatUser.DoesNotExist:
		return None

def signup_view(request):
	if get_logged_in_user(request):
		return redirect('chat_list')

	if request.method == 'POST':
		form = SignupForm(request.POST)
		if form.is_valid():
			name = form.cleaned_data['name']
			number = form.cleaned_data['number']
			password = form.cleaned_data['password']

			if ChatUser.objects.filter(number=number).exists():
				form.add_error('number', 'A user with that number already exists.')
			else:
				ChatUser.objects.create(name=name, number=number, password=password)
				return redirect('login')
	else:
		form = SignupForm()

	return render(request, 'chat_app/signup.html', {'form': form})
