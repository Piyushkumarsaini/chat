from django.shortcuts import render, redirect, get_object_or_404
from .models import ChatUser, ChatMessage
from .forms import SignupForm, LoginForm
from django.db.models import Q, OuterRef, Subquery, Count
from django.utils import timezone 
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

def get_last_message_subquery(user_id):
    """
    Returns a subquery that finds the ID of the most recent message 
    (sent or received) between the OuterRef user and the current user (user_id).
    """
    # Find the ID of the single most recent message
    return ChatMessage.objects.filter(
        # Message sent by the other user to current user OR sent by current user to the other user
        (Q(sender_id=OuterRef('id'), receiver_id=user_id) | Q(sender_id=user_id, receiver_id=OuterRef('id')))
    ).order_by('-timestamp').values('id')[:1]

def chat_list_view(request):
    current_user = get_logged_in_user(request)
    if not current_user:
        return redirect('login')

    # 1. Fetch users except current user
    users = ChatUser.objects.exclude(id=current_user.id).annotate(
        # Subqueries for last message
        last_message_id=Subquery(
            ChatMessage.objects.filter(
                Q(sender_id=OuterRef('id'), receiver_id=current_user.id) |
                Q(sender_id=current_user.id, receiver_id=OuterRef('id'))
            ).order_by('-timestamp').values('id')[:1]
        ),
    )

    # 2. Add content, time, sender, etc. using last_message_id
    users = users.annotate(
        last_message_content=Subquery(
            ChatMessage.objects.filter(id=OuterRef('last_message_id')).values('content')[:1]
        ),
        last_message_time=Subquery(
            ChatMessage.objects.filter(id=OuterRef('last_message_id')).values('timestamp')[:1]
        ),
        last_message_sender_id=Subquery(
            ChatMessage.objects.filter(id=OuterRef('last_message_id')).values('sender_id')[:1]
        ),
        unread_count=Subquery(
            ChatMessage.objects.filter(
                sender_id=OuterRef('id'),
                receiver_id=current_user.id,
                status__in=['sent', 'delivered']
            ).values('sender_id')
            .annotate(count=Count('id'))
            .values('count')[:1]
        )
    ).order_by('-last_message_time')

    # 3. Build chat_list_data
    chat_list_data = []
    now = timezone.now()

    for user in users:
        initials = ''.join(word[0] for word in user.name.split() if word).upper()[:3]
        if not initials:
            initials = str(user.number)[-2:]

        time_display = '—'
        if user.last_message_time:
            time_diff = now - user.last_message_time
            if time_diff.total_seconds() < 86400:
                time_display = user.last_message_time.strftime('%H:%M')
            else:
                time_display = user.last_message_time.strftime('%d/%m/%y')

        if user.is_online:
            preview_text = 'Online'
        elif user.last_message_content:
            prefix = 'You: ' if user.last_message_sender_id == current_user.id else ''
            preview_text = prefix + user.last_message_content
        else:
            preview_text = 'Start a chat'

        data_type = 'Unread' if user.unread_count and user.unread_count > 0 else 'All'

        chat_list_data.append({
            'user': user,
            'initials': initials,
            'time_display': time_display,
            'preview_text': preview_text,
            'data_type': data_type,
            'unread_count': user.unread_count or 0,
        })

    return render(request, 'chat_app/chat_list.html', {
        'chat_list_data': chat_list_data,
        'current_user': current_user,
    })

def chat_view(request, username):
	# username here will be number for ChatUser links
	user = get_logged_in_user(request)
	if not user:
		return redirect('login')

	receiver = get_object_or_404(ChatUser, number=username)

	unread_messages = ChatMessage.objects.filter(
	sender=receiver,
	receiver=user,
	status__in=['sent', 'delivered']
	)
    
	unread_messages.update(status='read')

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
			ChatMessage.objects.create(sender=user, receiver=receiver, content=content, status='sent')
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