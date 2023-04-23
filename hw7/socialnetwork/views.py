from asyncio import constants
from cgitb import text
from ctypes.wintypes import POINT
from curses.ascii import isdigit
from multiprocessing import context
import string
from urllib import request
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils import timezone
from django.http import HttpResponse, Http404
from django.utils.timezone import get_current_timezone
from datetime import datetime
from django.core.exceptions import ObjectDoesNotExist
from django.utils.dateparse import parse_datetime

from socialnetwork.forms import LoginForm, ProfileForm, RegisterForm, EntryForm

import json

# Imports the Item class
from socialnetwork.models import *

def login_action(request):
    context = {}

    # Just display the registration form if this is a GET request.
    if request.method == 'GET':
        context['form'] = LoginForm()
        if request.user.is_authenticated:
            reversed_posts = reversed(Post.objects.all())
            return render(request, 'socialnetwork/global_stream.html', { 'posts': reversed_posts })
        return render(request, 'socialnetwork/login.html', context)

    # Creates a bound form from the request POST parameters and makes the 
    # form available in the request context dictionary.
    form = LoginForm(request.POST)
    context['form'] = form

    # Validates the form.
    if not form.is_valid():
        return render(request, 'socialnetwork/login.html', context)

    new_user = authenticate(username=form.cleaned_data['username'],
                            password=form.cleaned_data['password'])

    login(request, new_user)
    return redirect(reverse('global_stream'))

def register_action(request):
    context = {}

    # Just display the registration form if this is a GET request.
    if request.method == 'GET':
        context['form'] = RegisterForm()
        return render(request, 'socialnetwork/register.html', context)

    # Creates a bound form from the request POST parameters and makes the 
    # form available in the request context dictionary.
    form = RegisterForm(request.POST)
    context['form'] = form

    # Validates the form.
    if not form.is_valid():
        return render(request, 'socialnetwork/register.html', context)

    # At this point, the form data is valid.  Register and login the user.
    new_user = User.objects.create_user(username=form.cleaned_data['username'], 
                                        password=form.cleaned_data['password'],
                                        email=form.cleaned_data['email'],
                                        first_name=form.cleaned_data['first_name'],
                                        last_name=form.cleaned_data['last_name'])
    new_user.save()

    # Create a Profile object by passing a key value pair. (user=new_user)
    new_profile = Profile(user=new_user)
    new_profile.save()

    new_user = authenticate(username=form.cleaned_data['username'],
                            password=form.cleaned_data['password'])

    login(request, new_user)
    return redirect(reverse('global_stream'))

@login_required
def global_stream_action(request):
    reversed_posts = reversed(Post.objects.all())

    # Just display the registration form if this is a GET request.
    if request.method == 'GET':
        return render(request, 'socialnetwork/global_stream.html', { 'posts': reversed_posts })

    if 'text' not in request.POST or not request.POST['text']:
        # deal with error
        return render(request, 'socialnetwork/global_stream.html', { 'error': 'You must enter an post to add.' })

    new_post = Post(text=request.POST['text'], user=request.user, creation_time=timezone.now())
    new_post.save()
    return redirect(reverse('global_stream'))

@login_required
def follower_stream_action(request):
    reversed_posts = reversed(Post.objects.all())

    # Just display the registration form if this is a GET request.
    if request.method == 'GET':
        return render(request, 'socialnetwork/follower_stream.html', { 'posts': reversed_posts })
    return render(request, 'socialnetwork/follower_stream.html', { 'posts': reversed_posts })

@login_required
def my_profile_action(request):
    profile = get_object_or_404(Profile, id=request.user.id)

    if request.method == 'GET':
        context = {'profile': request.user.profile,
                'form': ProfileForm(initial={'bio': request.user.profile.bio})}
        return render(request, 'socialnetwork/my_profile.html', context)

    form = ProfileForm(request.POST, request.FILES)
    if not form.is_valid():
        context = {'profile': request.user.profile, 'form': form}
        return render(request, 'socialnetwork/my_profile.html', context)

    pic = form.cleaned_data['picture'] 
    print('Uploaded picture: {} (type={})'.format(pic, type(pic)))

    profile.picture = form.cleaned_data['picture']
    profile.content_type = form.cleaned_data['picture'].content_type
    profile.bio = form.cleaned_data['bio']
    profile.save()

    context = {
        'profile': profile,
        'form': form,
    }
    # return render(request, 'socialnetwork/my_profile.html', context)
    return redirect(reverse('my_profile'))

@login_required
def other_profile_action(request, user_id):
    user = User.objects.get(id=user_id)
    return render(request, 'socialnetwork/other_profile.html', {'profile': user.profile})

def logout_action(request):
    logout(request)
    return redirect(reverse('login'))

@login_required
def get_photo(request, id):
    profile = get_object_or_404(Profile, id=id)
    print('Picture #{} fetched from db: {} (type={})'.format(id, profile.picture, type(profile.picture)))

    # Maybe we don't need this check as form validation requires a picture be uploaded.
    # But someone could have delete the picture leaving the DB with a bad references.
    if not profile.picture:
        raise Http404

    return HttpResponse(profile.picture, content_type=profile.content_type)

def unfollow(request, user_id):
    user_to_unfollow = User.objects.get(id=user_id)
    request.user.profile.following.remove(user_to_unfollow)
    request.user.profile.save()

    return render(request, 'socialnetwork/other_profile.html', {'profile': user_to_unfollow.profile}) 


