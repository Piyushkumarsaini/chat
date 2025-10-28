from django.shortcuts import render, redirect, get_object_or_404
from .models import ChatUser, ChatMessage
from .forms import SignupForm, PhoneNumberForm, OTPForm
from django.db.models import Q, OuterRef, Subquery, Count
from django.utils import timezone 
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

def get_logged_in_user(request):
	user_id = request.session.get('chat_user_id')
	if not user_id:
		return None
	try:
		return ChatUser.objects.get(id=user_id)
	except ChatUser.DoesNotExist:
		return None

# def signup_view(request):
#     if request.method == 'POST':
#         form = SignupForm(request.POST, request.FILES)
#         if form.is_valid():
#             number = form.cleaned_data['number']

#             # Check if number already exists
#             if ChatUser.objects.filter(number=number).exists():
#                 form.add_error('number', 'This phone number is already registered.')
#             else:
#                 form.save()
#                 return redirect('login')  # or your chat homepage
#     else:
#         form = SignupForm()

#     return render(request, 'chat_app/signup.html', {'form': form})


def phone_login_page(request):
    return render(request, 'chat_app/login.html')

# Step 1: Enter phone number
@csrf_exempt
def phone_login(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'})

        form = PhoneNumberForm(data)
        if not form.is_valid():
            return JsonResponse({'status': 'error', 'message': form.errors.get('number', ['Invalid number'])[0]})

   

        number = form.cleaned_data['number']

        # Check if the user exists first
        try:
            user = ChatUser.objects.get(number=number)
        except ChatUser.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'This number is not registered.'})


        # Generate OTP
        otp = user.generate_otp()
        print(f"✅ OTP for {number}: {otp}")  # Debug — In production, send via SMS API

        request.session['pending_user'] = user.id
        return JsonResponse({'status': 'success', 'message': 'OTP sent to your number.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})


# # Step 2: Verify OTP
# @csrf_exempt
# def verify_otp(request):
#     if request.method == 'POST':
#         data = json.loads(request.body.decode('utf-8'))
#         entered_otp = data.get('otp')
#         user_id = request.session.get('pending_user')

#         if not user_id:
#             return JsonResponse({'status': 'error', 'message': 'Session expired, please start again.'})

#         try:
#             user = ChatUser.objects.get(id=user_id)
#         except ChatUser.DoesNotExist:
#             return JsonResponse({'status': 'error', 'message': 'User not found.'})

#         if user.verify_otp(entered_otp):
#             request.session['is_authenticated'] = True
#             request.session['chat_user_id'] = user.id
#             user.is_online = True
#             user.save()

#             if 'pending_user' in request.session:
#                 del request.session['pending_user']

#             return JsonResponse({
#                 'status': 'success',
#                 'message': 'OTP verified successfully!',
#                 'redirect_url': '/chat/'
#             })
#         else:
#             return JsonResponse({'status': 'error', 'message': 'Invalid or expired OTP.'})

#     return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})


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


def get_profile(request):
    user = get_logged_in_user(request)
    profile_data = {
        'name': user.name,
        'status': user.status,
        'phone': user.number,
        'profile_image': user.image.url if user.image else 'https://via.placeholder.com/120',
    }
    return profile_data


def update_profile(request):
    user = get_logged_in_user(request)
    if request.method == 'POST':
        name = request.POST.get('name')
        status = request.POST.get('status')
        image = request.FILES.get('image')

        if name:
            user.name = name
        if status:
            user.status = status
        if image:
            user.image = image

        user.save()

        return JsonResponse({
            'success': True,
            'name': user.name,
            'status': user.status,
            'image_url': user.image.url if user.image else 'https://via.placeholder.com/120'
        })

    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

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
    
    
	# Call get_profile and add its data to the context
	profile_data = get_profile(request)
    
	return render(request, 'chat_app/chat.html', {
		'receiver': receiver,
		'messages': messages,
		'current_user': user,
		'room_name': room_name,
		'profile_data': profile_data,
	})


# MESSAGES_PER_PAGE = 20

# def load_messages(request, username):
# 	user = get_logged_in_user(request)
# 	if not user:
# 		return JsonResponse({'error': 'Unauthorized'}, status=401)

# 	receiver = get_object_or_404(ChatUser, number=username)

# 	page = int(request.GET.get('page', 1))

# 	messages_qs = ChatMessage.objects.filter(
# 		(Q(sender=user) & Q(receiver=receiver)) |
# 		(Q(sender=receiver) & Q(receiver=user))
# 	).order_by('-timestamp')

# 	paginator = Paginator(messages_qs, MESSAGES_PER_PAGE)
# 	if page > paginator.num_pages:
# 		return JsonResponse({
# 			'messages': [],
# 			'has_more': False
# 		})
# 	page_obj = paginator.get_page(page)

# 	messages = list(page_obj.object_list.values(
# 		'content', 'sender_id', 'receiver_id', 'timestamp'
# 	))

# 	return JsonResponse({
# 		'messages': messages[::-1],  # Reverse to show oldest at top
# 		'has_more': page_obj.has_next()
# 	})

# def lobby_view(request):
#     return render(request, 'chat_app/lobby.html')

import random
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
import phonenumbers
from .models import TempUser, ChatUser
from .forms import SignupForm

# -------------------- SEND OTP --------------------
def send_otp(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

    country_code = request.POST.get('country_code')
    number = request.POST.get('number')

    if not country_code or not number:
        return JsonResponse({'status': 'error', 'message': 'Country code and number required.'})

    # Normalize number to E.164
    try:
        parsed = phonenumbers.parse(f"{country_code}{number}", None)
        full_number = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return JsonResponse({'status': 'error', 'message': 'Invalid phone number format.'})

    # Check if already registered
    if ChatUser.objects.filter(number=full_number).exists():
        return JsonResponse({'status': 'exists', 'message': 'This number is already registered. Please login.'})

    # Generate numeric OTP
    otp = f"{random.randint(100000, 999999)}"

    # Create or update TempUser
    temp_user, created = TempUser.objects.get_or_create(
        number=full_number,
        defaults={'country_code': country_code, 'otp': otp}
    )
    if not created:
        temp_user.otp = otp
        temp_user.otp_created_at = timezone.now()
        temp_user.is_verified = False
        temp_user.save()

    # Send OTP via SMS API here. For testing:
    print(f"OTP for {full_number}: {otp}")

    return JsonResponse({'status': 'success', 'message': 'OTP sent successfully!'})

# -------------------- VERIFY OTP --------------------
def verify_otp(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

    country_code = request.POST.get('country_code')
    number = request.POST.get('number')
    otp_input = request.POST.get('otp')

    # Normalize number to E.164
    try:
        parsed = phonenumbers.parse(f"{country_code}{number}", None)
        full_number = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return JsonResponse({'status': 'error', 'message': 'Invalid phone number format.'})

    try:
        temp_user = TempUser.objects.get(number=full_number)
    except TempUser.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'No OTP request found for this number.'})

    # Check expiry (5 minutes)
    if (timezone.now() - temp_user.otp_created_at).total_seconds() > 300:
        return JsonResponse({'status': 'error', 'message': 'OTP expired, please request again.'})

    # Verify OTP
    if otp_input != temp_user.otp:
        return JsonResponse({'status': 'error', 'message': 'Invalid OTP.'})

    temp_user.is_verified = True
    temp_user.save()

    return JsonResponse({'status': 'success', 'message': 'OTP verified successfully!'})

# -------------------- SIGNUP --------------------
def signup_view(request):
    if request.method == 'POST':
        form = SignupForm(request.POST, request.FILES)
        if form.is_valid():
            country_code = form.cleaned_data['country_code']
            number = form.cleaned_data['number']

            try:
                temp_user = TempUser.objects.get(number=number, is_verified=True)
            except TempUser.DoesNotExist:
                form.add_error('number', 'Please verify OTP before signing up.')
                return render(request, 'chat_app/signup.html', {'form': form})

            if ChatUser.objects.filter(number=number).exists():
                form.add_error('number', 'This phone number is already registered.')
                return render(request, 'chat_app/signup.html', {'form': form})

            form.save()
            temp_user.delete()
            return redirect('login')
    else:
        form = SignupForm()

    return render(request, 'chat_app/signup.html', {'form': form})

