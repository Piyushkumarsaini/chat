from django.shortcuts import render, redirect, get_object_or_404
from .models import ChatUser, ChatMessage, TempUser
from .forms import SignupForm, PhoneNumberForm
from django.db.models import Q, OuterRef, Subquery, Count
from django.utils import timezone 
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import pyotp
from django.middleware.csrf import get_token




# ---------------------------
# Helper Functions
# ---------------------------
def get_logged_in_user(request):
    """Retrieve the currently logged-in ChatUser from session."""
    user_id = request.session.get('chat_user_id')
    if not user_id:
        return None
    try:
        return ChatUser.objects.get(id=user_id)
    except ChatUser.DoesNotExist:
        return None


# ---------------------------
# Views: Signup & User Management
# ---------------------------
def signup_view(request):
    """Render signup form and handle initial registration submission."""
    get_token(request)  # Ensure CSRF token

    if request.method == 'POST':
        form = SignupForm(request.POST, request.FILES)
        if form.is_valid():
            country_code = form.cleaned_data['country_code']
            number = form.cleaned_data['number']

            # Check if number already exists
            if ChatUser.objects.filter(number=number).exists():
                form.add_error('number', 'This phone number is already registered.')
            else:
                form.save()
                return redirect('login')
    else:
        form = SignupForm()

    return render(request, 'chat_app/signup.html', {'form': form})


def check_phone(request):
    """Check if a phone number is already registered."""
    number = request.GET.get('number')
    exists = ChatUser.objects.filter(number=number).exists()
    return JsonResponse({'exists': exists})


# ---------------------------
# Views: OTP Handling
# ---------------------------
def send_otp(request):
    """Generate a time-based OTP and store temporary secret in TempUser."""
    country_code = request.GET.get('country_code')
    number = request.GET.get('number')

    if not number:
        return JsonResponse({'success': False, 'error': 'Phone number is required.'})

    if ChatUser.objects.filter(number=number).exists():
        return JsonResponse({'success': False, 'error': 'This number is already registered.'})

    # Generate OTP
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret, interval=300)  # 5 minutes
    otp = totp.now()

    # Store temporary user
    TempUser.objects.update_or_create(
        number=number,
        defaults={
            'country_code': country_code,
            'otp': otp,  # optional: for debug/logging
            'otp_secret': secret,
            'otp_created_at': timezone.now(),
            'is_verified': False
        }
    )

    # Debug: simulate sending SMS
    print(f"📱 [DEBUG] OTP for {country_code}{number} is {otp}")

    return JsonResponse({'success': True, 'message': 'OTP sent successfully'})


def verify_otp(request):
    """Verify OTP submitted by user."""
    number = request.GET.get('number')
    otp = request.GET.get('otp')

    if not number or not otp:
        return JsonResponse({'success': False, 'error': 'Missing number or OTP.'})

    try:
        temp_user = TempUser.objects.get(number=number)
    except TempUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Number not found.'})

    if not temp_user.otp_secret:
        return JsonResponse({'success': False, 'error': 'No OTP secret found.'})

    totp = pyotp.TOTP(temp_user.otp_secret, interval=300)

    # Allow ±1 step for clock skew
    if totp.verify(otp, valid_window=1):
        temp_user.is_verified = True
        temp_user.save()
        return JsonResponse({'success': True, 'message': 'OTP verified successfully'})
    else:
        return JsonResponse({'success': False, 'error': 'Invalid or expired OTP.'})


# ---------------------------
# Views: Completing Signup
# ---------------------------
def complete_signup(request):
    """
    After OTP verification, create ChatUser and finalize signup.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'})

    name = request.POST.get('name')
    number = request.POST.get('number')
    country_code = request.POST.get('country_code')
    image = request.FILES.get('image')

    if not name:
        return JsonResponse({'success': False, 'error': 'Name is required.'})

    try:
        temp_user = TempUser.objects.get(number=number, is_verified=True)
    except TempUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Phone not verified yet.'})

    # Create or update ChatUser
    user, created = ChatUser.objects.get_or_create(
        number=number,
        defaults={'country_code': country_code, 'name': name, 'image': image}
    )

    # Store user ID in session
    request.session['chat_user_id'] = user.id

    # Cleanup TempUser
    temp_user.delete()

    return JsonResponse({
        'success': True,
        'message': 'Signup complete!',
        'username': user.name or user.number
    })


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


# Step 2: Verify OTP
@csrf_exempt
def login_verify_otp(request):
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        entered_otp = data.get('otp')
        user_id = request.session.get('pending_user')

        if not user_id:
            return JsonResponse({'status': 'error', 'message': 'Session expired, please start again.'})

        try:
            user = ChatUser.objects.get(id=user_id)
        except ChatUser.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'User not found.'})
        if user.verify_otp(entered_otp):
            request.session['is_authenticated'] = True
            request.session['chat_user_id'] = user.id
            user.is_online = True
            user.save()
            if 'pending_user' in request.session:
                del request.session['pending_user']

            return JsonResponse({
                'status': 'success',
                'message': 'OTP verified successfully!',
                'redirect_url': '/chat/'
            })
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid or expired OTP.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

def logout_view(request):
	request.session.flush()
	return redirect('login')

# def get_last_message_subquery(user_id):
#     """
#     Returns a subquery that finds the ID of the most recent message 
#     (sent or received) between the OuterRef user and the current user (user_id).
#     """
#     # Find the ID of the single most recent message
#     return ChatMessage.objects.filter(
#         # Message sent by the other user to current user OR sent by current user to the other user
#         (Q(sender_id=OuterRef('id'), receiver_id=user_id) | Q(sender_id=user_id, receiver_id=OuterRef('id')))
#     ).order_by('-timestamp').values('id')[:1]


