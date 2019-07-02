from django.shortcuts import render
from rango.models import Category,Page, User, UserProfile
from rango.forms import CategoryForm,PageForm, UserForm, UserProfileForm
from django.contrib.auth import authenticate, login
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from datetime import datetime
from rango.bing_search import google_search
from django.shortcuts import redirect
from django.template import RequestContext

def get_category_list(max_results=0, starts_with=''):
    cat_list = []
    if starts_with:
        cat_list = Category.objects.filter(name__istartswith=starts_with)

    if max_results > 0:
        if len(cat_list) > max_results:
            cat_list = cat_list[:max_results]
    return cat_list

def get_server_side_cookie(request, cookie, default_val=None):
    val = request.session.get(cookie)

    if not val:
        val = default_val
    return val

def visitor_cookie_handler(request):
    visits = int(get_server_side_cookie(request, 'visits', '1'))

    last_visit_cookie = get_server_side_cookie(request, 'last_visit', str(datetime.now()))
    last_visit_time = datetime.strptime(last_visit_cookie[:-7], '%Y-%m-%d %H:%M:%S')

    if (datetime.now() - last_visit_time).seconds > 0:
        visits = visits + 1
        request.session['last_visit'] = str(datetime.now())
    else:
        visits = 1
        request.session['last_visit']  = last_visit_cookie

    request.session['visits'] = visits

def index(request):
    category_list = Category.objects.order_by('-likes')[:5]
    top_five_pages = Page.objects.order_by('-views')[:5]
#    print(top_five_pages)
    context_dict = {'categories': category_list, 'pages': top_five_pages}

    visitor_cookie_handler(request)
    context_dict['visits'] = request.session['visits']

    return render(request, 'rango/index.html', context=context_dict)

def about(request):
    context_dict = {'boldmessage':"Bro bro bro"}

    visitor_cookie_handler(request)
    context_dict['visits'] = request.session['visits']
    return render(request, 'rango/about.html', context=context_dict)

def show_category(request, category_name_slug):
    context_dict = {}
    result_list = []

    try:
        category = Category.objects.get(slug = category_name_slug)
        category.views += 1
        category.save()

        pages = Page.objects.filter(category = category).order_by('-views')

        query=""
        if request.method == 'POST':
            query = request.POST['query'].strip()
            if query:
                result_list = google_search(query, num=10)


        context_dict['result_list'] = result_list
        context_dict['pages'] = pages
        context_dict['category'] = category
    except Category.DoesNotExist:
        context_dict['category'] = None
        context_dict['pages'] = None

    return render(request, 'rango/category.html', context_dict)


@login_required
def add_category(request):
    form = CategoryForm()

    if request.method == 'POST':
        form = CategoryForm(request.POST)

        if form.is_valid():
            form.save(commit = True)

            return index(request)
        else:
            print(form.errors)
    return render(request, 'rango/add_category.html', {'form': form})

@login_required
def add_page(request, category_name_slug):
    try:
        category = Category.objects.get(slug=category_name_slug)
    except Category.DoesNotExist:
        category = None

    form = PageForm()

    if request.method == 'POST':
        form = PageForm(request.POST)

        if form.is_valid():
            if category:
                page = form.save(commit = False)
                page.category = category
                page.views = 0
                page.save()
                return show_category(request, category_name_slug)
        else:
            print(form.errors)
    context_dict={'form':form, 'category' : category}
    return render(request, 'rango/add_page.html', context_dict)


def search(request):
    result_list = []
    query=""
    if request.method == 'POST':
        query = request.POST['query'].strip()
        if query:
            result_list = google_search(query, num=10)

    return render(request, 'rango/search.html', {'result_list': result_list,
                                                 'query':query})

