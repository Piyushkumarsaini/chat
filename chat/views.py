from django.shortcuts import render, redirect, get_object_or_404
from .models import ChatUser, ChatMessage
from .forms import SignupForm, LoginForm
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse

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


def login_view(request):
	if get_logged_in_user(request):
		return redirect('chat_list')

	error = None
	if request.method == 'POST':
		form = LoginForm(request.POST)
		if form.is_valid():
			number = form.cleaned_data['number']
			password = form.cleaned_data['password']
			try:
				user = ChatUser.objects.get(number=number)
				if user.password == password:
					request.session['chat_user_id'] = user.id
					return redirect('chat_list')
				else:
					error = 'Invalid credentials.'
			except ChatUser.DoesNotExist:
				error = 'Invalid credentials.'
	else:
		form = LoginForm()

	return render(request, 'chat_app/login.html', {'form': form, 'error': error})


def logout_view(request):
	request.session.flush()
	return redirect('login')


def chat_list_view(request):
	user = get_logged_in_user(request)
	if not user:
		return redirect('login')
	users = ChatUser.objects.exclude(id=user.id)
	return render(request, 'chat_app/chat_list.html', {'users': users, 'current_user': user})


def chat_view(request, username):
	# username here will be number for ChatUser links
	user = get_logged_in_user(request)
	if not user:
		return redirect('login')

	receiver = get_object_or_404(ChatUser, number=username)

	messages = ChatMessage.objects.filter(
		(Q(sender=user) & Q(receiver=receiver)) |
		(Q(sender=receiver) & Q(receiver=user))
	).order_by('timestamp')

	# canonical room name for two users: sorted ids joined by underscore
	ids = sorted([str(user.id), str(receiver.id)])
	room_name = '_'.join(ids)

	if request.method == 'POST':
		content = request.POST.get('content')
		if content:
			ChatMessage.objects.create(sender=user, receiver=receiver, content=content)
		return redirect('chat', username=receiver.number)

	return render(request, 'chat_app/chat.html', {
		'receiver': receiver,
		'messages': messages,
		'current_user': user,
		'room_name': room_name,
	})

MESSAGES_PER_PAGE = 20

def load_messages(request, username):
	user = get_logged_in_user(request)
	if not user:
		return JsonResponse({'error': 'Unauthorized'}, status=401)

	receiver = get_object_or_404(ChatUser, number=username)

	page = int(request.GET.get('page', 1))

	messages_qs = ChatMessage.objects.filter(
		(Q(sender=user) & Q(receiver=receiver)) |
		(Q(sender=receiver) & Q(receiver=user))
	).order_by('-timestamp')

	paginator = Paginator(messages_qs, MESSAGES_PER_PAGE)
	if page > paginator.num_pages:
		return JsonResponse({
			'messages': [],
			'has_more': False
		})
	page_obj = paginator.get_page(page)

	messages = list(page_obj.object_list.values(
		'content', 'sender_id', 'receiver_id', 'timestamp'
	))

	return JsonResponse({
		'messages': messages[::-1],  # Reverse to show oldest at top
		'has_more': page_obj.has_next()
	})

def lobby_view(request):
    return render(request, 'chat_app/lobby.html')