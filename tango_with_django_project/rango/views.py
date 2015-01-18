# Create your views here.
from django.http import HttpResponse
from django.template import RequestContext
from django.shortcuts import render_to_response
from rango.models import Category, Page, UserProfile
from rango.forms import CategoryForm, PageForm, UserForm, UserProfileForm
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib.auth.decorators import login_required
from datetime import datetime
from rango.bing_search import run_query
from django.contrib.auth.models import User 
from django.shortcuts import redirect

def decode_url(url):
	decoded_url = url.replace('_', ' ')
	return decoded_url

def encode_url(url):
	encoded_url = url.replace(' ', '_')
	return encoded_url

def get_category_list(max_results=0, starts_with=''):
	category_list = []
	if starts_with:
		category_list = Category.objects.filter(name__istartswith=starts_with)
	else:
		category_list = Category.objects.all()

	if max_results > 0:
		if len(category_list) > max_results:
			category_list = category_list[:max_results]

	for category in category_list:
		category.url = encode_url(category.name)

	return category_list

def index(request):
	#Obtain the context from the HTTP request
	context = RequestContext(request)

	#Query the database for a list of ALL categories
	#Order the categories by num of likes in descending order
	#Retrieve the top 5 only - or all if less than 5
	#Place the list in our context_dict dictionary which will be passed to the template engine
	category_list = Category.objects.order_by('-likes')[:5]
	context_dict = {'categories':category_list}
	
	# This attribute stores an encoded URL(e.g. spaces replaced with underscores)
	for category in category_list:
		category.url = encode_url(category.name)

	page_list = Page.objects.order_by('-views')[:5]
	context_dict['pages'] = page_list
	
	if request.session.get('last_visit'):
		last_visit_time = request.session.get('last_visit')
		visits = request.session.get('visits', 0)

		if (datetime.now() - datetime.strptime(last_visit_time[:-7], 
			"%Y-%m-%d %H:%M:%S")).seconds > 5:
			request.session['visits'] = visits+1
			request.session['last_visit'] = str(datetime.now())

	else:
		request.session['last_visit'] = str(datetime.now())
		request.session['visits'] = 1

	return render_to_response('rango/index.html', context_dict, context)

def about(request):
	context = RequestContext(request)
	category_list = get_category_list()
	context_dict = {}
	context_dict['category_list'] = category_list

	if request.session.get('visits'):
		context_dict['visits'] = request.session.get('visits')
	else:
		count = 0

	return render_to_response('rango/about.html', context_dict, context)

def category(request, category_name_url):
	# Request our context from the request passed
	context = RequestContext(request)
	category_name = decode_url(category_name_url)
	category_list = get_category_list()
	context_dict = {'category_name': category_name, 'category_name_url': category_name_url}
	context_dict['category_list'] = category_list
	result_list = []

	if request.method == 'POST':
		query = request.POST['query'].strip()

		if query:
			result_list = run_query(query)
			context_dict['result_list'] = result_list

	# Change underscores in the category name to spaces


	try:
		#Get a category with the given name.
		#If not found, exception will be raised
		category = Category.objects.get(name=category_name)

		#Add the category object from the database to the context dictionary
		context_dict['category'] = category

		#Retrieve all of the associated pages
		pages = Page.objects.filter(category=category)
		pages = pages.order_by('-views')
		#Add our results list to the template context under name pages
		context_dict['pages'] = pages


	except Category.DoesNotExist:
		pass 

	# Go render the response and return it
	return render_to_response('rango/category.html', context_dict, context)

def add_category(request):
	#Get the context from the request
	context = RequestContext(request)
	category_list = get_category_list()
	context_dict = {}
	context_dict['category_list'] = category_list
	#A HTTP POST?
	if request.method == 'POST':
		form = CategoryForm(request.POST)
		context_dict['form'] = form
		#Check the validity of form
		if form.is_valid():
			#Save the new category to the database
			form.save(commit=True)

			#Now call the index() view
			#The user will be shown the homepage
			return index(request)
		else:
			print form.errors
	else:
		#Display the form to enter details
		form = CategoryForm()
		context_dict['form'] = form
	return render_to_response('rango/add_category.html', context_dict, context)

def add_page(request, category_name_url):
	context = RequestContext(request)
	category_name = decode_url(category_name_url)
	if request.method == 'POST':
		form = PageForm(request.POST)

		if form.is_valid():
			page = form.save(commit=False)

			try:
				cat = Category.objects.get(name=category_name)
				page.category = cat
			except Category.DoesNotExist:
				return render_to_response('rango/add_category.html', {}, context)

			#set default value = 0 
			page.views = 0
			page.save()

			return category(request, category_name_url)
		else:
			print form.errors

	else:
		form = PageForm()

	return render_to_response('rango/add_page.html',
		{'category_name_url':category_name_url,
		'category_name': category_name, 'form': form},
		context)