def get_profile(request):
    user = get_logged_in_user(request)
    profile_data = {
        'name': user.name,
        'status': user.status,
        'phone': user.number,
        'profile_image': user.image.url if user.image else 'https://via.placeholder.com/120',
    }
    return profile_data

@csrf_exempt
def update_profile(request):
    user = get_logged_in_user(request)
    if request.method == 'POST':
        # Try to handle both JSON and FormData
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            name = data.get('name')
            status = data.get('status')
            image = None
        else:
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
        user.refresh_from_db() 
        
        return JsonResponse({
            'success': True,
            'name': user.name,
            'status': user.status,
            'image_url': user.image.url if user.image else 'https://via.placeholder.com/120'
        })

    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)


def chat_view(request, number=None):
    """Unified chat page — shows chat list and optionally opens a conversation if number provided."""
    current_user = get_logged_in_user(request)
    if not current_user:
        return redirect('login')

    # === chat_list_view logic === (unchanged) ===
    users = ChatUser.objects.exclude(id=current_user.id).annotate(
        last_message_id=Subquery(
            ChatMessage.objects.filter(
                Q(sender_id=OuterRef('id'), receiver_id=current_user.id) |
                Q(sender_id=current_user.id, receiver_id=OuterRef('id'))
            ).order_by('-timestamp').values('id')[:1]
        ),
    )

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
        # safe to call get_profile once (not inside loop ideally)
        profile_data = get_profile(request)
        chat_list_data.append({
            'user': user,
            'initials': initials,
            'time_display': time_display,
            'preview_text': preview_text,
            'data_type': data_type,
            'unread_count': user.unread_count or 0,
        })

    # If a number is provided, try to load that conversation
    receiver = None
    messages = []
    room_name = "global_chat"  # keep same group name as consumer
    if number:
        try:
            receiver = ChatUser.objects.get(number=number)
            messages_qs = ChatMessage.objects.filter(
                Q(sender=current_user, receiver=receiver) |
                Q(sender=receiver, receiver=current_user)
            ).order_by('timestamp')
            messages = list(messages_qs)
        except ChatUser.DoesNotExist:
            receiver = None
            messages = []

    return render(request, 'chat_app/chat.html', {
        'chat_list_data': chat_list_data,
        'current_user': current_user,
        'profile_data': profile_data,
        'receiver': receiver,
        'messages': messages,
        'room_name': room_name,
    })



def get_chat_messages(request, number):
    """Return chat messages between current user and the given number."""
    current_user = get_logged_in_user(request)
    if not current_user:
        return JsonResponse({'error': 'Not logged in'}, status=403)

    try:
        other_user = ChatUser.objects.get(number=number)
    except ChatUser.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

    messages = ChatMessage.objects.filter(
        Q(sender=current_user, receiver=other_user) |
        Q(sender=other_user, receiver=current_user)
    ).order_by('timestamp')

    data = [
        {
            'id': msg.id,
            'content': msg.content,
            'is_sender': msg.sender_id == current_user.id,
            'timestamp': msg.timestamp.strftime('%H:%M'),
            'status': msg.status,
        }
        for msg in messages
    ]

    return JsonResponse({'messages': data})





	# receiver = get_object_or_404(ChatUser, number=username)

	# unread_messages = ChatMessage.objects.filter(
	# sender=receiver,
	# receiver=user,
	# status__in=['sent', 'delivered']
	# )

    
	# unread_messages.update(status='read')

	# messages = ChatMessage.objects.filter(
	# 	(Q(sender=user) & Q(receiver=receiver)) |
	# 	(Q(sender=receiver) & Q(receiver=user))
	# ).order_by('timestamp')

	# # canonical room name for two users: sorted ids joined by underscore
	# ids = sorted([str(user.id), str(receiver.id)])
	# room_name = '_'.join(ids)

	# if request.method == 'POST':
	# 	content = request.POST.get('content')
	# 	if content:
	# 		ChatMessage.objects.create(sender=user, receiver=receiver, content=content, status='sent')
	# 	return redirect('chat', username=receiver.number)
    
    
	# Call get_profile and add its data to the context
	# profile_data = get_profile(request)
    
	# return render(request, 'chat_app/chat.html', {
	# 	'receiver': receiver,
	# 	'messages': messages,
	# 	'current_user': user,
	# 	'room_name': room_name,
	# 	'profile_data': profile_data,
	# })

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