def track_url(request):
    #todo
    page_id = None
    if request.method == 'GET':
        if 'page_id' in request.GET:
            page_id = request.GET['page_id']
            print(page_id)

            try:
                page = Page.objects.get(id=page_id)
                page.views += 1
                page.save()
                return redirect(page.url)
            except Page.DoesNotExist:
                return HttpResponseRedirect(reverse('index'))
    
    return HttpResponseRedirect(reverse('index'))


@login_required
def profile(request, username):
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return HttpResponseRedirect(reverse('index'))

    userprofile = UserProfile.objects.get_or_create(user=user)[0]
    form = UserProfileForm({'website': userprofile.website, 'picture': userprofile.picture})
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES,instance=userprofile)
        if form.is_valid():
            form.save(commit=True)
            return HttpResponseRedirect(reverse('rango:profile', args=[user.username]))
        else:
            print(form.errors)
    return render(request, 'rango/profile.html', {'userprofile':userprofile,'selecteduser':user,'profile_form': form})

@login_required
def register_profile(request):
    if request.method == "POST":
        profile_form = UserProfileForm(request.POST, request.FILES)
        if profile_form.is_valid():
            profile = profile_form.save(commit = False)
            profile.user = request.user
            profile.save()

            return HttpResponseRedirect(reverse('index'))
        else:
            print(profile_form.errors)
            return HttpResponseRedirect(reverse('index'))
    else:
        profile_form = UserProfileForm()
        return render(request, 'registration/profile_registration.html', {'profile_form':profile_form}, RequestContext(request))

@login_required
def list_profiles(request):
    userprofile_list = UserProfile.objects.all()
    return render(request, 'rango/list_profiles.html', {'userprofile_list' : userprofile_list})

@login_required
def like_category(request):
    cat_id = None
    if request.method == 'GET':
        cat_id = request.GET['category_id']
        likes = 0
        if cat_id:
            cat = Category.objects.get(id=int(cat_id))
            if cat:
                likes = cat.likes + 1
                cat.likes = likes
                cat.save()
    return HttpResponse(likes)

def suggest_category(request):
    cat_list = []
    starts_with = ''
    if request.method == 'GET':
        starts_with = request.GET['suggestion']
        cat_list = get_category_list(8, starts_with)
    return render(request, 'rango/cats.html', {'cats': cat_list })

@login_required
def auto_add_page(request):
    cat_id = None
    url = None
    title = None
    context_dict = {}
    if request.method == 'GET':
        cat_id = request.GET['category_id']
        url = request.GET['url']
        title = request.GET['title']
        if cat_id:
            category = Category.objects.get(id=int(cat_id))
            p = Page.objects.get_or_create(category=category, title=title, url=url)
            pages = Page.objects.filter(category=category).order_by('-views')
            # Adds our results list to the template context under name pages.
            context_dict['pages'] = pages
    return render(request, 'rango/page_list.html', context_dict)


'''
def register(request):
    registered = False

    if request.method == 'POST':
        user_form = UserForm(data=request.POST)

        profile_form = UserProfileForm(data=request.POST)

        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()

            user.set_password(user.password)
            user.save()

            profile = profile_form.save(commit = False)

            profile.user = user

            if 'profile_photo' in request.FILES:
                profile.picture = request.FILES['profile_photo']

            profile.save()

            registered = True

        else:
            print(user_form.errors, profile_form.errors)

    else:
        user_form = UserForm()
        profile_form = UserProfileForm()

    return render(request, 'rango/register.html', {'user_form':user_form,
                                                   'profile_form':profile_form,
                                                   'registered':registered})

'''

'''
def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(username = username, password=password)
        
        if user:
            if user.is_active:
                login(request,user)
                return HttpResponseRedirect(reverse('index'))

            else:
                return HttpResponse("Your Rango account is disabled")


        else:
            print("Invalid login details: {0}, {1}".format(username, password))
            return HttpResponse("Invalid login details supplied")
    else:
        return render(request, 'rango/login.html', {})

'''

'''
@login_required
def user_logout(request):
    logout(request)
    return HttpResponseRedirect(reverse('index'))
'''