def register(request):
	context = RequestContext(request)

	# A boolean value for telling the template whether the registration was successful
	registered = False

	#If it's a HTTP POst, process form data
	if request.method == 'POST':
		user_form = UserForm(data=request.POST)
		profile_form = UserProfileForm(data=request.POST)

		if user_form.is_valid() and profile_form.is_valid():
			#save the user's form data to the database
			user = user_form.save()

			#Hash the password with the set_password method and then save
			user.set_password(user.password)
			user.save()

			#Delay saving the model until we can set the user
			# attributes ourselves
			profile = profile_form.save(commit=False)
			profile.user = user

			if 'picture' in request.FILES:
				profile.picture = request.FILES['picture']

			#Now we save the UserProfile Model instance
			profile.save()

			#Update our registered variable to tell the template registration was successful
			registered = True

		#Invalid forms
		else:
			print user_form.errors, profile_form.errors
	else:
		user_form = UserForm()
		profile_form = UserProfileForm()

	# Render the template depending on the context
	return render_to_response(
		'rango/register.html',
		{'user_form':user_form, 
		'profile_form':profile_form,
		'registered': registered},
		context) 

def user_login(request):
	context = RequestContext(request)

	if request.method == 'POST':
		username = request.POST['username']
		password = request.POST['password']

		user = authenticate(username=username, password=password)
		if user:
			if user.is_active:
				login(request, user)
				return HttpResponseRedirect('/rango/')
			else:
				return HttpResponse("Your Rango account is disabled")
		else:
			print "Invalid login details: {0}, {1}".format(username, password)
			return HttpResponse("Invalid login details supplied.")
	else:
		return render_to_response('rango/login.html', {}, context)

def search(request):
	context = RequestContext(request)
	category_list = get_category_list()
	context_dict = {}
	context_dict['category_list'] = category_list
	result_list = []

	if request.method == 'POST':
		query = request.POST['query'].strip()

		if query:
			result_list = run_query(query)
			context_dict['result_list'] = result_list
	return render_to_response('rango/search.html', context_dict, context)

def profile(request):
	context = RequestContext(request)
	category_list = get_category_list()
	context_dict ={'category_list': category_list}
	u = User.objects.get(username=request.user)

	try:
		up = UserProfile.objects.get(user=u)
	except:
		up = None

	context_dict['user'] = u
	context_dict['userprofile'] = up
	return render_to_response('rango/profile.html', context_dict, context)

def track_url(request):
	context = RequestContext(request)
	page_id = None
	url = '/rango/'
	if request.method == 'GET':
		if 'page_id' in request.GET:
			page_id = request.GET['page_id']
			try:
				page = Page.objects.get(id=page_id)
				page.views = page.views+1
				page.save()
				url = page.url
			except:
				pass

			return redirect(url)

def suggest_category(request):
	context = RequestContext(request)
	category_list = []
	starts_with = ''
	if request.method == 'GET':
		starts_with = request.GET['suggestion']

	category_list = get_category_list(8, starts_with)

	return render_to_response('rango/category_list.html', {'category_list':category_list}, context)

@login_required
def restricted(request):
	return HttpResponse("Since you're logged in, you can see this text!")

@login_required
def user_logout(request):
	logout(request)
	return HttpResponseRedirect('/rango/')

@login_required
def like_category(request):
	context = RequestContext(request)
	
	category_id = None
	if request.method == 'GET':
		category_id = request.GET['category_id']

	likes = 0
	if category_id:
		category = Category.objects.get(id=int(category_id))
		if category:
			likes = category.likes + 1
			category.likes = likes
			category.save()

	return HttpResponse(likes)

def landing(request):
	context = RequestContext(request)

	return render_to_response('rango/landing.html',{}, context)

@login_required
def auto_add_page(request):
	context = RequestContext(request)
	category_id = None
	url = None
	title = None
	context_dict = {}
	if request.method == "GET":
		category_id = request.GET['category_id']
		url = request.GET['url']
		title = request.GET['title']
		if category_id:
			category = Category.objects.get(id=int(category_id))
			p = Page.objects.get_or_create(category=category, title=title, url=url)

			pages = Page.objects.filter(category=category).order_by('-views')
			context_dict['pages'] = pages
	return render_to_response('rango/category.html', context_dict, context)