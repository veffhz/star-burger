from django import forms
from django.core.cache import cache
from django.views import View
from django.conf import settings
from django.urls import reverse_lazy
from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import user_passes_test
from geopy import distance

from foodcartapp.models import Product, Restaurant
from foodcartapp.models import Order, RestaurantMenuItem
from restaurateur.geo_helper import fetch_coordinates


class Login(forms.Form):
    username = forms.CharField(
        label='Логин', max_length=75, required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Укажите имя пользователя'
        })
    )
    password = forms.CharField(
        label='Пароль', max_length=75, required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите пароль'
        })
    )


class LoginView(View):
    def get(self, request, *args, **kwargs):
        form = Login()
        return render(request, "login.html", context={
            'form': form
        })

    def post(self, request):
        form = Login(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                if user.is_staff:  # FIXME replace with specific permission
                    return redirect("restaurateur:RestaurantView")
                return redirect("start_page")

        return render(request, "login.html", context={
            'form': form,
            'ivalid': True,
        })


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy('restaurateur:login')


def is_manager(user):
    return user.is_staff  # FIXME replace with specific permission


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_products(request):
    restaurants = list(Restaurant.objects.order_by('name'))
    products = list(Product.objects.prefetch_related('menu_items'))

    default_availability = {restaurant.id: False for restaurant in restaurants}
    products_with_restaurants = []
    for product in products:

        availability = {
            **default_availability,
            **{item.restaurant_id: item.availability for item in product.menu_items.all()},
        }
        orderer_availability = [availability[restaurant.id] for restaurant in restaurants]

        products_with_restaurants.append(
            (product, orderer_availability)
        )

    return render(request, template_name="products_list.html", context={
        'products_with_restaurants': products_with_restaurants,
        'restaurants': restaurants,
    })


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_restaurants(request):
    return render(request, template_name="restaurants_list.html", context={
        'restaurants': Restaurant.objects.all(),
    })


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_orders(request):
    orders = Order.objects.new_orders().cost().prefetch_products().fetch_with_products()
    restaurant_items = RestaurantMenuItem.objects.group_by_restaurant()

    order_items = {}

    for order in orders:
        order_items[order] = []

        order_cached_coordinates = cache.get(order.address.replace(' ', ''))
        if not order_cached_coordinates:
            order_cached_coordinates = fetch_coordinates(settings.YANDEX_API_KEY, order.address)
            cache.set(order.address.replace(' ', ''), order_cached_coordinates, timeout=None)

        order_lon, order_lat = order_cached_coordinates

        for restaurant in restaurant_items:
            result = order.products_set.issubset(restaurant_items[restaurant])

            if result:
                restaurant_cached_coordinates = cache.get(restaurant.address.replace(' ', ''))

                if not restaurant_cached_coordinates:
                    restaurant_cached_coordinates = fetch_coordinates(settings.YANDEX_API_KEY, restaurant.address)
                    cache.set(restaurant.address.replace(' ', ''), restaurant_cached_coordinates, timeout=None)

                restaurant_lon, restaurant_lat = restaurant_cached_coordinates
                distance_km = distance.distance((order_lat, order_lon), (restaurant_lat, restaurant_lon)).km
                order_items[order].append({
                    'restaurant': restaurant, 'distance_km': round(distance_km, 3)
                })

        order_items[order].sort(
            key=lambda restaurant_pair: restaurant_pair['distance_km']
        )

    return render(request, template_name='order_items.html', context={
        'order_items': order_items
    })