def follow(request, user_id):
    user_to_follow = User.objects.get(id=user_id)
    request.user.profile.following.add(user_to_follow)
    request.user.profile.save()
    return render(request, 'socialnetwork/other_profile.html', {'profile': user_to_follow.profile}) 


def get_global_json_dumps_serializer(request):
    # To make quiz11 easier, we permit reading the list without logging in. :-)
    if not request.user.id:
        return _my_json_error_response("You must be logged in to do this operation", status=401)

    response_data = []
    for post_item in Post.objects.all():
        comments = Comment.objects.filter(post__id=post_item.id)
        comments_list = []
        for comment in comments:
            comments_item = {
                'id': comment.id,
                'post_id': comment.post.id,
                'user_id': comment.creator.id,
                'user_firstname': comment.creator.first_name,
                'user_lastname': comment.creator.last_name,
                'text': comment.text,
                # 'creation_time': comment.creation_time.strftime("%m/%d/%Y %I:%M %p"),
                'creation_time': comment.creation_time.isoformat(),
            }
            comments_list.append(comments_item)
        post_item = {
            'id': post_item.id,
            'user_id': post_item.user.id,
            'user_firstname': post_item.user.first_name,
            'user_lastname': post_item.user.last_name,
            'text': post_item.text,
            # 'creation_time': post_item.creation_time.strftime("%m/%d/%Y %I:%M %p"),
            'creation_time': post_item.creation_time.isoformat(),
            'comments': comments_list
        }
        response_data.append(post_item)

    response_json = json.dumps(response_data)

    return HttpResponse(response_json, content_type='application/json')

def get_follower_json_dumps_serializer(request):
    # To make quiz11 easier, we permit reading the list without logging in. :-)
    if not request.user.id:
        return _my_json_error_response("You must be logged in to do this operation", status=401)

    response_data = []
    profile = Profile.objects.filter(id=request.user.id)
    id_list = profile.values_list('following__id')
    for post_item in Post.objects.filter(user__id__in=id_list):
        comments = Comment.objects.filter(post__id=post_item.id)
        comments_list = []
        for comment in comments:
            comments_item = {
                'id': comment.id,
                'post_id': comment.post.id,
                'user_id': comment.creator.id,
                'user_firstname': comment.creator.first_name,
                'user_lastname': comment.creator.last_name,
                'text': comment.text,
                # 'creation_time': comment.creation_time.strftime("%m/%d/%Y %I:%M %p"),
                'creation_time': comment.creation_time.isoformat(),
            }
            comments_list.append(comments_item)
        post_item = {
            'id': post_item.id,
            'user_id': post_item.user.id,
            'user_firstname': post_item.user.first_name,
            'user_lastname': post_item.user.last_name,
            'text': post_item.text,
            # 'creation_time': post_item.creation_time.strftime("%m/%d/%Y %I:%M %p"),
            'creation_time': post_item.creation_time.isoformat(),
            'comments': comments_list
        }
        response_data.append(post_item)

    response_json = json.dumps(response_data)

    return HttpResponse(response_json, content_type='application/json')

def _my_json_error_response(message, status=200):
    # You can create your JSON by constructing the string representation yourself (or just use json.dumps)
    response_json = '{ "error": "' + message + '" }'
    return HttpResponse(response_json, content_type='application/json', status=status)

def add_comments(request):
    if not request.user.id:
        return _my_json_error_response("You must be logged in to do this operation", status=401)

    if request.method != 'POST':
        return _my_json_error_response("You must use a POST request for this operation", status=405)

    if not 'comment_text' in request.POST or not request.POST['comment_text'] or not 'post_id' in request.POST or not request.POST['post_id'] or not request.POST['post_id'].isdigit():
        return _my_json_error_response("You must enter an comment to add.", status=400)

    try:
        post = Post.objects.get(id=request.POST['post_id'])
    except ObjectDoesNotExist:
        return _my_json_error_response(f"Post with id={request.POST['post_id']} does not exist.", status=400)

    new_item = Comment(text=request.POST['comment_text'], 
                        creator=request.user,
                        creation_time=timezone.now(),
                        post=Post.objects.get(id=request.POST['post_id']))
    new_item.save()

    if 'follower' in request.POST:
        return get_follower_json_dumps_serializer(request)
    return get_global_json_dumps_serializer(request)
    # return redirect(reverse('global_stream'))

# def add_comments_follower(request):
#     if not request.user.id:
#         return _my_json_error_response("You must be logged in to do this operation", status=401)

#     if request.method != 'POST':
#         return _my_json_error_response("You must use a POST request for this operation", status=405)

#     if not 'comment_text' in request.POST or not request.POST['comment_text'] or not 'post_id' in request.POST or not request.POST['post_id'] or not request.POST['post_id'].isdigit():
#         return _my_json_error_response("You must enter an comment to add.", status=400)

#     try:
#         post = Post.objects.get(id=request.POST['post_id'])
#     except ObjectDoesNotExist:
#         return _my_json_error_response(f"Post with id={request.POST['post_id']} does not exist.", status=400)

#     new_item = Comment(text=request.POST['comment_text'], 
#                         creator=request.user,
#                         creation_time=timezone.now(),
#                         post=Post.objects.get(id=request.POST['post_id']))
#     new_item.save()

#     return get_follower_json_dumps_serializer(request)
